from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import AccountProfile
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
        self.assertNotContains(response, '作成したThread')
        self.assertContains(response, reverse('accounts:thread-pane', args=[account.username]))

    def test_thread_pane_lists_created_threads_on_demand(self):
        account = get_user_model().objects.create_user('creator_user', password='eightchars')
        self.make_public_thread(account, '作成したThread')

        response = self.client.get(reverse('accounts:thread-pane', args=[account.username]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '作成したThread')

    def test_account_page_hides_undiscoverable_threads(self):
        account = get_user_model().objects.create_user('creator_user', password='eightchars')
        visible = self.make_public_thread(account, '公開Thread')
        hidden = Thread.objects.create(creator=account, title='非公開Thread')
        ThreadPost.objects.create(thread=hidden, number=1, creator=account, body='開始投稿')

        response = self.client.get(reverse('accounts:thread-pane', args=[account.username]))

        self.assertEqual(list(response.context['created_page'].object_list), [visible])
        self.assertNotContains(response, '非公開Thread')

    def test_replied_threads_are_not_listed_in_thread_tabs(self):
        account = get_user_model().objects.create_user('reply_user', password='eightchars')
        thread = self.make_public_thread(None, '返信したThread')
        ThreadPost.objects.create(thread=thread, number=2, creator=account, body='返信')

        response = self.client.get(reverse('accounts:thread-pane', args=[account.username]))

        self.assertNotContains(response, '返信したThread')
        self.assertNotContains(response, 'data-thread-tab="replied"')

    def test_thread_detail_is_loaded_on_demand(self):
        account = get_user_model().objects.create_user('creator_user', password='eightchars')
        thread = self.make_public_thread(account, '詳細Thread')

        response = self.client.get(reverse('accounts:thread-detail', args=[account.username, thread.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '詳細Thread')
        self.assertContains(response, '開始投稿')


class MyPageTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('my_page_user', password='eightchars')

    def test_guest_is_redirected_from_my_page(self):
        response = self.client.get(reverse('mypage'))

        self.assertRedirects(response, reverse('events:map'))

    def test_display_name_is_saved_and_shown_on_profile(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse('mypage'), {'display_name': '山田 太郎'})

        self.assertRedirects(response, reverse('mypage'))
        self.user.refresh_from_db()
        self.assertEqual(self.user.niixy_profile.display_name, '山田 太郎')
        self.assertEqual(self.user.niixy_profile.display_label, '山田 太郎 @my_page_user')
        profile_response = self.client.get(reverse('accounts:detail', args=[self.user.username]))
        self.assertContains(profile_response, '山田 太郎 @my_page_user')

    def test_display_name_rejects_emoji_and_excessive_width(self):
        self.client.force_login(self.user)

        emoji_response = self.client.post(reverse('mypage'), {'display_name': '山田😀'})
        width_response = self.client.post(reverse('mypage'), {'display_name': 'あ' * 13})

        self.assertContains(emoji_response, '絵文字は使えません。')
        self.assertContains(width_response, '表示名は全角12文字、半角24文字相当までです。')
        self.assertEqual(AccountProfile.objects.get(user=self.user).display_name, '')

    def test_header_menu_includes_my_page_and_profile(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('events:map'))

        self.assertContains(response, 'マイページ')
        self.assertContains(response, 'プロフィール')
