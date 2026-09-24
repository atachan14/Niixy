from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Locality, Station, Thread, ThreadAccessRule, ThreadPlacement, ThreadPost


class ThreadViewTests(TestCase):
    def payload(self, **overrides):
        data = {
            'submission_id': str(uuid4()), 'title': '地図上のThread', 'body': '最初の本文',
            'latitude': '35.681236', 'longitude': '139.767125',
        }
        for capability in ('discover', 'view', 'write'):
            data[f'{capability}_guest'] = 'true'
            data[f'{capability}_account'] = 'true'
        data.update(overrides)
        return data

    def test_guest_creates_thread_opening_post_placement_and_rules(self):
        response = self.client.post(reverse('events:thread-create'), self.payload(), HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        thread = Thread.objects.get()
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(thread.creator)
        self.assertEqual(thread.posts.get().number, 1)
        self.assertEqual(thread.placements.get().kind, ThreadPlacement.NII_MAP)
        self.assertEqual(thread.access_rules.count(), 6)

    def test_duplicate_submission_creates_one_thread(self):
        payload = self.payload()
        self.client.post(reverse('events:thread-create'), payload)
        self.client.post(reverse('events:thread-create'), payload)
        self.assertEqual(Thread.objects.count(), 1)

    def test_guest_can_reply_when_write_rule_allows_it(self):
        thread = Thread.objects.create(title='公開Thread')
        ThreadPost.objects.create(thread=thread, number=1, body='本文')
        for capability in ('discover', 'view', 'write'):
            ThreadAccessRule.objects.create(thread=thread, capability=capability, audience='guest')
        response = self.client.post(reverse('events:thread-post-create', args=[thread.pk]), {'body': '返信'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(thread.posts.count(), 2)

    def test_duplicate_reply_submission_creates_one_post(self):
        thread = Thread.objects.create(title='公開Thread')
        ThreadPost.objects.create(thread=thread, number=1, body='本文')
        for capability in ('discover', 'view', 'write'):
            ThreadAccessRule.objects.create(thread=thread, capability=capability, audience='guest')
        payload = {'body': '返信', 'submission_id': str(uuid4())}
        url = reverse('events:thread-post-create', args=[thread.pk])
        self.client.post(url, payload)
        self.client.post(url, payload)
        self.assertEqual(thread.posts.count(), 2)

    def test_view_and_write_are_enforced(self):
        thread = Thread.objects.create(title='非公開Thread')
        ThreadPost.objects.create(thread=thread, number=1, body='本文')
        response = self.client.post(reverse('events:thread-post-create', args=[thread.pk]), {'body': '返信'})
        self.assertEqual(response.status_code, 403)

    def test_map_hides_undiscoverable_threads(self):
        public = Thread.objects.create(title='公開Thread')
        hidden = Thread.objects.create(title='非公開Thread')
        for thread in (public,):
            ThreadAccessRule.objects.create(thread=thread, capability='discover', audience='guest')
            ThreadPlacement.objects.create(thread=thread, latitude='35.6', longitude='139.7')
        ThreadPlacement.objects.create(thread=hidden, latitude='35.6', longitude='139.7')
        response = self.client.get(reverse('events:map'))
        self.assertContains(response, '公開Thread')
        self.assertNotContains(response, '非公開Thread')

    def test_map_keeps_thread_creation_in_list_pane(self):
        response = self.client.get(reverse('events:map'))

        content = response.content.decode()
        list_start = content.index('<aside class="thread-list-pane"')
        detail_start = content.index('<aside class="thread-detail-pane"')
        form_start = content.index('id="thread-create-form"')
        self.assertGreater(form_start, list_start)
        self.assertLess(form_start, detail_start)
        self.assertNotContains(response, 'id="thread-create-detail"')

    def test_guest_threads_are_shown_by_default_for_an_account(self):
        user = get_user_model().objects.create_user('niixy_user', password='eightchars')
        self.client.force_login(user)
        response = self.client.get(reverse('events:map'))
        self.assertTrue(response.context['filter_preferences']['show_guest_threads'])

    def test_location_search_includes_stations_and_localities(self):
        Station.objects.create(station_code='s1', group_code='g1', name='Test Station', line_name='Line', operator_name='Rail', latitude=35, longitude=139)
        Locality.objects.create(source_key='l1', name='Test Town', full_name='Test Prefecture Test Town', detail='Test Prefecture', kind='town', latitude=35, longitude=139)
        response = self.client.get(reverse('events:location-search'), {'q': 'Test'})
        self.assertEqual({item['name'] for item in response.json()['locations']}, {'Test Station', 'Test Town'})
