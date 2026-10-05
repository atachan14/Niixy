from uuid import uuid4
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .models import AccountList, AccountListReference, AccountMute, AccountReview
from .internal_urls import resolve_internal_url
from django.test import RequestFactory
from django.core.exceptions import ValidationError


class AccountListTests(TestCase):
    def setUp(self):
        self.assertEqual(settings.DATABASES['default']['ENGINE'], 'django.db.backends.sqlite3')
        User = get_user_model()
        self.owner = User.objects.create_user('list_owner')
        self.target = User.objects.create_user('list_target')
        self.other = User.objects.create_user('list_other')
        self.list = AccountList.objects.create(owner=self.owner, name='知り合い', submission_id=uuid4())
        self.target_url = reverse('accounts:detail', args=[self.target.username])
        self.client.force_login(self.owner)

    def url(self, kind, *extra):
        return reverse('accounts:list-' + kind, args=[self.list.pk, *extra])

    def test_create_and_replayed_create_are_owner_scoped(self):
        token = uuid4()
        data = {'name':' 新しいList ', 'submission_id':token, 'owner':self.other.pk, 'target_url':self.target_url}
        first = self.client.post(reverse('accounts:list-create'), data)
        self.assertEqual(first.status_code,201)
        replay = self.client.post(reverse('accounts:list-create'), {**data,'name':'勝手な変更'})
        self.assertEqual(replay.status_code,200)
        self.assertEqual(first.json()['list_id'],replay.json()['list_id'])
        created = AccountList.objects.get(pk=first.json()['list_id'])
        self.assertEqual((created.owner,created.name),(self.owner,'新しいList'))
        self.assertEqual(created.references.count(),1)

    def test_add_unique_idempotent_and_remove_keeps_account(self):
        data={'target_url':self.target_url,'target':self.other.pk}
        first=self.client.post(self.url('add'),data)
        self.assertEqual(first.status_code,201)
        reference=AccountListReference.objects.get()
        self.assertEqual(reference.target,self.target)
        self.assertEqual(self.client.post(self.url('add'),data).status_code,200)
        self.assertEqual(self.list.references.count(),1)
        for _ in range(2):
            self.assertEqual(self.client.post(self.url('remove',reference.pk)).status_code,200)
        self.assertFalse(self.list.references.exists())
        self.assertTrue(get_user_model().objects.filter(pk=self.target.pk).exists())

    def test_other_owner_cannot_rename_delete_add_remove(self):
        reference=AccountListReference.objects.create(account_list=self.list,target=self.target)
        self.client.force_login(self.other)
        for url,data in [(self.url('rename'),{'name':'違う名前'}),(self.url('delete'),{}),
                         (self.url('add'),{'target_url':self.target_url}),(self.url('remove',reference.pk),{})]:
            self.assertEqual(self.client.post(url,data).status_code,404)
        self.list.refresh_from_db(); self.assertEqual(self.list.name,'知り合い')
        self.assertTrue(self.list.references.exists())
        # Cross-List reference IDs cannot remove a reference from another List.
        own=AccountList.objects.create(owner=self.other,name='本人',submission_id=uuid4())
        self.assertEqual(self.client.post(reverse('accounts:list-remove',args=[own.pk,reference.pk])).status_code,200)
        self.assertTrue(self.list.references.exists())

    def test_guest_public_get_and_all_mutations_denied(self):
        ref=AccountListReference.objects.create(account_list=self.list,target=self.target)
        self.client.logout()
        for url in [self.url('page'),self.url('detail'),reverse('accounts:list-index',args=[self.owner.username])]:
            self.assertEqual(self.client.get(url).status_code,200)
        self.assertContains(self.client.get(self.url('detail')),'@list_target')
        self.assertNotContains(self.client.get(self.url('detail')),'data-account-list-form')
        for url,data in [(reverse('accounts:list-create'),{}),(self.url('rename'),{}),(self.url('delete'),{}),
                         (self.url('add'),{}),(self.url('remove',ref.pk),{})]:
            self.assertEqual(self.client.post(url,data).status_code,401)
        self.assertEqual(self.client.get(self.url('delete')).status_code,405)

    def test_owner_rename_delete_preserve_target_and_other_list(self):
        AccountListReference.objects.create(account_list=self.list,target=self.target)
        other=AccountList.objects.create(owner=self.other,name='残るList',submission_id=uuid4())
        AccountListReference.objects.create(account_list=other,target=self.target)
        self.assertEqual(self.client.post(self.url('rename'),{'name':' 改名 '}).status_code,200)
        self.list.refresh_from_db();self.assertEqual(self.list.name,'改名')
        self.assertEqual(self.client.post(self.url('delete')).status_code,200)
        self.assertTrue(other.references.exists())
        self.assertTrue(get_user_model().objects.filter(pk=self.target.pk).exists())

    def test_saved_review_add_control_and_picker_gate(self):
        picker=reverse('accounts:list-picker',args=[self.target.username])
        self.assertNotContains(self.client.get(self.target_url),'data-account-list-picker-url')
        self.assertEqual(self.client.get(picker).status_code,403)
        review=AccountReview.objects.create(author=self.owner,target=self.target,sentiment='hate',body='紹介文')
        self.assertContains(self.client.get(self.target_url),'data-account-list-picker-url')
        self.assertContains(self.client.get(picker),'知り合い')
        self.assertContains(self.client.get(picker),'URLを共有')
        review.delete()
        self.assertEqual(self.client.get(picker).status_code,403)
        self.client.logout();self.assertEqual(self.client.get(picker).status_code,401)

    def test_free_account_references_need_no_review_and_no_fav_bad(self):
        self.assertEqual(self.client.post(self.url('add'),{'target_url':reverse('accounts:detail',args=[self.owner.username])}).status_code,201)
        self.assertFalse(AccountReview.objects.exists())
        self.assertNotContains(self.client.get(self.url('detail')),'Fav')
        self.assertNotContains(self.client.get(self.url('detail')),'Bad')

    def test_url_allowlist_no_external_fetch_no_other_target_kind(self):
        bad=['https://evil.example'+self.target_url,'http://127.0.0.1:8000'+self.target_url,
             '//testserver'+self.target_url,'http://user@testserver'+self.target_url,'http://@testserver'+self.target_url,
             'file://testserver'+self.target_url,'http://testserver/accounts/no_such_user/',
             self.url('page'),'/mypage/interfaces/layouts/1/','/accounts/list_target/pane/',
             self.target_url+'?pane=people',self.target_url+'#detail','/accounts/%6cist_target/',
             'http://testserver:bad'+self.target_url,'http://:'+self.target_url,'http://:80'+self.target_url,'http://testserver.evil'+self.target_url,
             'http://testserver/'+chr(10),'http://testserver\\@evil.example'+self.target_url]
        with patch('urllib.request.urlopen',side_effect=AssertionError('No external fetch')):
            for value in bad:
                with self.subTest(value=value):
                    self.assertEqual(self.client.post(self.url('add'),{'target_url':value}).status_code,400)
            self.assertEqual(self.client.post(self.url('add'),{'target_url':'http://testserver'+self.target_url}).status_code,201)
        self.assertEqual(self.list.references.count(),1)

    @override_settings(NIIXY_REFERENCE_ORIGINS=['https://niixy.example'])
    def test_explicit_deployment_origin_and_list_resolution(self):
        self.assertEqual(self.client.post(self.url('add'),{'target_url':'https://niixy.example'+self.target_url}).status_code,201)
        request=RequestFactory().get('/')
        target=resolve_internal_url(request,'https://niixy.example'+self.url('page'))
        self.assertEqual((target.kind,target.instance.pk),('account-list',self.list.pk))
        for value in ['https://niixy.example:444'+self.target_url,'https://niixy.example.evil'+self.target_url]:
            with self.assertRaises(ValidationError): resolve_internal_url(request,value)

    def test_invalid_names_and_bad_url_are_atomic(self):
        create=reverse('accounts:list-create')
        for name in ['', '  　', 'x'*81]:
            self.assertEqual(self.client.post(create,{'name':name,'submission_id':uuid4()}).status_code,400)
            self.assertEqual(self.client.post(self.url('rename'),{'name':name}).status_code,400)
        self.assertEqual(self.client.post(create,{'name':'失敗List','submission_id':uuid4(),'target_url':'https://evil.example'}).status_code,400)
        self.assertEqual(AccountList.objects.count(),1)

    def test_database_unique_reference_and_submission(self):
        AccountListReference.objects.create(account_list=self.list,target=self.target)
        with self.assertRaises(IntegrityError),transaction.atomic():
            AccountListReference.objects.create(account_list=self.list,target=self.target)
        with self.assertRaises(IntegrityError),transaction.atomic():
            AccountList.objects.create(owner=self.owner,name='重複',submission_id=self.list.submission_id)

    def test_target_delete_leaves_non_sensitive_placeholder(self):
        reference=AccountListReference.objects.create(account_list=self.list,target=self.target)
        self.target.delete(); reference.refresh_from_db()
        self.assertIsNone(reference.target_id)
        response=self.client.get(self.url('detail'))
        self.assertContains(response,'削除されました')
        self.assertNotContains(response,'list_target')
        self.assertEqual(self.client.post(self.url('remove',reference.pk)).status_code,200)

    def test_pagination_empty_order_escape_and_viewer_mute(self):
        self.assertContains(self.client.get(self.url('detail')),'表示できるAccount参照はありません')
        User=get_user_model()
        for index in range(22):
            target=User.objects.create_user('reference_'+str(index))
            AccountListReference.objects.create(account_list=self.list,target=target)
        response=self.client.get(self.url('detail'))
        self.assertEqual(len(response.context['summary_page']),20)
        self.assertEqual(response.context['summary_page'][0].target.username,'reference_21')
        self.assertEqual(len(self.client.get(self.url('detail'),{'page':2}).context['summary_page']),2)
        AccountListReference.objects.create(account_list=self.list,target=self.target)
        AccountMute.objects.create(muter=self.owner,muted_account=self.target)
        self.assertNotContains(self.client.get(self.url('detail')),'@list_target')
        self.assertEqual(self.client.get(self.target_url).status_code,200)
        self.client.logout();self.assertContains(self.client.get(self.url('detail')),'@list_target')
        self.list.name='<script>alert(1)</script>'; self.list.save()
        self.assertContains(self.client.get(reverse('accounts:list-index',args=[self.owner.username])),'&lt;script&gt;')

    def test_csrf_and_safe_http_methods(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.owner)
        for endpoint in ['add','rename','delete']:
            self.assertEqual(client.post(self.url(endpoint),{}).status_code,403)
            self.assertEqual(self.client.get(self.url(endpoint)).status_code,405)
        page=client.get(self.url('detail'))
        token=client.cookies['csrftoken'].value
        self.assertEqual(client.post(self.url('add'),{'target_url':self.target_url,'csrfmiddlewaretoken':token}).status_code,201)

    def test_list_and_picker_pagination_and_private_cache(self):
        for index in range(22):
            AccountList.objects.create(owner=self.owner,name='List '+str(index),submission_id=uuid4())
        AccountReview.objects.create(author=self.owner,target=self.target,sentiment='love',body='紹介文')
        for url in [reverse('accounts:list-index',args=[self.owner.username]),reverse('accounts:list-picker',args=[self.target.username])]:
            first=self.client.get(url)
            self.assertEqual(len(first.context['summary_page']),20)
            self.assertEqual(first.context['summary_page'][0],self.list)
            self.assertEqual(len(self.client.get(url,{'page':2}).context['summary_page']),3)
            self.assertIn('private',first['Cache-Control'])
            self.assertIn('no-store',first['Cache-Control'])
