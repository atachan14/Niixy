import copy
import json

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .models import AccountLayoutDraft, AccountLayoutApplication, InterfaceDraft, InterfaceDraftField, AccountFieldValue
from .services import publish_field_definition, publish_draft
from .account_applications import change_application, MergeConfirmationRequired
from . import account_layouts as layouts
from .layout_renderer import html_fragment, stylesheet, render_document


class AccountLayoutTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user('layout_owner')
        self.other = get_user_model().objects.create_user('layout_other')
        self.field, _ = publish_field_definition(creator=self.owner, name='血液型', field_type='short_text')
        draft = InterfaceDraft.objects.create(creator=self.owner, name='プロフィールIF', kind='account')
        InterfaceDraftField.objects.create(draft=draft, definition=self.field, required=True, position=0)
        self.interface, _ = publish_draft(draft.pk)
        self.payload = {'name': 'My Profile', 'description': '', 'html': '<section class="card"><strong>{{blood.name}}</strong><p>{{blood.value}}</p></section>',
            'css': '.card {display:grid; gap:12px; padding:16px; background-color:#f2f4fa; border-radius:12px;} @media (max-width:600px) {.card {display:flex;flex-direction:column;}}',
            'requirements': {'fields': [], 'interfaces': [self.interface.pk]}, 'items': [{'alias': 'blood', 'field_id': self.field.pk}]}

    def publish(self, payload=None):
        payload = payload or self.payload
        draft = AccountLayoutDraft.objects.create(creator=self.owner)
        token = layouts.preview(self.owner, payload)['token']
        return layouts.save_draft(self.owner, draft.pk, payload, publish=True, token=token)

    def change(self, payload):
        try:
            change_application(self.owner, payload)
        except MergeConfirmationRequired as error:
            change_application(self.owner, payload, error.token)

    def apply_if(self, value='A'):
        self.change({'operation': 'add_interface', 'id': self.interface.pk, 'values': {str(self.field.key): [value]}})

    def test_if_require_supplies_field_item_but_field_only_cannot_replace_if(self):
        version = self.publish()
        self.change({'operation': 'add_field', 'id': self.field.pk, 'values': {str(self.field.key): ['B']}})
        with self.assertRaisesMessage(ValidationError, '必要Mod'):
            layouts.apply_layout(self.owner, version.layout_id)
        self.apply_if('B')
        layouts.apply_layout(self.owner, version.layout_id)
        self.assertEqual(self.owner.layout_application.version_id, version.pk)
        self.assertEqual(version.require_fields.count(), 0)
        self.assertEqual(version.items.first().field_version_id, self.field.current_version_id)

    def test_publication_is_immutable_and_apply_switch_preserves_mods_values(self):
        one = self.publish(); self.apply_if(); layouts.apply_layout(self.owner, one.layout_id)
        before = list(AccountFieldValue.objects.values_list('pk', 'value', 'updated_at'))
        with self.assertRaises(ValidationError):
            one.name = 'overwrite'; one.save()
        draft = layouts.edit_draft(self.owner, one.layout_id)
        payload = layouts.draft_payload(draft); payload['html'] += '<p>new</p>'
        two = layouts.save_draft(self.owner, draft.pk, payload, publish=True, token=layouts.preview(self.owner, payload)['token'])
        self.assertEqual(self.owner.layout_application.version_id, one.pk)
        layouts.apply_layout(self.owner, two.layout_id)
        self.assertEqual(AccountLayoutApplication.objects.get(account=self.owner).version_id, two.pk)
        AccountLayoutApplication.objects.filter(account=self.owner).delete()
        self.assertEqual(list(AccountFieldValue.objects.values_list('pk', 'value', 'updated_at')), before)
        self.assertEqual(self.owner.interface_implementations.count(), 1)

    def test_frozen_dependencies_keep_display_current_values_without_blocking_updates(self):
        one = self.publish(); self.apply_if(); layouts.apply_layout(self.owner, one.layout_id)
        with self.assertRaisesMessage(ValidationError, 'Layout'):
            change_application(self.owner, {'operation': 'remove_interface', 'id': self.owner.interface_implementations.get().pk})
        publish_field_definition(creator=self.owner, definition=self.field, name='Blood label v2', field_type='short_text')
        self.field.refresh_from_db()
        binding = self.owner.field_bindings.get()
        self.change({'operation': 'edit_value', 'id': binding.pk, 'values': ['updated <script>secret</script>']})
        context = layouts.profile_context(self.owner)
        self.assertTrue(context['account_layout_frozen'])
        self.assertIn('血液型', context['account_layout_document'])
        self.assertIn('updated &lt;script&gt;secret&lt;/script&gt;', context['account_layout_document'])
        self.assertEqual(self.owner.field_bindings.get().version_id, self.field.current_version_id)
        self.assertEqual(self.owner.layout_application.version_id, one.pk)
        # Repairing the IF follows its existing recovery boundary, with no missingField added.
        draft = InterfaceDraft.objects.create(creator=self.owner, interface=self.interface, kind='account', name=self.interface.name)
        InterfaceDraftField.objects.create(draft=draft, definition=self.field, required=True, position=0)
        publish_draft(draft.pk)
        self.assertEqual(self.owner.interface_implementations.get().state, 'active')
        self.assertIn('updated &lt;script&gt;', layouts.profile_context(self.owner)['account_layout_document'])

    def test_latest_dependencies_at_publish_and_stale_preview_rejected(self):
        payload = copy.deepcopy(self.payload); payload['requirements'] = {'fields': [self.field.pk], 'interfaces': []}
        draft = AccountLayoutDraft.objects.create(creator=self.owner)
        token = layouts.preview(self.owner, payload)['token']
        publish_field_definition(creator=self.owner, definition=self.field, name='New label', field_type='short_text')
        with self.assertRaisesMessage(ValidationError, '変わりました'):
            layouts.save_draft(self.owner, draft.pk, payload, publish=True, token=token)
        fresh = layouts.preview(self.owner, payload)['token']
        version = layouts.save_draft(self.owner, draft.pk, payload, publish=True, token=fresh)
        self.field.refresh_from_db()
        self.assertEqual(version.items.get().field_version_id, self.field.current_version_id)

    def test_preview_uses_own_values_and_never_persists_sample(self):
        before = AccountFieldValue.objects.count()
        self.assertIn('サンプル値', layouts.preview(self.owner, self.payload)['document'])
        self.assertEqual(AccountFieldValue.objects.count(), before)
        self.apply_if('<img src=x onerror=alert(1)>')
        output = layouts.preview(self.owner, self.payload)['document']
        self.assertIn('&lt;img', output); self.assertNotIn('<img', output)
        self.assertIn('サンプル値', layouts.preview(self.other, self.payload)['document'])

    def test_invalid_aliases_items_and_unknown_bindings(self):
        for items in [[{'alias': 'blood', 'field_id': self.field.pk}]*2, [{'alias': '9bad', 'field_id': self.field.pk}], [{'alias': 'blood', 'field_id': 99999}]]:
            with self.subTest(items=items), self.assertRaises(ValidationError):
                payload = copy.deepcopy(self.payload); payload['items'] = items; layouts.prepare(payload)
        for html in ['{{unknown.name}}', '{{blood.__class__}}', '{{ blood.value|safe }}', '{% include "secret" %}', '{{blood.value + 1}}', '<div title="{{blood.value}}"></div>']:
            with self.subTest(html=html), self.assertRaises(ValidationError):
                payload = copy.deepcopy(self.payload); payload['html'] = html; layouts.prepare(payload)

    def test_owner_authorization_csrf_and_guest_read_only(self):
        version = self.publish(); draft = layouts.edit_draft(self.owner, version.layout_id)
        save_url = reverse('interfaces:layout-draft-save', args=[draft.pk])
        apply_url = reverse('accounts:layout-change', args=[self.owner.username])
        self.assertEqual(self.client.post(save_url, '{}', content_type='application/json').status_code, 401)
        self.assertEqual(self.client.get(reverse('interfaces:layout-detail', args=[version.layout_id])).status_code, 200)
        self.assertEqual(self.client.get(reverse('accounts:detail', args=[self.owner.username])).status_code, 200)
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(save_url, '{}', content_type='application/json').status_code, 404)
        self.assertEqual(self.client.post(apply_url, json.dumps({'operation': 'apply', 'id': version.layout_id}), content_type='application/json').status_code, 403)
        self.assertFalse(AccountLayoutApplication.objects.exists())
        from django.test import Client
        csrf = Client(enforce_csrf_checks=True); csrf.force_login(self.owner)
        self.assertEqual(csrf.post(apply_url, '{}', content_type='application/json').status_code, 403)

    def test_direct_preview_rejects_malicious_input_and_stale_apply_version(self):
        version = self.publish(); self.apply_if()
        draft = layouts.edit_draft(self.owner, version.layout_id)
        self.client.force_login(self.owner)
        payload = copy.deepcopy(self.payload); payload['css'] = '.card{background-image:url(https://example.invalid/x)}'
        response = self.client.post(reverse('interfaces:layout-draft-save', args=[draft.pk]), json.dumps({'operation': 'preview', 'layout': payload}), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json())
        self.assertEqual(AccountLayoutApplication.objects.count(), 0)
        response = self.client.post(reverse('accounts:layout-change', args=[self.owner.username]), json.dumps({'operation': 'apply', 'id': version.layout_id, 'version': version.pk + 999}), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('公開版が変わりました', response.json()['error'])
        self.assertNotContains(self.client.get(reverse('interfaces:layout-detail', args=[version.layout_id])), 'data-layout-apply')

    def test_field_requirement_can_use_if_binding_and_last_reference_removal_is_blocked(self):
        payload = copy.deepcopy(self.payload); payload['requirements'] = {'fields': [self.field.pk], 'interfaces': []}
        version = self.publish(payload); self.apply_if(); layouts.apply_layout(self.owner, version.layout_id)
        implementation = self.owner.interface_implementations.get()
        with self.assertRaisesMessage(ValidationError, 'Layout'):
            change_application(self.owner, {'operation': 'remove_interface', 'id': implementation.pk})
        self.change({'operation': 'add_field', 'id': self.field.pk, 'values': {}})
        change_application(self.owner, {'operation': 'remove_interface', 'id': implementation.pk})
        self.assertIn('A', layouts.profile_context(self.owner)['account_layout_document'])
        with self.assertRaisesMessage(ValidationError, 'Layout'):
            change_application(self.owner, {'operation': 'remove_field', 'id': self.owner.direct_fields.get().pk})


class LayoutRendererSecurityTests(TestCase):
    def test_rejects_active_html_and_bad_structure(self):
        bad = ['<script>alert(1)</script>', '<img src="https://x">', '<svg><script /></svg>', '<iframe srcdoc="x"></iframe>',
            '<form><input></form>', '<a href="javascript:alert(1)">x</a>', '<embed>', '<object></object>',
            '<div onclick="x"></div>', '<div style="position:fixed"></div>', '<div id="outer"></div>',
            '<meta http-equiv="refresh">', '<base href="https://x">', '<div></span>', '<div>',
            '<div class="a" class="b"></div>', '<!--x-->', '<!doctype html>', '<div class=', '<div>'*21 + '</div>'*21, '<br>'*301]
        for source in bad:
            with self.subTest(source=source[:80]), self.assertRaises(ValidationError):
                html_fragment(source, set())
        with self.assertRaises(ValidationError): html_fragment('x'*20001, set())

    def test_rejects_network_overlay_selector_and_nested_rule_attacks(self):
        bad = ['@import "https://x";', '@font-face{font-family:x;src:url(https://x)}',
            '.card{background-image:url(https://x)}', '.card{color:var(--secret)}', '.card{color:expression(alert(1))}',
            '.card{position:fixed}', '.card{position:absolute}', '.card{transform:scale(2)}', '.card{z-index:9999}',
            '.card{margin:-10px}', '.card{width:999999px}', '.card{width:100vw}', '.card{color:red!important}',
            '.card{--x:url(https://x)}', 'body{color:red}', ':root{color:red}', '.card:has(p){color:red}',
            '[class]{color:red}', '.card~p{color:red}', '#outer{color:red}', '.card{nested{color:red}}',
            '@supports(display:grid){.card{color:red}}', '@media print{.card{color:red}}',
            '.card{color:red; /* comment */}', '.card{color:rgb(url(x))}', '.card{padding:calc(100vw)}',
            '.card{grid-template-columns:repeat(99999,1fr)}', '.card{color:}', '.card {color:red; broken}',
            '.card{background-color:r\\65 d;position:f\\69 xed}', '.card{color:red', '.card{color:rgb(1,2,3}',
            '@media(max-width:600px){'*4 + '.card{color:red}' + '}'*4]
        for source in bad:
            with self.subTest(source=source), self.assertRaises(ValidationError): stylesheet(source)
        with self.assertRaises(ValidationError): stylesheet(' '*10001)

    def test_supported_language_and_inert_document(self):
        html = '<div class="card"><p>{{x.name}}</p><span>{{x.value}}</span></div>'
        css = '.card{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;color:rgb(10,20,30);border-color:#ddd;border-style:solid;border-width:1px;} @media(max-width:600px){.card{grid-template-columns:1fr;}}'
        document = render_document(html, css, {'x'}, {'x': {'name': '<name>', 'value': '</style><script>alert(1)</script>'}})
        self.assertIn('&lt;name&gt;', document)
        self.assertNotIn('<script>', document)
        self.assertIn('contain:layout style paint', document)
        self.assertIn('data-account-layout-surface', document)
        self.assertNotIn('<iframe', document)
        self.assertNotIn('src=', document)
        self.assertRegex(document, r'\.niixy-layout-[a-f0-9]+ \.card\{')
