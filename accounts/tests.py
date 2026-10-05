from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase
from django.urls import reverse

from accounts.models import AccountCondition, AccountProfile
from accounts.services import account_condition_catalog, save_account_condition
from events.models import Thread, ThreadAccessRule, ThreadPlacement, ThreadPost
from interfaces.models import FieldType, Interface, InterfaceDraft
from interfaces.services import publish_draft, publish_field_definition
from rooms.models import Room, RoomMembership


class AccountConditionTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user('condition_owner', password='eightchars')
        self.other = get_user_model().objects.create_user('condition_target', password='eightchars')

    def test_catalog_seeds_defaults_and_can_hide_one(self):
        catalog = account_condition_catalog(self.owner)
        guest = next(item for item in catalog if item['definition'] == {'code': 'guest'})
        self_condition = next(item for item in catalog if item['definition'] == {'code': 'self'})

        self.assertEqual(self_condition['label'], '@condition_owner')

        self.client.force_login(self.owner)
        response = self.client.post(reverse('accounts:account-condition-delete', args=[guest['id']]))

        self.assertEqual(response.status_code, 200)
        self.assertNotIn({'code': 'guest'}, [item['definition'] for item in account_condition_catalog(self.owner)])
        self.assertIn({'code': 'guest'}, [item['definition'] for item in account_condition_catalog(self.owner, include_inactive=True)])

    def test_guest_catalog_only_contains_guest(self):
        catalog = account_condition_catalog(AnonymousUser())

        self.assertEqual(len(catalog), 1)
        self.assertEqual(catalog[0]['definition'], {'code': 'guest'})
        self.assertEqual(catalog[0]['label'], 'Guest')

    def test_catalog_api_returns_only_the_current_accounts_history(self):
        own_condition = save_account_condition(
            self.owner,
            kind=AccountCondition.ACCOUNT,
            definition={'account_id': self.other.pk},
        )
        hidden_condition = save_account_condition(
            self.owner,
            kind=AccountCondition.DEFAULT,
            definition={'code': 'guest'},
        )
        hidden_condition.active = False
        hidden_condition.save(update_fields=['active'])
        other_condition = save_account_condition(
            self.other,
            kind=AccountCondition.ACCOUNT,
            definition={'account_id': self.owner.pk},
        )
        self.client.force_login(self.owner)

        response = self.client.get(reverse('accounts:account-condition-list'))

        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertIn(own_condition.pk, [item['id'] for item in result['conditions']])
        self.assertNotIn(hidden_condition.pk, [item['id'] for item in result['conditions']])
        self.assertIn(hidden_condition.pk, [item['id'] for item in result['available_conditions']])
        self.assertNotIn(other_condition.pk, [item['id'] for item in result['available_conditions']])

    def test_guest_catalog_api_returns_only_guest(self):
        response = self.client.get(reverse('accounts:account-condition-list'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['conditions'], [{
            'id': 'default:guest',
            'kind': 'default',
            'definition': {'code': 'guest'},
            'label': 'Guest',
            'active': True,
        }])
        self.assertEqual(response.json()['available_conditions'], response.json()['conditions'])

    def test_saving_existing_condition_reactivates_without_duplicate(self):
        condition = save_account_condition(
            self.owner,
            kind=AccountCondition.ACCOUNT,
            definition={'account_id': self.other.pk},
        )
        condition.active = False
        condition.save(update_fields=['active'])

        restored = save_account_condition(
            self.owner,
            kind=AccountCondition.ACCOUNT,
            definition={'account_id': self.other.pk},
        )

        self.assertEqual(restored.pk, condition.pk)
        self.assertTrue(restored.active)
        self.assertEqual(self.owner.account_conditions.filter(kind=AccountCondition.ACCOUNT).count(), 1)

    def test_account_search_returns_display_label(self):
        self.other.niixy_profile.display_name = '対象者'
        self.other.niixy_profile.save(update_fields=['display_name'])

        response = self.client.get(reverse('accounts:account-condition-search'), {'q': '対象者'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['accounts'][0]['label'], '対象者 @condition_target')

    def test_room_condition_can_be_saved_and_searched(self):
        room = Room.objects.create(owner=self.owner, created_by=self.owner, name='参加先Room')
        RoomMembership.objects.create(room=room, account=self.owner)

        condition = save_account_condition(
            self.owner,
            kind=AccountCondition.ROOM,
            definition={'room_id': room.pk, 'relation': 'member'},
        )
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse('accounts:account-condition-room-search'),
            {'q': '参加先', 'joined': 'true'},
        )

        self.assertEqual(condition.definition, {'room_id': room.pk, 'relation': 'member'})
        self.assertEqual(condition.label, '参加先Roomに参加')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['rooms'], [
            {'id': room.pk, 'name': room.name, 'label': '参加先Roomに参加'},
        ])

    def test_field_condition_saves_current_version_and_value(self):
        field, version = publish_field_definition(
            creator=self.owner,
            name='年齢',
            field_type=FieldType.INTEGER,
        )

        condition = save_account_condition(
            self.owner,
            kind=AccountCondition.FIELD,
            definition={'field_id': field.pk, 'operator': 'gte', 'value': '20'},
        )

        self.assertEqual(condition.definition, {
            'field_id': field.pk,
            'field_version_id': version.pk,
            'operator': 'gte',
            'value': '20',
        })
        self.assertEqual(condition.label, '年齢@condition_owner: 20')

    def test_blank_field_condition_only_requires_implementation(self):
        field, version = publish_field_definition(
            creator=self.owner,
            name='居住地',
            field_type=FieldType.SHORT_TEXT,
        )

        condition = save_account_condition(
            self.owner,
            kind=AccountCondition.FIELD,
            definition={'field_id': field.pk, 'operator': 'contains', 'value': ''},
        )

        self.assertEqual(condition.definition['field_version_id'], version.pk)
        self.assertEqual(condition.definition['operator'], '')
        self.assertEqual(condition.label, '居住地@condition_ownerを実装')

    def test_field_condition_can_replace_history_item(self):
        field, _ = publish_field_definition(
            creator=self.owner,
            name='年齢',
            field_type=FieldType.INTEGER,
        )
        condition = save_account_condition(
            self.owner,
            kind=AccountCondition.FIELD,
            definition={'field_id': field.pk, 'operator': 'gte', 'value': '20'},
        )

        edited = save_account_condition(
            self.owner,
            kind=AccountCondition.FIELD,
            definition={'field_id': field.pk, 'operator': 'gte', 'value': '30'},
            condition_id=condition.pk,
        )

        self.assertEqual(edited.pk, condition.pk)
        self.assertEqual(edited.definition['value'], '30')
        self.assertEqual(self.owner.account_conditions.filter(active=True, kind=AccountCondition.FIELD).count(), 1)

    def test_field_condition_edit_merges_with_existing_history_item(self):
        field, _ = publish_field_definition(
            creator=self.owner,
            name='年齢',
            field_type=FieldType.INTEGER,
        )
        first = save_account_condition(
            self.owner,
            kind=AccountCondition.FIELD,
            definition={'field_id': field.pk, 'operator': 'gte', 'value': '20'},
        )
        existing = save_account_condition(
            self.owner,
            kind=AccountCondition.FIELD,
            definition={'field_id': field.pk, 'operator': 'gte', 'value': '30'},
        )

        merged = save_account_condition(
            self.owner,
            kind=AccountCondition.FIELD,
            definition={'field_id': field.pk, 'operator': 'gte', 'value': '30'},
            condition_id=first.pk,
        )

        first.refresh_from_db()
        self.assertEqual(merged.pk, existing.pk)
        self.assertFalse(first.active)
        self.assertEqual(self.owner.account_conditions.filter(active=True, kind=AccountCondition.FIELD).count(), 1)


