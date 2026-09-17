from datetime import timedelta
from uuid import uuid4

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model

from .models import Event, Locality, NiiMapFilterPreference, Station


class EventViewTests(TestCase):
    def test_map_view_is_available_without_login(self):
        Event.objects.create(
            title='定員付きの集まり',
            starts_at=timezone.now(),
            capacity=8,
            latitude=35.681236,
            longitude=139.767125,
        )

        response = self.client.get(reverse('events:map'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'NiiMap')
        self.assertContains(response, '投稿者：ゲスト')
        self.assertContains(response, '募集人数：0/8')
        self.assertContains(response, '詳細：未設定')

    def test_healthcheck_is_available_without_database_access(self):
        response = self.client.get(reverse('events:healthcheck'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'ok')

    def test_guest_can_create_event(self):
        starts_at = timezone.localtime(timezone.now()).replace(microsecond=0)
        response = self.client.post(
            reverse('events:create'),
            {
                'title': '週末のマーケット',
                'description': '駅前で小さなマーケットを開きます。',
                'capacity': '12',
                'starts_at': starts_at.strftime('%Y-%m-%dT%H:%M'),
                'ends_at': '',
                'latitude': '35.681236',
                'longitude': '139.767125',
            },
        )

        event = Event.objects.get()
        self.assertRedirects(response, reverse('events:map'))
        self.assertEqual(event.title, '週末のマーケット')
        self.assertEqual(event.capacity, 12)

    def test_duplicate_submission_id_creates_only_one_event(self):
        starts_at = timezone.localtime(timezone.now()).replace(microsecond=0)
        payload = {
            'submission_id': str(uuid4()),
            'title': '重複しないEvent',
            'capacity': '4',
            'starts_at': starts_at.strftime('%Y-%m-%dT%H:%M'),
            'ends_at': '',
            'latitude': '35.681236',
            'longitude': '139.767125',
        }

        first_response = self.client.post(
            reverse('events:create'),
            payload,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        second_response = self.client.post(
            reverse('events:create'),
            payload,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(Event.objects.count(), 1)

    def test_logged_in_user_is_saved_as_event_creator(self):
        user = get_user_model().objects.create_user('niixy_user', password='eightchars')
        self.client.force_login(user)
        starts_at = timezone.localtime(timezone.now()).replace(microsecond=0)

        self.client.post(
            reverse('events:create'),
            {
                'title': 'Account Event',
                'capacity': '4',
                'starts_at': starts_at.strftime('%Y-%m-%dT%H:%M'),
                'ends_at': '',
                'latitude': '35.681236',
                'longitude': '139.767125',
            },
        )

        self.assertEqual(Event.objects.get().creator, user)

    def test_filter_preferences_default_to_guests_for_guest_visitors(self):
        response = self.client.get(reverse('events:map'))

        self.assertTrue(response.context['filter_preferences']['show_guest_events'])
        self.assertFalse(response.context['filter_preferences']['account_ids_enabled'])

    def test_logged_in_user_can_save_filter_preferences(self):
        user = get_user_model().objects.create_user('niixy_user', password='eightchars')
        self.client.force_login(user)

        response = self.client.post(
            reverse('events:filter-preferences'),
            {
                'range_filter_enabled': 'true',
                'show_ongoing': 'true',
                'show_today': 'false',
                'show_tomorrow': 'true',
                'show_ended': 'false',
                'show_guest_events': 'true',
                'account_ids_enabled': 'true',
                'datetime_section_open': 'true',
                'account_section_open': 'false',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        preference = NiiMapFilterPreference.objects.get(user=user)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(preference.show_ongoing)
        self.assertTrue(preference.show_tomorrow)
        self.assertTrue(preference.show_guest_events)
        self.assertTrue(preference.account_ids_enabled)
        self.assertTrue(preference.datetime_section_open)
        self.assertFalse(preference.account_section_open)
        self.assertFalse(preference.show_today)

    def test_event_creator_can_update_event(self):
        user = get_user_model().objects.create_user('niixy_user', password='eightchars')
        event = Event.objects.create(
            title='Before update',
            creator=user,
            capacity=4,
            starts_at=timezone.now(),
            latitude=35.681236,
            longitude=139.767125,
        )
        self.client.force_login(user)
        starts_at = timezone.localtime(event.starts_at).replace(microsecond=0)

        response = self.client.post(
            reverse('events:update', args=[event.pk]),
            {
                'title': 'After update',
                'description': 'Updated details',
                'capacity': '8',
                'starts_at': starts_at.strftime('%Y-%m-%dT%H:%M'),
                'ends_at': '',
                'latitude': '34.693725',
                'longitude': '135.502253',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        event.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(event.title, 'After update')
        self.assertEqual(event.capacity, 8)
        self.assertEqual(event.creator, user)

    def test_only_creator_can_update_or_delete_event(self):
        creator = get_user_model().objects.create_user('creator', password='eightchars')
        other_user = get_user_model().objects.create_user('other_user', password='eightchars')
        event = Event.objects.create(
            title='Protected Event',
            creator=creator,
            capacity=4,
            starts_at=timezone.now(),
            latitude=35.681236,
            longitude=139.767125,
        )
        self.client.force_login(other_user)

        update_response = self.client.post(reverse('events:update', args=[event.pk]))
        delete_response = self.client.post(reverse('events:delete', args=[event.pk]))

        self.assertEqual(update_response.status_code, 403)
        self.assertEqual(delete_response.status_code, 403)
        self.assertTrue(Event.objects.filter(pk=event.pk).exists())

    def test_event_creator_can_delete_event(self):
        user = get_user_model().objects.create_user('niixy_user', password='eightchars')
        event = Event.objects.create(
            title='Deletable Event',
            creator=user,
            capacity=4,
            starts_at=timezone.now(),
            latitude=35.681236,
            longitude=139.767125,
        )
        self.client.force_login(user)

        response = self.client.post(
            reverse('events:delete', args=[event.pk]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Event.objects.filter(pk=event.pk).exists())

    def test_invalid_event_returns_json_errors_for_map_form(self):
        starts_at = timezone.localtime(timezone.now()).replace(microsecond=0)
        ends_at = starts_at - timedelta(hours=1)

        response = self.client.post(
            reverse('events:create'),
            {
                'title': '終了時刻が早いEvent',
                'capacity': '4',
                'starts_at': starts_at.strftime('%Y-%m-%dT%H:%M'),
                'ends_at': ends_at.strftime('%Y-%m-%dT%H:%M'),
                'latitude': '35.681236',
                'longitude': '139.767125',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('ends_at', response.json()['errors'])

    def test_location_search_includes_stations_and_localities(self):
        for index in range(6):
            Station.objects.create(
                station_code=f'test-station-{index}',
                group_code=f'test-group-{index}',
                name=f'Test Station {index}',
                line_name='Test Line',
                operator_name='Test Railway',
                latitude=35.681236,
                longitude=139.767125,
            )
        Locality.objects.create(
            source_key='test-locality',
            name='Test Town',
            full_name='Test Prefecture Test City Test Town',
            detail='Test Prefecture Test City',
            kind='town',
            latitude=35.681236,
            longitude=139.767125,
        )

        response = self.client.get(reverse('events:location-search'), {'q': 'Test'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {location['name'] for location in response.json()['locations']},
            {
                'Test Station 0',
                'Test Station 1',
                'Test Station 2',
                'Test Station 3',
                'Test Station 4',
                'Test Town',
            },
        )
