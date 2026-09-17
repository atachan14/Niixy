from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


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
