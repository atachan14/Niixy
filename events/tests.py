from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Event, Locality, Station


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
