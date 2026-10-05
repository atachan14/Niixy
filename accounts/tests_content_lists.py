"""Direct reference, authorization, Policy and public rating regressions; SQLite only."""
from uuid import uuid4
from unittest.mock import patch
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import Client, RequestFactory, TestCase, override_settings
from accounts.models import AccountMute, AccountReview
from accounts.internal_urls import resolve_internal_url
from accounts.content_lists import KINDS, route
from interfaces.models import Interface, InterfaceDraft, InterfaceVersion, InterfaceList, InterfaceListReference
from interfaces.services import publish_draft
from rooms.models import Board, BoardPlacement, BoardPolicyCondition, BoardListReference, Collection
from rooms.services import create_room


class ContentListTests(TestCase):
    def setUp(self):
        self.assertEqual(settings.DATABASES['default']['ENGINE'], 'django.db.backends.sqlite3')
        User = get_user_model()
        self.owner = User.objects.create_user('content_owner')
        self.other = User.objects.create_user('content_other')
        self.board = Board.objects.get(placement__collection__account=self.other)
        draft = InterfaceDraft.objects.create(creator=self.other, kind=Interface.ACCOUNT, name='公開IF', description='公開の説明')
        self.interface, _ = publish_draft(draft.pk)
        self.board_list = self.owner.collections.get(name='Main')
        self.interface_list = InterfaceList.objects.create(owner=self.owner, name='IF List', submission_id=uuid4())
        self.client.force_login(self.owner)

    def entries(self):
        return [('board', self.board_list, self.board), ('interface', self.interface_list, self.interface)]

    def test_create_replay_owner_and_original_placement(self):
        before = list(BoardPlacement.objects.values())
        for kind, _, target in self.entries():
            with self.subTest(kind=kind):
                token = uuid4()
                data = {'name':' 新規List ', 'submission_id':token, 'target_url':route(kind,'page',target.pk), 'owner':self.other.pk, 'room':999}
                first = self.client.post(route(kind,'list-create'),data)
                self.assertEqual(first.status_code,201)
                replay = self.client.post(route(kind,'list-create'),{**data,'name':'変更しない'})
                self.assertEqual(replay.status_code,200)
                self.assertEqual(first.json()['list_id'],replay.json()['list_id'])
                spec = KINDS[kind]; item = spec.model.objects.get(pk=first.json()['list_id'])
                self.assertEqual(getattr(item,spec.owner_field),self.owner)
                self.assertEqual(item.name,'新規List');self.assertEqual(item.references.count(),1)
        self.assertEqual(list(BoardPlacement.objects.values()),before)

    def test_duplicate_add_remove_keeps_content_placement_other_lists(self):
        before=list(BoardPlacement.objects.values())
        for kind,item,target in self.entries():
            other_item = KINDS[kind].model.objects.create(**{KINDS[kind].owner_field:self.other,'name':'別List',KINDS[kind].token_field:uuid4()})
            other_ref=KINDS[kind].reference.objects.create(**{KINDS[kind].list_field:other_item,'target':target})
            for _ in range(2):
                response=self.client.post(route(kind,'list-add',item.pk),{'target_url':route(kind,'page',target.pk),'target':999})
                self.assertEqual(response.status_code,200)
                self.assertEqual(response.json()['reference_count'],1)
            ref=item.references.get()
            for _ in range(2):self.assertEqual(self.client.post(route(kind,'list-remove',item.pk,ref.pk)).status_code,200)
            self.assertFalse(item.references.exists());self.assertTrue(type(target).objects.filter(pk=target.pk).exists())
            self.assertTrue(type(other_ref).objects.filter(pk=other_ref.pk).exists())
        self.assertEqual(list(BoardPlacement.objects.values()),before)

    def test_non_owner_and_cross_list_remove(self):
        for kind,item,target in self.entries():
            ref=KINDS[kind].reference.objects.create(**{KINDS[kind].list_field:item,'target':target})
            self.client.force_login(self.other)
            for action,data,extra in [('rename',{'name':'bad'},()),('delete',{},()),('add',{'target_url':route(kind,'page',target.pk)},()),('remove',{},(ref.pk,))]:
                self.assertEqual(self.client.post(route(kind,'list-'+action,item.pk,*extra),data).status_code,404)
            owned=KINDS[kind].model.objects.create(**{KINDS[kind].owner_field:self.other,'name':'本人',KINDS[kind].token_field:uuid4()})
            self.assertEqual(self.client.post(route(kind,'list-remove',owned.pk,ref.pk)).status_code,200)
            self.assertTrue(type(ref).objects.filter(pk=ref.pk).exists())
        self.client.force_login(self.owner)

    def test_room_boardlist_never_accepted_by_reference_api(self):
        room,_=create_room(submission_id=uuid4(),owner=self.owner,name='本人Room',description='',latitude='35',longitude='139')
        room_list=room.collections.first()
        for action,data in [('add',{'target_url':route('board','page',self.board.pk)}),('rename',{'name':'bad'}),('delete',{})]:
            self.assertEqual(self.client.post(route('board','list-'+action,room_list.pk),data).status_code,404)
        self.assertEqual(self.client.get(route('board','list-page',room_list.pk)).status_code,404)
        picker=self.client.get(route('board','picker',self.board.pk))
        self.assertNotContains(picker,route('board','list-add',room_list.pk))
        self.assertEqual(room_list.references.count(),0)

    def test_guest_read_write_denied_and_cache(self):
        self.client.logout()
        for kind,item,target in self.entries():
            KINDS[kind].reference.objects.create(**{KINDS[kind].list_field:item,'target':target})
            for url in [route(kind,'list-index',self.owner.username),route(kind,'list-page',item.pk),route(kind,'list-detail',item.pk),route(kind,'page',target.pk),route(kind,'pane',target.pk)]:
                response=self.client.get(url);self.assertEqual(response.status_code,200);self.assertIn('no-store',response['Cache-Control'])
            self.assertNotContains(self.client.get(route(kind,'list-detail',item.pk)),'data-account-list-form')
            for url in [route(kind,'list-create'),route(kind,'list-rename',item.pk),route(kind,'list-delete',item.pk),route(kind,'list-add',item.pk),route(kind,'list-remove',item.pk,1),route(kind,'rating',target.pk)]:
                self.assertEqual(self.client.post(url).status_code,401)
                self.assertEqual(self.client.get(url).status_code,405)
            self.assertEqual(self.client.get(route(kind,'picker',target.pk)).status_code,401)

    def test_csrf_required_on_every_mutation(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.owner)
        for kind,item,target in self.entries():
            for url in [route(kind,'list-create'),route(kind,'list-rename',item.pk),route(kind,'list-delete',item.pk),route(kind,'list-add',item.pk),route(kind,'list-remove',item.pk,1),route(kind,'rating',target.pk)]:
                self.assertEqual(client.post(url).status_code,403)

    def test_name_validation_and_uncategorized_protection(self):
        for kind,item,_ in self.entries():
            for name in ['   ','x'*(KINDS[kind].max_length+1)]:
                self.assertEqual(self.client.post(route(kind,'list-create'),{'name':name,'submission_id':uuid4()}).status_code,400)
                self.assertEqual(self.client.post(route(kind,'list-rename',item.pk),{'name':name}).status_code,400)
            self.assertEqual(self.client.post(route(kind,'list-rename',item.pk),{'name':' 改名 '}).status_code,200)
            item.refresh_from_db();self.assertEqual(item.name,'改名')
        uncategorized=self.owner.collections.get(is_uncategorized=True)
        for action in ['rename','delete']:self.assertEqual(self.client.post(route('board','list-'+action,uncategorized.pk),{'name':'bad'}).status_code,400)

    def test_list_delete_preserves_targets_and_board_placement_fallback(self):
        own_board=Board.objects.get(placement__collection=self.board_list)
        for kind,item,target in self.entries():
            KINDS[kind].reference.objects.create(**{KINDS[kind].list_field:item,'target':target})
            self.assertEqual(self.client.post(route(kind,'list-delete',item.pk)).status_code,200)
            self.assertTrue(type(target).objects.filter(pk=target.pk).exists())
        own_board.refresh_from_db();self.assertTrue(own_board.placement.collection.is_uncategorized)
        self.assertEqual(self.board.placement.collection.account,self.other)

    def test_board_policy_change_no_reference_privilege_or_metadata_leak(self):
        self.board.description='secret-board-description';self.board.save()
        BoardListReference.objects.create(board_list=self.board_list,target=self.board)
        self.board.policy_conditions.all().delete()
        for response in [self.client.get(route('board','pane',self.board.pk)),self.client.get(route('board','page',self.board.pk)),self.client.get(route('board','list-detail',self.board_list.pk))]:
            self.assertEqual(response.status_code,200);self.assertContains(response,'閲覧できません' if b'data-board-view-unavailable' in response.content else '閲覧不可');self.assertNotContains(response,'secret-board-description')
            self.assertNotContains(response,'data-content-rating-form')
        for action in ['picker','ratings']:self.assertEqual(self.client.get(route('board',action,self.board.pk)).status_code,403)
        self.assertEqual(self.client.post(route('board','rating',self.board.pk),{'sentiment':'fav'}).status_code,403)
        self.assertEqual(self.client.post(route('board','list-add',self.board_list.pk),{'target_url':route('board','page',self.board.pk)}).status_code,403)
        # Referring List owner is not Board owner; original placement owner is rescued.
        self.client.force_login(self.other);self.assertContains(self.client.get(route('board','pane',self.board.pk)),'secret-board-description')

    def test_interface_draft_deleted_and_unpublished_do_not_leak(self):
        private=InterfaceDraft.objects.create(creator=self.other,interface=self.interface,kind=self.interface.kind,name='secret-draft',description='draft-secret-body')
        InterfaceListReference.objects.create(interface_list=self.interface_list,target=self.interface)
        self.assertNotContains(self.client.get(route('interface','list-detail',self.interface_list.pk)),'secret-draft')
        self.assertNotContains(self.client.get(route('interface','page',self.interface.pk)),'draft-secret-body')
        self.interface.status=Interface.DELETED;self.interface.save()
        self.assertNotContains(self.client.get(route('interface','list-detail',self.interface_list.pk)),'公開IF')
        self.assertEqual(self.client.get(route('interface','page',self.interface.pk)).status_code,404)
        self.assertEqual(self.client.post(route('interface','list-add',self.interface_list.pk),{'target_url':route('interface','page',self.interface.pk)}).status_code,400)
        unpublished=Interface.objects.create(creator=self.other,name='unpublished',kind=Interface.ROOM)
        self.assertEqual(self.client.get(route('interface','page',unpublished.pk)).status_code,404)
        self.assertTrue(private.pk)

    def test_definition_reference_follows_public_version_without_application(self):
        InterfaceListReference.objects.create(interface_list=self.interface_list,target=self.interface)
        draft=InterfaceDraft.objects.create(creator=self.other,interface=self.interface,kind=self.interface.kind,name='公開v2')
        publish_draft(draft.pk)
        response=self.client.get(route('interface','list-detail',self.interface_list.pk))
        self.assertContains(response,'公開v2');self.assertContains(response,'公開定義 v2');self.assertContains(response,'AccountIF')
        from interfaces.models import AccountInterfaceImplementation
        self.assertEqual(AccountInterfaceImplementation.objects.count(),0)

    def test_url_rejection_no_fetch_wrong_kinds_origins_ids_admin_and_encoding(self):
        with patch('urllib.request.urlopen',side_effect=AssertionError('external fetch forbidden')):
            for kind,item,target in self.entries():
                good=route(kind,'page',target.pk)
                bad=['https://external.invalid'+good,'http://user:pass@testserver'+good,good+'?x=1',good+'#x',good.replace(str(target.pk),'0'+str(target.pk)),good.replace('/', '/%2f',1),'/admin/','/mypage/interfaces/manage/drafts/1/',route(kind,'page',999999),route(kind,'list-page',item.pk),'/accounts/content_owner/',route('interface' if kind=='board' else 'board','page',self.interface.pk if kind=='board' else self.board.pk)]
                for value in bad:self.assertEqual(self.client.post(route(kind,'list-add',item.pk),{'target_url':value}).status_code,400,value)
                self.assertFalse(item.references.exists())
                self.assertEqual(self.client.post(route(kind,'list-add',item.pk),{'target_url':'http://testserver'+good}).status_code,200)

    @override_settings(NIIXY_REFERENCE_ORIGINS=['https://niixy.example'])
    def test_resolver_typed_list_and_known_origin(self):
        request=RequestFactory().get('/');request.user=self.owner
        for kind,item,target in self.entries():
            self.assertEqual(resolve_internal_url(request,'https://niixy.example'+route(kind,'page',target.pk)).kind,kind)
            self.assertEqual(resolve_internal_url(request,route(kind,'list-page',item.pk)).kind,kind+'-list')
            with self.assertRaises(ValidationError):resolve_internal_url(request,'https://niixy.example:444'+route(kind,'page',target.pk))

    def test_db_uniqueness_and_rating_enum(self):
        for kind,item,target in self.entries():
            spec=KINDS[kind];spec.reference.objects.create(**{spec.list_field:item,'target':target})
            with self.assertRaises(IntegrityError),transaction.atomic():spec.reference.objects.create(**{spec.list_field:item,'target':target})
            spec.rating.objects.create(author=self.owner,target=target,sentiment='fav')
            with self.assertRaises(IntegrityError),transaction.atomic():spec.rating.objects.create(author=self.owner,target=target,sentiment='bad')
            with self.assertRaises(IntegrityError),transaction.atomic():spec.rating.objects.create(author=self.other,target=target,sentiment='love')
            token=uuid4();spec.model.objects.create(**{spec.owner_field:self.owner,spec.token_field:token,'name':'one'})
            with self.assertRaises(IntegrityError),transaction.atomic():spec.model.objects.create(**{spec.owner_field:self.owner,spec.token_field:token,'name':'two'})

    def test_ratings_exclusive_public_idempotent_and_account_review_unchanged(self):
        review=AccountReview.objects.create(author=self.owner,target=self.other,sentiment='love',body='Accountだけの紹介文')
        for kind,_,target in self.entries():
            for sentiment in ['fav','fav','bad','bad','','']:
                response=self.client.post(route(kind,'rating',target.pk),{'sentiment':sentiment,'author':self.other.pk,'target':999})
                self.assertEqual(response.status_code,200)
                self.assertEqual(response.json()['sentiment'],sentiment)
                self.assertEqual(response.json()['fav_count'],int(sentiment=='fav'))
                self.assertEqual(response.json()['bad_count'],int(sentiment=='bad'))
                self.assertEqual(KINDS[kind].rating.objects.filter(target=target).count(),int(bool(sentiment)))
            self.assertEqual(self.client.post(route(kind,'rating',target.pk),{'sentiment':'love'}).status_code,400)
            self.client.post(route(kind,'rating',target.pk),{'sentiment':'fav'})
            self.client.logout();self.assertContains(self.client.get(route(kind,'ratings',target.pk)),'@content_owner')
            self.assertContains(self.client.get(route(kind,'pane',target.pk)),'fav (1)')
            self.client.force_login(self.owner)
        review.refresh_from_db();self.assertEqual((review.sentiment,review.body),('love','Accountだけの紹介文'))

    def test_mute_display_only_counts_total_and_direct_read(self):
        AccountMute.objects.create(muter=self.owner,muted_account=self.other)
        for kind,item,target in self.entries():
            KINDS[kind].reference.objects.create(**{KINDS[kind].list_field:item,'target':target})
            self.assertNotContains(self.client.get(route(kind,'list-detail',item.pk)),route(kind,'page',target.pk))
            self.assertEqual(self.client.get(route(kind,'page',target.pk)).status_code,200)
            self.assertEqual(item.references.count(),1)
            self.client.logout();self.assertContains(self.client.get(route(kind,'list-detail',item.pk)),route(kind,'page',target.pk));self.client.force_login(self.owner)

    def test_deleted_board_reference_has_no_snapshot_and_can_be_removed(self):
        ref=BoardListReference.objects.create(board_list=self.board_list,target=self.board)
        self.board.delete();ref.refresh_from_db();self.assertIsNone(ref.target_id)
        response=self.client.get(route('board','list-detail',self.board_list.pk));self.assertContains(response,'削除済み・公開参照不可')
        self.assertNotContains(response,'content_other')
        self.assertEqual(self.client.post(route('board','list-remove',self.board_list.pk,ref.pk)).status_code,200)

    def test_reference_thread_scope_and_guest_thread_policy(self):
        from events.models import Thread, ThreadPlacement, ThreadPost, ThreadAccessRule
        from rooms.services import seed_board_policy
        collection=self.board.placement.collection
        second=Board.objects.create(name='同じ配置先の別Board',creator=self.other)
        BoardPlacement.objects.create(board=second,kind='collection',collection=collection)
        seed_board_policy(second,account=self.other)
        thread=Thread.objects.create(creator=self.other,title='参照Thread')
        ThreadPost.objects.create(thread=thread,number=1,creator=self.other,body='protected-thread-body')
        ThreadPlacement.objects.create(thread=thread,kind=ThreadPlacement.BOARD,board=second)
        ThreadAccessRule.objects.create(thread=thread,capability='view',audience='account')
        self.assertEqual(self.client.get(route('board','thread',self.board.pk,thread.pk)).status_code,404)
        self.assertContains(self.client.get(route('board','thread',second.pk,thread.pk)),'protected-thread-body')
        self.client.logout()
        denied=self.client.get(route('board','thread',second.pk,thread.pk))
        self.assertEqual(denied.status_code,200);self.assertNotContains(denied,'protected-thread-body')

    def test_list_and_picker_pagination_owner_only(self):
        for kind,item,target in self.entries():
            spec=KINDS[kind]
            for index in range(21):spec.model.objects.create(**{spec.owner_field:self.owner,spec.token_field:uuid4(),'name':'page-list-'+str(index)})
            other_item=spec.model.objects.create(**{spec.owner_field:self.other,spec.token_field:uuid4(),'name':'他人の追加先'})
            first=self.client.get(route(kind,'picker',target.pk));second=self.client.get(route(kind,'picker',target.pk)+'?page=2')
            self.assertEqual(len(first.context['summary_page']),20)
            self.assertTrue(len(second.context['summary_page'])>0)
            self.assertNotContains(first,'他人の追加先');self.assertNotContains(second,route(kind,'list-add',other_item.pk))