class AuthenticationTests(TestCase):
    def test_signup_creates_and_logs_in_user(self):
        response = self.client.post(
            reverse('accounts:signup'),
            {
                'username': 'niixy_user',
                'display_name': 'こあたみ',
                'password': 'eightchars',
                'password_confirmation': 'eightchars',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['username'], 'niixy_user')
        self.assertTrue(get_user_model().objects.filter(username='niixy_user').exists())
        self.assertEqual(int(self.client.session['_auth_user_id']), get_user_model().objects.get().pk)
        self.assertEqual(get_user_model().objects.get().niixy_profile.display_name, 'こあたみ')

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
        for capability in ('view', 'write'):
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
        self.assertNotContains(response, "sessionStorage.getItem('niixy:account:")

    def test_account_page_exposes_module_workspace(self):
        account = get_user_model().objects.create_user('module_owner', password='eightchars')

        response = self.client.get(reverse('accounts:detail', args=[account.username]))

        self.assertContains(response, 'data-open-account-modules')
        self.assertContains(response, 'data-open-account-account-if')
        self.assertContains(response, 'data-open-account-people')
        self.assertContains(response, 'data-open-account-rooms')
        self.assertContains(response, reverse('accounts:module-pane', args=[account.username]))
        self.assertContains(response, reverse('accounts:room-pane', args=[account.username]))
        self.assertContains(response, 'data-ui-feature-workspace="conversation"')
        self.assertContains(response, 'data-ui-feature-workspace="room"')
        self.assertContains(response, 'data-ui-feature-workspace="account-if"')
        self.assertContains(response, 'data-ui-feature-workspace="people"')
        self.assertContains(response, 'class="account-thread-workspace ui-feature-workspace"')
        self.assertContains(response, 'aria-label="Applied一覧"')
        self.assertNotContains(response, 'AccountIFを選択してください。')
        self.assertContains(response, '>People</button>')
        self.assertContains(response, '>AccountListA</button>')
        self.assertContains(response, '>AccountListB</button>')
        self.assertContains(response, '>Love</button>')
        self.assertContains(response, '>Hate</button>')
        self.assertContains(response, 'account.js?v=20261005-account-layout')
        self.assertContains(response, 'reviews.js?v=20261005-mute-draft')
        self.assertContains(response, 'class="account-overview-content identity-overview-content"')
        self.assertContains(response, 'class="account-hero identity-overview-hero"')
        self.assertContains(response, '<h2>Review</h2>')
        self.assertContains(response, '<h2>Profile</h2>')
        self.assertNotContains(response, 'id="account-page-context"')
        self.assertNotContains(response, '>Interface</button>')

    def test_account_pane_exposes_reusable_overview_and_workspace_endpoints(self):
        account = get_user_model().objects.create_user('pane_owner', password='eightchars')

        response = self.client.get(reverse('accounts:pane', args=[account.username]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-account-fragment')
        self.assertContains(response, 'data-account-title="@pane_owner"')
        self.assertContains(response, reverse('accounts:thread-pane', args=[account.username]))
        self.assertContains(response, reverse('accounts:response-pane', args=[account.username]))
        self.assertContains(response, reverse('accounts:room-pane', args=[account.username]))
        self.assertContains(response, reverse('accounts:module-pane', args=[account.username]))
        self.assertContains(response, 'data-open-account-threads')
        self.assertNotContains(response, '<!doctype html>')

    def test_room_pane_separates_owned_and_joined_rooms(self):
        account = get_user_model().objects.create_user('room_account', password='eightchars')
        other = get_user_model().objects.create_user('other_room_owner', password='eightchars')
        owned = Room.objects.create(owner=account, created_by=account, name='Owned Room')
        joined = Room.objects.create(owner=other, created_by=other, name='Joined Room')
        hidden = Room.objects.create(owner=other, created_by=other, name='Hidden Room')
        RoomMembership.objects.create(room=owned, account=account)
        RoomMembership.objects.create(room=joined, account=account)

        response = self.client.get(reverse('accounts:room-pane', args=[account.username]))

        self.assertEqual(response.status_code, 200)
        self.assertCountEqual(response.context['owner_page'].object_list, [owned])
        self.assertCountEqual(response.context['member_page'].object_list, [owned, joined])
        self.assertContains(response, 'data-ui-tab="owner"')
        self.assertContains(response, 'data-ui-tab="member"')
        self.assertContains(response, f'data-account-room-detail="{owned.pk}"', count=2)
        self.assertContains(response, f'data-account-room-detail="{joined.pk}"', count=1)
        self.assertContains(response, 'data-summary-kind="room"', count=3)
        self.assertNotContains(response, hidden.name)

    def test_profile_module_pane_shows_only_published_active_modules(self):
        account = get_user_model().objects.create_user('module_owner', password='eightchars')
        field, _ = publish_field_definition(
            creator=account,
            name='公開Field',
            field_type=FieldType.SHORT_TEXT,
        )
        deleted_field, _ = publish_field_definition(
            creator=account,
            name='削除Field',
            field_type=FieldType.SHORT_TEXT,
        )
        deleted_field.status = deleted_field.DELETED
        deleted_field.save(update_fields=['status'])
        draft = InterfaceDraft.objects.create(creator=account, kind=Interface.THREAD, name='公開Interface')
        interface, _ = publish_draft(draft.pk)
        InterfaceDraft.objects.create(creator=account, kind=Interface.ACCOUNT, name='編集中Interface')

        response = self.client.get(reverse('accounts:module-pane', args=[account.username]))

        self.assertContains(response, 'data-module-type="element"')
        self.assertContains(response, 'data-module-type="interface"')
        self.assertContains(response, 'data-module-collection="self"')
        self.assertContains(response, 'data-module-collection="saved"')
        self.assertNotContains(response, 'data-module-collection="search"')
        self.assertNotContains(response, 'data-module-collection="editing"')
        self.assertNotContains(response, 'data-module-collection="deleted"')
        self.assertNotContains(response, '>新規作成<')
        self.assertContains(response, field.name)
        self.assertContains(response, interface.name)
        self.assertContains(response, 'data-summary-kind="field"')
        self.assertContains(response, 'data-summary-kind="interface"')
        self.assertNotContains(response, deleted_field.name)
        self.assertNotContains(response, '編集中Interface')

    def test_profile_module_details_are_scoped_to_profile_owner(self):
        account = get_user_model().objects.create_user('module_owner', password='eightchars')
        other = get_user_model().objects.create_user('other_owner', password='eightchars')
        field, _ = publish_field_definition(
            creator=account,
            name='本人Field',
            field_type=FieldType.SHORT_TEXT,
        )
        other_field, _ = publish_field_definition(
            creator=other,
            name='他人Field',
            field_type=FieldType.SHORT_TEXT,
        )
        draft = InterfaceDraft.objects.create(creator=account, kind=Interface.THREAD, name='本人Interface')
        interface, _ = publish_draft(draft.pk)

        field_response = self.client.get(reverse(
            'accounts:module-field-detail', args=[account.username, field.pk]
        ))
        interface_response = self.client.get(reverse(
            'accounts:module-interface-detail', args=[account.username, interface.pk]
        ))
        foreign_response = self.client.get(reverse(
            'accounts:module-field-detail', args=[account.username, other_field.pk]
        ))

        self.assertContains(field_response, '本人Field@module_owner v1/Field', count=1)
        self.assertContains(interface_response, '本人Interface@module_owner v1/ThreadIF', count=1)
        self.assertNotContains(field_response, '定義を編集')
        self.assertNotContains(interface_response, '定義を編集')
        self.assertEqual(foreign_response.status_code, 404)

        self.client.force_login(account)
        owner_field_response = self.client.get(reverse(
            'accounts:module-field-detail', args=[account.username, field.pk]
        ))
        owner_interface_response = self.client.get(reverse(
            'accounts:module-interface-detail', args=[account.username, interface.pk]
        ))

        self.assertContains(owner_field_response, '定義を編集')
        self.assertContains(owner_field_response, f'field_edit={field.pk}')
        self.assertContains(owner_interface_response, '定義を編集')

    def test_thread_pane_lists_created_threads_on_demand(self):
        account = get_user_model().objects.create_user('creator_user', password='eightchars')
        thread = self.make_public_thread(account, '作成したThread')

        response = self.client.get(reverse('accounts:thread-pane', args=[account.username]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '作成したThread')
        self.assertContains(response, f'data-thread-detail="{thread.pk}"')
        self.assertContains(response, 'data-summary-kind="thread"')
        self.assertNotContains(response, '詳細を見る')

    def test_profile_thread_detail_links_niimap_placement_coordinates(self):
        account = get_user_model().objects.create_user('creator_user', password='eightchars')
        thread = self.make_public_thread(account, '配置付きThread')
        ThreadPlacement.objects.create(
            thread=thread,
            latitude='35.681236',
            longitude='139.767125',
        )

        response = self.client.get(reverse('accounts:thread-detail', args=[account.username, thread.pk]))

        self.assertContains(response, 'data-thread-placement-link')
        self.assertContains(response, 'class="ui-placement-row is-sticky"')
        self.assertContains(response, '緯度 35.681236 / 経度 139.767125')
        self.assertContains(
            response,
            f'href="{reverse("events:map")}?latitude=35.681236&amp;longitude=139.767125&amp;zoom=15"',
        )

    def test_thread_pane_lists_threads_even_when_they_are_not_viewable(self):
        account = get_user_model().objects.create_user('creator_user', password='eightchars')
        visible = self.make_public_thread(account, '公開Thread')
        hidden = Thread.objects.create(creator=account, title='非公開Thread')
        ThreadPost.objects.create(thread=hidden, number=1, creator=account, body='開始投稿')

        response = self.client.get(reverse('accounts:thread-pane', args=[account.username]))

        self.assertCountEqual(response.context['created_page'].object_list, [hidden, visible])
        self.assertContains(response, '非公開Thread')

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

    def test_response_pane_lists_responses_newest_first_without_initial_post(self):
        account = get_user_model().objects.create_user('reply_user', password='eightchars')
        older_thread = self.make_public_thread(None, '古い返信先')
        newer_thread = self.make_public_thread(None, '新しい返信先')
        older = ThreadPost.objects.create(thread=older_thread, number=2, creator=account, body='古い返信')
        newer = ThreadPost.objects.create(thread=newer_thread, number=2, creator=account, body='新しい返信')
        ThreadPost.objects.filter(pk=older.pk).update(created_at='2026-01-01T00:00:00Z')
        ThreadPost.objects.filter(pk=newer.pk).update(created_at='2026-01-02T00:00:00Z')

        response = self.client.get(reverse('accounts:response-pane', args=[account.username]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '古い返信')
        self.assertContains(response, '新しい返信')
        self.assertNotContains(response, '開始投稿')
        content = response.content.decode()
        self.assertLess(content.index('新しい返信先'), content.index('古い返信先'))

    def test_response_pane_lists_unviewable_response_without_its_body(self):
        account = get_user_model().objects.create_user('reply_user', password='eightchars')
        thread = Thread.objects.create(title='秘密の返信先')
        ThreadPost.objects.create(thread=thread, number=1, body='開始投稿')
        ThreadPost.objects.create(thread=thread, number=2, creator=account, body='非表示本文')

        response = self.client.get(reverse('accounts:response-pane', args=[account.username]))

        self.assertContains(response, '秘密の返信先')
        self.assertNotContains(response, '非表示本文')

    def test_thread_detail_returns_locked_content_when_thread_is_not_viewable(self):
        account = get_user_model().objects.create_user('reply_user', password='eightchars')
        thread = Thread.objects.create(title='見出しだけのThread')
        ThreadPost.objects.create(thread=thread, number=1, body='開始投稿')
        ThreadPost.objects.create(thread=thread, number=2, creator=account, body='隠す返信本文')

        response = self.client.get(reverse('accounts:thread-detail', args=[account.username, thread.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '見出しだけのThread')
        self.assertContains(response, 'data-thread-view-unavailable')
        self.assertNotContains(response, '隠す返信本文')

    def test_response_pane_paginates_ten_responses(self):
        account = get_user_model().objects.create_user('reply_user', password='eightchars')
        thread = self.make_public_thread(None, '返信先')
        for number in range(2, 13):
            ThreadPost.objects.create(thread=thread, number=number, creator=account, body=f'返信{number}')

        first_page = self.client.get(reverse('accounts:response-pane', args=[account.username]))
        second_page = self.client.get(reverse('accounts:response-pane', args=[account.username]), {'response_page': 2})

        self.assertEqual(len(first_page.context['response_page'].object_list), 10)
        self.assertEqual(len(second_page.context['response_page'].object_list), 1)
        self.assertContains(first_page, 'data-pane-pagination')


class MyPageTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('my_page_user', password='eightchars')

    def test_guest_is_redirected_from_my_page(self):
        response = self.client.get(reverse('mypage'))

        self.assertRedirects(response, reverse('events:map'))

    def test_overview_uses_one_module_entry(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse('mypage'))

        self.assertContains(response, 'id="open-module"', count=1)
        self.assertNotContains(response, 'id="mypage-context"')
        self.assertNotContains(response, '定義: Field')
        self.assertNotContains(response, '定義: Interface')

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
