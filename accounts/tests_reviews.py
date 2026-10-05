from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import AccountReview


class AccountReviewTests(TestCase):
    def setUp(self):
        self.assertEqual(settings.DATABASES['default']['ENGINE'], 'django.db.backends.sqlite3')
        self.author = get_user_model().objects.create_user('review_author')
        self.target = get_user_model().objects.create_user('review_target')
        self.other = get_user_model().objects.create_user('review_other')
        self.save_url = reverse('accounts:review-save', args=[self.target.username])
        self.delete_url = reverse('accounts:review-delete', args=[self.target.username])
        self.list_url = reverse('accounts:reviews', args=[self.target.username])
        self.editor_url = reverse('accounts:review-editor', args=[self.target.username])
        self.client.force_login(self.author)

    def create_review(self, **overrides):
        return AccountReview.objects.create(**{
            'author': self.author, 'target': self.target, 'sentiment': 'love', 'body': '紹介文', **overrides,
        })

    def test_author_create_edit_delete_and_counts(self):
        response = self.client.post(self.save_url, {'sentiment': 'love', 'body': '  初めの紹介文 \n'})
        self.assertEqual(response.status_code, 201)
        own = AccountReview.objects.get()
        self.assertEqual(own.body, '初めの紹介文')
        self.assertEqual((own.author, own.target, own.revision), (self.author, self.target, 1))
        page = self.client.get(self.list_url)
        self.assertEqual(page.context['review_counts'], {'total': 1, 'love': 1, 'hate': 0})
        self.assertEqual(page.context['review_score'], 1)
        # Opening Hate is only a draft; no mutation occurs until Save.
        editor = self.client.get(self.editor_url, {'sentiment': 'hate'})
        self.assertContains(editor, '初めの紹介文')
        own.refresh_from_db(); self.assertEqual(own.sentiment, 'love')
        response = self.client.post(self.save_url, {
            'review_id': own.pk, 'revision': 1, 'sentiment': 'hate', 'body': '編集した紹介文',
        })
        self.assertEqual(response.status_code, 200)
        own.refresh_from_db()
        self.assertEqual((own.sentiment, own.revision), ('hate', 2))
        page = self.client.get(self.list_url)
        self.assertEqual(page.context['review_counts'], {'total': 1, 'love': 0, 'hate': 1})
        self.assertEqual(page.context['review_score'], -1)
        self.assertEqual(self.client.post(self.delete_url, {'review_id': own.pk, 'revision': 2}).status_code, 200)
        self.assertFalse(AccountReview.objects.exists())
        page = self.client.get(self.list_url)
        self.assertEqual(page.context['review_counts'], {'total': 0, 'love': 0, 'hate': 0})

    def test_guest_read_only_and_self_prohibited(self):
        own = self.create_review()
        self.client.logout()
        for url in [self.list_url, reverse('accounts:detail', args=[self.target.username]), reverse('accounts:pane', args=[self.target.username])]:
            self.assertContains(self.client.get(url), '紹介文')
        self.assertEqual(self.client.get(self.editor_url).status_code, 401)
        self.assertEqual(self.client.post(self.save_url, {'sentiment': 'hate', 'body': 'Guest'}).status_code, 401)
        self.assertEqual(self.client.post(self.delete_url, {'review_id': own.pk, 'revision': 1}).status_code, 401)
        self.client.force_login(self.target)
        self.assertEqual(self.client.get(self.editor_url).status_code, 403)
        self.assertEqual(self.client.post(self.save_url, {'sentiment': 'love', 'body': '自分'}).status_code, 403)
        self.assertEqual(self.client.post(self.delete_url, {'review_id': own.pk, 'revision': 1}).status_code, 403)
        self.assertTrue(AccountReview.objects.filter(pk=own.pk).exists())
        self.assertFalse(self.client.get(self.list_url).context['can_review'])

    def test_other_author_cannot_change_delete_or_copy_review_to_another_target(self):
        own = self.create_review()
        data = {'review_id': own.pk, 'revision': 1, 'sentiment': 'hate', 'body': '偽装'}
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.save_url, data).status_code, 404)
        self.assertEqual(self.client.post(self.delete_url, data).status_code, 404)
        self.client.force_login(self.author)
        for action in ['review-save', 'review-delete']:
            url = reverse('accounts:' + action, args=[self.other.username])
            self.assertEqual(self.client.post(url, data).status_code, 404)
        own.refresh_from_db(); self.assertEqual((own.sentiment, own.body), ('love', '紹介文'))

    def test_posted_author_and_target_are_ignored(self):
        response = self.client.post(self.save_url, {'sentiment': 'love', 'body': '本文', 'author': self.other.pk, 'target': self.author.pk})
        self.assertEqual(response.status_code, 201)
        own = AccountReview.objects.get()
        self.assertEqual((own.author, own.target), (self.author, self.target))

    def test_validation_blank_length_and_exclusive_choice(self):
        for data in [
            {'sentiment': 'love', 'body': ' \n\t\u3000'}, {'sentiment': 'love', 'body': ''},
            {'sentiment': 'both', 'body': '本文'}, {'sentiment': '', 'body': '本文'},
            {'sentiment': 'love', 'body': 'あ' * 10001},
            {'sentiment': 'love', 'body': '本文', 'revision': 1},
        ]:
            with self.subTest(data_keys=list(data)):
                self.assertEqual(self.client.post(self.save_url, data).status_code, 400)
        self.assertFalse(AccountReview.objects.exists())
        self.assertEqual(self.client.post(self.save_url, {'sentiment': 'love', 'body': 'あ' * 10000}).status_code, 201)
        for revision in ['', 'bad', '0', '-1', '9' * 100]:
            self.assertEqual(self.client.post(self.delete_url, {'review_id': 1, 'revision': revision}).status_code, 400)
        for action in [self.save_url, self.delete_url]:
            self.assertEqual(self.client.post(action, {'review_id': '9' * 100, 'revision': 1, 'sentiment': 'love', 'body': '本文'}).status_code, 400)

    def test_duplicate_create_and_stale_update_delete_do_not_overwrite(self):
        own = self.create_review()
        self.assertEqual(self.client.post(self.save_url, {'sentiment': 'hate', 'body': '二重作成'}).status_code, 409)
        data = {'review_id': own.pk, 'revision': 1, 'sentiment': 'hate', 'body': '最新'}
        self.assertEqual(self.client.post(self.save_url, data).status_code, 200)
        self.assertEqual(self.client.post(self.save_url, {**data, 'body': '古い編集'}).status_code, 409)
        self.assertEqual(self.client.post(self.delete_url, {'review_id': own.pk, 'revision': 1}).status_code, 409)
        own.refresh_from_db()
        self.assertEqual((own.body, own.sentiment, own.revision), ('最新', 'hate', 2))
        self.assertEqual(AccountReview.objects.count(), 1)

    def test_database_constraints_and_model_validation(self):
        self.create_review()
        for overrides in [{'body': 'duplicate'}, {'author': self.target}, {'author': self.other, 'sentiment': 'both'}, {'author': self.other, 'body': ''}]:
            with self.subTest(overrides=overrides), self.assertRaises(IntegrityError), transaction.atomic():
                self.create_review(**overrides)
        for body in ['\n \u3000', 'あ' * 10001]:
            with self.assertRaises(ValidationError):
                AccountReview(author=self.other, target=self.target, sentiment='love', body=body).full_clean()

    def test_csrf_and_http_methods(self):
        secure = Client(enforce_csrf_checks=True)
        secure.force_login(self.author)
        for url in [self.save_url, self.delete_url]:
            self.assertEqual(secure.post(url, {'sentiment': 'love', 'body': '本文'}).status_code, 403)
            self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(self.list_url).status_code, 405)
        self.assertEqual(self.client.post(self.editor_url).status_code, 405)
        secure.get(self.editor_url)
        response = secure.post(self.save_url, {'sentiment': 'love', 'body': 'CSRF成功'}, HTTP_X_CSRFTOKEN=secure.cookies['csrftoken'].value)
        self.assertEqual(response.status_code, 201)

    def test_counts_filters_update_order_pagination_and_collapse(self):
        rows = []
        for index in range(14):
            author = get_user_model().objects.create_user(f'page_author_{index}')
            rows.append(self.create_review(author=author, sentiment='hate' if index % 2 else 'love', body=f'本文{index}'))
        timestamp = timezone.now()
        AccountReview.objects.all().update(updated_at=timestamp)
        page = self.client.get(self.list_url)
        self.assertEqual(page.context['review_counts'], {'total': 14, 'love': 7, 'hate': 7})
        self.assertEqual([row.pk for row in page.context['review_page']], [row.pk for row in rows[-3:][::-1]])
        self.assertContains(page, 'もっと見る')
        page = self.client.get(self.list_url, {'review_expanded': '1'})
        self.assertEqual(len(page.context['review_page']), 10)
        self.assertContains(page, '次へ')
        page = self.client.get(self.list_url, {'review_expanded': '1', 'review_page': '2'})
        self.assertEqual(len(page.context['review_page']), 4)
        page = self.client.get(self.list_url, {'review_expanded': '0', 'review_page': '2'})
        self.assertEqual(page.context['review_page'].number, 1)
        self.assertEqual(len(page.context['review_page']), 3)
        for kind in ['love', 'hate']:
            page = self.client.get(self.list_url, {'review_expanded': '1', 'review_filter': kind})
            self.assertEqual(len(page.context['review_page']), 7)
            self.assertTrue(all(row.sentiment == kind for row in page.context['review_page']))
        self.client.force_login(rows[0].author)
        self.client.post(self.save_url, {'review_id': rows[0].pk, 'revision': 1, 'sentiment': 'hate', 'body': '更新して先頭'})
        page = self.client.get(self.list_url)
        self.assertEqual(page.context['review_page'][0].pk, rows[0].pk)
        self.assertEqual(page.context['review_counts'], {'total': 14, 'love': 6, 'hate': 8})

    def test_markup_escaping_controls_and_invalid_pagination(self):
        self.create_review(body='<script>alert(1)</script>\n二行目')
        page = self.client.get(self.list_url)
        self.assertContains(page, '&lt;script&gt;alert(1)&lt;/script&gt;<br>二行目', html=False)
        self.assertContains(page, 'data-review-edit="love">編集')
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(self.list_url), '>編集</button>')
        self.client.logout()
        page = self.client.get(self.list_url, {'review_filter': 'invalid', 'review_page': 'bad', 'review_expanded': '1'})
        self.assertEqual(page.context['review_filter'], 'all')
        self.assertContains(page, 'data-review-edit="love" aria-pressed="false" disabled')
        self.assertEqual(page.context['review_page'].number, 1)
