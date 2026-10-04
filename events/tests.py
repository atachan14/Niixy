from uuid import uuid4
import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Locality, NiiMapFilterPreference, Station, Thread, ThreadAccessRule, ThreadPlacement, ThreadPost
from interfaces.models import FieldType, Interface, InterfaceDraft, InterfaceDraftField, ThreadDirectField
from interfaces.services import publish_draft, publish_field_definition


class ThreadViewTests(TestCase):
    def place_on_map(self, *threads):
        for index, thread in enumerate(threads):
            ThreadPlacement.objects.create(
                thread=thread,
                kind=ThreadPlacement.NII_MAP,
                latitude=f'35.{index + 1:06d}',
                longitude=f'139.{index + 1:06d}',
            )

    def payload(self, **overrides):
        data = {
            'submission_id': str(uuid4()), 'title': '地図上のThread', 'body': '最初の本文',
            'latitude': '35.681236', 'longitude': '139.767125',
        }
        for capability in ('view', 'write'):
            data[f'{capability}_guest'] = 'true'
            data[f'{capability}_account'] = 'true'
        data.update(overrides)
        return data

    def test_guest_creates_thread_opening_post_placement_and_rules(self):
        response = self.client.post(reverse('events:thread-create'), self.payload(), HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        thread = Thread.objects.get()
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(thread.creator)
        self.assertEqual(response.json()['redirect_url'], f"{reverse('events:map')}?thread={thread.pk}")
        self.assertEqual(thread.posts.get().number, 1)
        self.assertEqual(thread.placements.get().kind, ThreadPlacement.NII_MAP)
        self.assertEqual(thread.access_rules.count(), 4)

    def test_duplicate_submission_creates_one_thread(self):
        payload = self.payload()
        self.client.post(reverse('events:thread-create'), payload)
        self.client.post(reverse('events:thread-create'), payload)
        self.assertEqual(Thread.objects.count(), 1)

    def test_thread_creation_saves_interface_implementation(self):
        owner = get_user_model().objects.create_user('interface_owner', password='eightchars')
        definition, _ = publish_field_definition(
            creator=owner,
            name='開始日時',
            field_type=FieldType.DATETIME,
        )
        draft = InterfaceDraft.objects.create(creator=owner, kind=Interface.THREAD, name='Event')
        draft_field = InterfaceDraftField.objects.create(
            draft=draft,
            definition=definition,
            required=True,
            position=0,
        )
        interface, _ = publish_draft(draft.pk)
        payload = self.payload()
        payload['interface_ids'] = str(interface.pk)
        payload[f'interface_value_{interface.pk}_{draft_field.field_key}'] = '2026-10-01T12:00'

        response = self.client.post(reverse('events:thread-create'), payload)

        self.assertEqual(response.status_code, 200)
        implementation = Thread.objects.get().interface_implementations.get()
        self.assertEqual(implementation.interface, interface)
        self.assertEqual(implementation.values.get().value, '2026-10-01T12:00:00')

        detail_response = self.client.get(reverse('events:map'))
        self.assertContains(detail_response, 'Event@interface_owner v1/ThreadIF')
        self.assertContains(detail_response, 'class="thread-post-layout-area"')
        self.assertContains(detail_response, 'class="thread-information-entry thread-interface-entry" open')
        self.assertContains(detail_response, '<summary>ThreadIF</summary>', count=1)
        self.assertContains(detail_response, '開始日時')
        self.assertContains(detail_response, '2026-10-01T12:00:00')

    def test_thread_creation_saves_required_direct_field(self):
        owner = get_user_model().objects.create_user('field_owner', password='eightchars')
        definition, version = publish_field_definition(
            creator=owner,
            name='募集人数',
            field_type=FieldType.INTEGER,
        )
        payload = self.payload(
            direct_field_ids=str(definition.pk),
            **{f'direct_field_value_{definition.key}': '4'},
        )

        response = self.client.post(reverse('events:thread-create'), payload)

        self.assertEqual(response.status_code, 200)
        implementation = ThreadDirectField.objects.select_related('binding__value').get()
        self.assertEqual(implementation.version, version)
        self.assertEqual(implementation.binding.value.value, 4)
        detail_response = self.client.get(reverse('events:map'))
        self.assertContains(detail_response, '<summary>DirectField</summary>')
        self.assertContains(detail_response, '募集人数')

    def test_thread_creation_rejects_empty_direct_field(self):
        owner = get_user_model().objects.create_user('field_owner', password='eightchars')
        definition, _ = publish_field_definition(
            creator=owner,
            name='必須Field',
            field_type=FieldType.SHORT_TEXT,
        )

        response = self.client.post(
            reverse('events:thread-create'),
            self.payload(direct_field_ids=str(definition.pk)),
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Thread.objects.exists())

    def test_thread_detail_always_shows_collapsed_policy_without_empty_response_information(self):
        thread = Thread.objects.create(title='Policy Thread')
        ThreadPost.objects.create(thread=thread, number=1, body='Opening post')
        ThreadPost.objects.create(thread=thread, number=2, body='Response')
        ThreadAccessRule.objects.create(
            thread=thread,
            capability=ThreadAccessRule.VIEW,
            audience=ThreadAccessRule.GUEST,
        )
        self.place_on_map(thread)
        response = self.client.get(reverse('events:map'))

        self.assertContains(response, 'class="thread-information-entry thread-policy-entry"')
        self.assertNotContains(response, 'class="thread-information-entry thread-policy-entry" open')
        self.assertContains(response, '<summary>Policy</summary>')
        self.assertContains(response, 'Guest')
        self.assertContains(response, '許可なし')
        self.assertNotContains(response, 'Response情報')

    def test_thread_detail_links_niimap_placement_coordinates(self):
        thread = Thread.objects.create(title='配置付きThread')
        ThreadPost.objects.create(thread=thread, number=1, body='Opening post')
        ThreadPlacement.objects.create(
            thread=thread,
            latitude='35.681236',
            longitude='139.767125',
        )

        response = self.client.get(reverse('events:map'))

        self.assertContains(response, 'data-thread-placement-link')
        self.assertContains(response, 'data-latitude="35.681236"')
        self.assertContains(response, 'data-longitude="139.767125"')
        self.assertContains(
            response,
            f'href="{reverse("events:map")}?latitude=35.681236&amp;longitude=139.767125&amp;zoom=15"',
        )

    def test_map_exposes_active_thread_interfaces_to_creation_ui(self):
        owner = get_user_model().objects.create_user('catalog_owner', password='eightchars')
        draft = InterfaceDraft.objects.create(creator=owner, kind=Interface.THREAD, name='募集')
        interface, _ = publish_draft(draft.pk)
        self.client.force_login(owner)

        response = self.client.get(reverse('events:map'))

        catalog = response.context['thread_interface_catalog']
        created_catalog = response.context['created_thread_interface_catalog']
        self.assertEqual(catalog[0]['version'], interface.current_version.version_number)
        self.assertEqual(catalog[0]['creator'], owner.username)
        self.assertEqual(catalog[0]['id'], interface.pk)
        self.assertEqual(created_catalog[0]['id'], interface.pk)
        self.assertContains(response, 'data-ui-tab="search"')
        self.assertContains(response, 'data-ui-tab="created"')
        self.assertContains(response, 'data-ui-tab="saved"')
        self.assertContains(response, 'data-select-thread-interface')

    def test_map_exposes_active_fields_to_direct_field_selector(self):
        owner = get_user_model().objects.create_user('catalog_field_owner', password='eightchars')
        definition, _ = publish_field_definition(
            creator=owner,
            name='直接追加Field',
            field_type=FieldType.SHORT_TEXT,
        )
        self.client.force_login(owner)

        response = self.client.get(reverse('events:map'))

        self.assertEqual(response.context['thread_field_catalog'][0]['id'], definition.pk)
        self.assertEqual(response.context['created_thread_field_catalog'][0]['id'], definition.pk)
        self.assertContains(response, 'id="open-direct-field-selector"')
        self.assertContains(response, 'data-select-thread-field')

    def test_guest_can_reply_when_write_rule_allows_it(self):
        thread = Thread.objects.create(title='公開Thread')
        ThreadPost.objects.create(thread=thread, number=1, body='本文')
        for capability in ('view', 'write'):
            ThreadAccessRule.objects.create(thread=thread, capability=capability, audience='guest')
        response = self.client.post(reverse('events:thread-post-create', args=[thread.pk]), {'body': '返信'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['redirect_url'], f"{reverse('events:map')}?thread={thread.pk}")
        self.assertEqual(thread.posts.count(), 2)

    def test_duplicate_reply_submission_creates_one_post(self):
        thread = Thread.objects.create(title='公開Thread')
        ThreadPost.objects.create(thread=thread, number=1, body='本文')
        for capability in ('view', 'write'):
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

    def test_map_lists_threads_even_when_they_are_not_viewable(self):
        public = Thread.objects.create(title='公開Thread')
        hidden = Thread.objects.create(title='非公開Thread')
        ThreadAccessRule.objects.create(thread=public, capability='view', audience='guest')
        ThreadPlacement.objects.create(thread=public, latitude='35.6', longitude='139.7')
        ThreadPlacement.objects.create(thread=hidden, latitude='35.6', longitude='139.7')
        response = self.client.get(reverse('events:map'))
        self.assertContains(response, '公開Thread')
        self.assertContains(response, '非公開Thread')
        self.assertContains(response, 'このThreadは閲覧できません。')

    def test_map_and_search_exclude_unplaced_threads(self):
        placed = Thread.objects.create(title='配置済みThread')
        unplaced = Thread.objects.create(title='未配置Thread')
        self.place_on_map(placed)
        for thread in (placed, unplaced):
            ThreadAccessRule.objects.create(thread=thread, capability='view', audience='guest')

        map_response = self.client.get(reverse('events:map'))
        search_response = self.client.post(reverse('events:thread-search'), self.search_payload())

        self.assertContains(map_response, '配置済みThread')
        self.assertNotContains(map_response, '未配置Thread')
        self.assertEqual(search_response.json()['thread_ids'], [placed.pk])

    def test_map_uses_list_controls_and_opens_thread_creation_in_detail_pane(self):
        response = self.client.get(reverse('events:map'))

        content = response.content.decode()
        list_start = content.index('<aside class="thread-list-pane"')
        detail_start = content.index('class="ui-detail-pane thread-detail-pane"')
        form_start = content.index('id="thread-create-form"')
        self.assertGreater(form_start, list_start)
        self.assertGreater(form_start, detail_start)
        self.assertNotContains(response, 'id="thread-create-detail"')
        self.assertContains(response, '>Spot一覧<')
        self.assertContains(response, 'id="niimap-control-windows"')
        self.assertContains(response, 'id="niimap-create-toggle"')
        self.assertContains(response, 'id="niimap-search-toggle"')
        self.assertContains(response, 'id="niimap-search-controls"')
        self.assertContains(response, 'class="ui-accordion-content niimap-control-window', count=2)
        self.assertContains(response, '<option value="near">近い順</option><option value="updated">新しい順</option><option value="field">Field</option>')
        self.assertContains(response, 'data-search-select="sort-field" disabled')
        self.assertContains(response, 'name="sort_direction" aria-label="Fieldの並び順" disabled')
        self.assertContains(response, 'class="niimap-search-section"', count=4)
        self.assertContains(response, 'id="account-condition-pane"')
        self.assertContains(response, 'id="account-condition-group-toggle"')
        self.assertContains(response, 'id="account-selector-template"')
        self.assertContains(response, 'data-account-condition-kind="default"')
        self.assertContains(response, 'data-account-condition-kind="account_interface"')
        self.assertContains(response, 'data-account-condition-kind="field"')
        self.assertNotContains(response, 'id="account-condition-kind"')
        self.assertContains(response, 'data-policy-capability="view"', count=2)
        self.assertContains(response, 'data-policy-capability="write"', count=2)
        self.assertContains(response, '>閲覧可能<')
        self.assertContains(response, '>閲覧不可<')
        self.assertContains(response, '>書き込み可能<')
        self.assertContains(response, '>書き込み不可<')
        self.assertNotContains(response, 'data-add-search-condition="policy"')
        self.assertContains(response, 'id="niimap-create-controls"')
        self.assertContains(response, 'class="button secondary is-unavailable"', count=3)
        self.assertContains(response, 'id="open-thread-create" class="button primary"')
        self.assertContains(response, 'id="open-room-create" class="button primary"')
        self.assertContains(response, 'title="未対応"', count=3)
        self.assertContains(response, 'aria-label="Board（未対応）"')
        self.assertContains(response, 'aria-label="Tweet（未対応）"')
        self.assertContains(response, 'aria-label="Timeline（未対応）"')
        self.assertContains(response, 'id="thread-create-placement-link"')
        self.assertContains(response, '<summary>Policy</summary>')
        self.assertNotContains(response, '<summary>制限</summary>')
        self.assertContains(response, 'id="open-direct-field-selector" class="button secondary"')
        self.assertContains(response, 'id="open-thread-interface-selector" class="button secondary"')
        self.assertNotContains(response, 'id="thread-location-status"')
        self.assertContains(response, 'data-pending-label="検索中..."')
        self.assertContains(response, 'data-pending-label="作成中..."', count=3)
        self.assertContains(response, 'data-pending-label="ログイン中..."')
        self.assertContains(response, 'function beginPendingAction')
        self.assertContains(response, 'function setAccordionExpanded')
        self.assertNotContains(response, 'id="thread-search-trigger"')
        self.assertNotContains(response, 'id="thread-create-trigger"')
        self.assertNotContains(response, '<summary>新規作成</summary>')
        self.assertNotContains(response, '<summary>検索</summary>')
        search_toggle = content.index('id="niimap-search-toggle"')
        create_toggle = content.index('id="niimap-create-toggle"')
        create_controls = content.index('id="niimap-create-controls"')
        search_controls = content.index('id="niimap-search-controls"')
        thread_list = content.index('id="thread-list"')
        self.assertLess(search_toggle, create_toggle)
        self.assertLess(search_controls, create_controls)
        self.assertLess(create_controls, thread_list)
        self.assertContains(response, 'map.js?v=20261004-27')
        self.assertNotContains(response, 'class="map-filter"')
        self.assertContains(response, 'niixy:resume:niimap')
        self.assertNotContains(response, 'niimap:open-thread')

    def search_payload(self, **overrides):
        data = {
            'sort_kind': 'updated',
            'sort_direction': 'desc',
            'target_type': 'all',
            'creator_include_groups': '[]',
            'creator_exclude_groups': '[]',
            'policy_conditions': '[]',
            'field_conditions': '[]',
            'interface_conditions': '[]',
        }
        data.update(overrides)
        return data

    def test_thread_search_uses_effective_view_policy(self):
        public = Thread.objects.create(title='公開')
        hidden = Thread.objects.create(title='非公開')
        self.place_on_map(public, hidden)
        ThreadAccessRule.objects.create(thread=public, capability='view', audience='guest')

        response = self.client.post(reverse('events:thread-search'), self.search_payload(
            policy_conditions=json.dumps([{'capability': 'view', 'decision': 'allow', 'actor': 'self'}]),
        ))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['thread_ids'], [public.pk])
        self.assertNotIn(hidden.pk, response.json()['thread_ids'])

    def test_thread_search_saves_conditions_for_logged_in_account(self):
        user = get_user_model().objects.create_user('search_owner', password='eightchars')
        self.client.force_login(user)
        creator_groups = [[{'kind': 'default', 'definition': {'code': 'self'}, 'label': '@search_owner'}]]
        policy = [{'capability': 'view', 'decision': 'allow', 'actor': 'self'}]

        response = self.client.post(reverse('events:thread-search'), self.search_payload(
            sort_direction='asc',
            freeword_include='保存する語',
            creator_include_groups=json.dumps(creator_groups),
            policy_conditions=json.dumps(policy),
        ))

        self.assertEqual(response.status_code, 200)
        state = user.niimap_filter_preference.search_state
        self.assertEqual(state['sort_direction'], 'asc')
        self.assertEqual(state['freeword_include'], '保存する語')
        self.assertEqual(state['conditions']['creator_include_groups'], creator_groups)
        self.assertEqual(state['conditions']['policy'], policy)

    def test_thread_search_does_not_save_guest_conditions(self):
        response = self.client.post(reverse('events:thread-search'), self.search_payload(
            freeword_include='Guestの条件',
        ))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(NiiMapFilterPreference.objects.exists())

    def test_thread_search_treats_account_groups_as_outer_or_and_inner_and(self):
        owner = get_user_model().objects.create_user('group_owner', password='eightchars')
        other = get_user_model().objects.create_user('group_other', password='eightchars')
        owner_thread = Thread.objects.create(creator=owner, title='本人')
        other_thread = Thread.objects.create(creator=other, title='他人')
        guest_thread = Thread.objects.create(title='Guest')
        self.place_on_map(owner_thread, other_thread, guest_thread)
        for thread in (owner_thread, other_thread, guest_thread):
            ThreadAccessRule.objects.create(thread=thread, capability='view', audience='guest')
        self.client.force_login(owner)
        account = lambda account_id: {'kind': 'account', 'definition': {'account_id': account_id}, 'label': 'Account'}
        default = lambda code: {'kind': 'default', 'definition': {'code': code}, 'label': code}

        response = self.client.post(reverse('events:thread-search'), self.search_payload(
            creator_include_groups=json.dumps([
                [default('self'), default('account')],
                [default('guest')],
            ]),
            creator_exclude_groups=json.dumps([[account(other.pk)]]),
        ))

        self.assertEqual(response.status_code, 200)
        self.assertCountEqual(response.json()['thread_ids'], [owner_thread.pk, guest_thread.pk])

    def test_thread_search_policy_accepts_account_condition_groups(self):
        public = Thread.objects.create(title='公開')
        account_only = Thread.objects.create(title='Account限定')
        self.place_on_map(public, account_only)
        ThreadAccessRule.objects.create(thread=public, capability='view', audience='guest')
        ThreadAccessRule.objects.create(thread=account_only, capability='view', audience='account')

        response = self.client.post(reverse('events:thread-search'), self.search_payload(
            policy_conditions=json.dumps([{
                'capability': 'view',
                'decision': 'allow',
                'account_groups': [[{'kind': 'default', 'definition': {'code': 'guest'}, 'label': 'Guest'}]],
            }]),
        ))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['thread_ids'], [public.pk])

    def test_thread_search_does_not_match_hidden_post_body(self):
        hidden = Thread.objects.create(title='通常タイトル')
        self.place_on_map(hidden)
        ThreadPost.objects.create(thread=hidden, number=1, body='秘密の検索語')

        response = self.client.post(reverse('events:thread-search'), self.search_payload(
            freeword_include='秘密の検索語',
        ))

        self.assertEqual(response.json()['thread_ids'], [])

    def test_thread_search_filters_by_field_and_interface(self):
        owner = get_user_model().objects.create_user('module_owner', password='eightchars')
        definition, _ = publish_field_definition(creator=owner, name='人数', field_type=FieldType.INTEGER)
        draft = InterfaceDraft.objects.create(creator=owner, kind=Interface.THREAD, name='募集')
        InterfaceDraftField.objects.create(draft=draft, definition=definition, required=True, position=0)
        interface, _ = publish_draft(draft.pk)
        payload = self.payload(
            direct_field_ids=str(definition.pk),
            interface_ids=str(interface.pk),
            **{
                f'direct_field_value_{definition.key}': '4',
                f'interface_value_{interface.pk}_{definition.key}': '4',
            },
        )
        self.client.post(reverse('events:thread-create'), payload)
        matching = Thread.objects.get()
        other = Thread.objects.create(title='別Thread')
        ThreadAccessRule.objects.create(thread=other, capability='view', audience='guest')

        response = self.client.post(reverse('events:thread-search'), self.search_payload(
            field_conditions=json.dumps([{'field_id': definition.pk, 'operator': 'gte', 'value': '4'}]),
            interface_conditions=json.dumps([{'interface_id': interface.pk, 'operator': 'include'}]),
        ))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['thread_ids'], [matching.pk])

    def test_location_search_includes_stations_and_localities(self):
        Station.objects.create(station_code='s1', group_code='g1', name='Test Station', line_name='Line', operator_name='Rail', latitude=35, longitude=139)
        Locality.objects.create(source_key='l1', name='Test Town', full_name='Test Prefecture Test Town', detail='Test Prefecture', kind='town', latitude=35, longitude=139)
        response = self.client.get(reverse('events:location-search'), {'q': 'Test'})
        self.assertEqual({item['name'] for item in response.json()['locations']}, {'Test Station', 'Test Town'})
