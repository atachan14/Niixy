from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from events.models import Thread, ThreadAccessRule, ThreadPost


class AuthenticationTests(TestCase):
    def test_signup_creates_and_logs_in_user(self):
        response = self.client.post(
            reverse('accounts:signup'),
            {
                'username': 'niixy_user',
                'password': 'eightchars',
                'password_confirmation': 'eightchars',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['username'], 'niixy_user')
        self.assertTrue(get_user_model().objects.filter(username='niixy_user').exists())
        self.assertEqual(int(self.client.session['_auth_user_id']), get_user_model().objects.get().pk)

    def test_signup_rejects_invalid_niixy_id(self):
        response = self.client.post(
            reverse('accounts:signup'),
            {
                'username': 'niixy-user',
                'password': 'eightchars',
                'password_confirmation': 'eightchars',
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('username', response.json()['errors'])

    def test_login_and_logout(self):
        user = get_user_model().objects.create_user('niixy_user', password='eightchars')

        login_response = self.client.post(
            reverse('accounts:login'),
            {'username': 'niixy_user', 'password': 'eightchars'},
        )

        self.assertEqual(login_response.status_code, 200)
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)

        logout_response = self.client.post(reverse('accounts:logout'))

        self.assertRedirects(logout_response, reverse('events:map'))
        self.assertNotIn('_auth_user_id', self.client.session)


class AccountPageTests(TestCase):
    def make_public_thread(self, creator, title):
        thread = Thread.objects.create(creator=creator, title=title)
        ThreadPost.objects.create(thread=thread, number=1, creator=creator, body='開始投稿')
        for capability in ('discover', 'view', 'write'):
            ThreadAccessRule.objects.create(thread=thread, capability=capability, audience='guest')
        return thread

    def test_guest_can_open_account_page_and_view_created_thread(self):
        account = get_user_model().objects.create_user('creator_user', password='eightchars')
        self.make_public_thread(account, '作成したThread')

        response = self.client.get(reverse('accounts:detail', args=[account.username]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '@creator_user')
        self.assertContains(response, '作成したThread')

    def test_account_page_hides_undiscoverable_threads(self):
        account = get_user_model().objects.create_user('creator_user', password='eightchars')
        visible = self.make_public_thread(account, '公開Thread')
        hidden = Thread.objects.create(creator=account, title='非公開Thread')
        ThreadPost.objects.create(thread=hidden, number=1, creator=account, body='開始投稿')

        response = self.client.get(reverse('accounts:detail', args=[account.username]))

        self.assertEqual(list(response.context['created_page'].object_list), [visible])
        self.assertNotContains(response, '非公開Thread')

    def test_replied_threads_are_unique_and_ordered_by_latest_reply(self):
        account = get_user_model().objects.create_user('reply_user', password='eightchars')
        first = self.make_public_thread(None, '最初に返信したThread')
        second = self.make_public_thread(None, '最後に返信したThread')
        ThreadPost.objects.create(thread=first, number=2, creator=account, body='返信1')
        ThreadPost.objects.create(thread=first, number=3, creator=account, body='返信2')
        ThreadPost.objects.create(thread=second, number=2, creator=account, body='返信3')

        response = self.client.get(reverse('accounts:detail', args=[account.username]))

        self.assertEqual(list(response.context['replied_page'].object_list), [second, first])
