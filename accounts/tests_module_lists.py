"""Latest Board/Module collection correction; isolated SQLite only."""
from uuid import uuid4
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, Client
from django.urls import reverse

from accounts.content_lists import KINDS, route
from accounts.models import AccountMute
from interfaces.models import (Interface, InterfaceDraft, InterfaceList, InterfaceListReference,
    FieldDefinition, AccountLayout, AccountLayoutDraft, AccountLayoutVersion)
from interfaces.services import publish_draft, publish_field_definition
from rooms.models import BoardPlacement


def seed(case):
    case.assertEqual(settings.DATABASES['default']['ENGINE'], 'django.db.backends.sqlite3')
    case.owner = get_user_model().objects.create_user('module_owner')
    case.other = get_user_model().objects.create_user('module_other')
    case.field, _ = publish_field_definition(creator=case.other, name='Public Field', field_type='short_text')
    case.own_field, _ = publish_field_definition(creator=case.owner, name='Own Field', field_type='short_text')
    case.interfaces = []
    for kind in ['account', 'room', 'thread', 'thread_post']:
        item, _ = publish_draft(InterfaceDraft.objects.create(creator=case.other, kind=kind, name='Public ' + kind + ' IF').pk)
        case.interfaces.append(item)
    case.interface = case.interfaces[2]
    case.layout = AccountLayout.objects.create(creator=case.other, name='Public Layout')
    version = AccountLayoutVersion.objects.create(layout=case.layout, version_number=1, name=case.layout.name, html='<p>PUBLIC LAYOUT</p>')
    case.layout.current_version=version; case.layout.save()
    case.own_layout = AccountLayout.objects.create(creator=case.owner, name='Own Layout')
    version = AccountLayoutVersion.objects.create(layout=case.own_layout, version_number=1, name=case.own_layout.name)
    case.own_layout.current_version=version; case.own_layout.save()
    case.content_list = InterfaceList.objects.create(owner=case.owner, name='Mixed List A', submission_id=uuid4())
    case.second_list = InterfaceList.objects.create(owner=case.owner, name='Mixed List B', submission_id=uuid4())
    for kind, target in [('field',case.field),('layout',case.layout),('interface',case.interface)]:
        KINDS[kind].reference.objects.create(interface_list=case.content_list,target=target)
        KINDS[kind].rating.objects.create(author=case.owner,target=target,sentiment='fav')
    InterfaceDraft.objects.create(creator=case.other, interface=case.interface, name='PRIVATE IF DRAFT', description='PRIVATE IF BODY')
    AccountLayoutDraft.objects.create(creator=case.other, layout=case.layout, name='PRIVATE LAYOUT DRAFT', html='PRIVATE LAYOUT BODY')
    case.client.force_login(case.owner)


class ModuleListTests(TestCase):
    def setUp(self): seed(self)

    def entries(self):
        return [('field',self.field),('layout',self.layout)] + [('interface',i) for i in self.interfaces]

    def test_exclusive_rating_all_real_modules_and_public_author_list(self):
        for kind, target in self.entries():
            with self.subTest(kind=kind,target=target.pk):
                for sentiment in ['fav','bad','bad','']:
                    response=self.client.post(route(kind,'rating',target.pk),{'sentiment':sentiment,'author':self.other.pk})
                    self.assertEqual(response.status_code,200)
                    rows=KINDS[kind].rating.objects.filter(target=target,author=self.owner)
                    self.assertEqual(rows.count(),bool(sentiment))
                    self.assertEqual(response.json()['sentiment'],sentiment)
                self.client.post(route(kind,'rating',target.pk),{'sentiment':'fav'})
                self.client.logout()
                response=self.client.get(route(kind,'ratings',target.pk))
                self.assertContains(response,self.owner.username)
                self.assertEqual(self.client.post(route(kind,'rating',target.pk),{'sentiment':'bad'}).status_code,401)
                self.client.force_login(self.owner)
                self.assertEqual(self.client.post(route(kind,'rating',target.pk),{'sentiment':'love'}).status_code,400)
                model=KINDS[kind].rating
                with self.assertRaises(IntegrityError),transaction.atomic():
                    model.objects.create(author=self.owner,target=target,sentiment='bad')
                with self.assertRaises(IntegrityError),transaction.atomic():
                    model.objects.create(author=self.other,target=target,sentiment='no')

    def test_mixed_list_preserves_old_reference_url_and_typed_removal(self):
        before=list(BoardPlacement.objects.order_by('pk').values())
        legacy=self.content_list.references.get()
        for kind,target in self.entries():
            for _ in range(2):
                self.assertEqual(self.client.post(route('interface','list-add',self.content_list.pk),{'target_url':route(kind,'page',target.pk)}).status_code,200)
            self.assertEqual(KINDS[kind].reference.objects.filter(interface_list=self.content_list,target=target).count(),1)
        response=self.client.get(route('interface','list-detail',self.content_list.pk))
        self.assertContains(response,'Public Field');self.assertContains(response,'Public Layout');self.assertContains(response,self.interface.name)
        for kind,target in [('field',self.field),('layout',self.layout)]:
            ref=KINDS[kind].reference.objects.get(interface_list=self.content_list,target=target)
            self.client.post(route(kind,'list-remove',self.content_list.pk,ref.pk))
        self.assertTrue(InterfaceListReference.objects.filter(pk=legacy.pk,target=self.interface).exists())
        self.assertEqual(route('interface','list-page',self.content_list.pk),'/interface-lists/'+str(self.content_list.pk)+'/')
        self.assertEqual(list(BoardPlacement.objects.order_by('pk').values()),before)

    def test_classification_filter_and_tab_order(self):
        page=self.client.get(reverse('accounts:detail',args=[self.owner.username]))
        self.assertNotContains(page,'>BoardList</button>');self.assertNotContains(page,'>InterfaceList</button>')
        response=self.client.get(reverse('accounts:module-pane',args=[self.owner.username]))
        keys=[g['key'] for g in response.context['module_collections']]
        self.assertEqual(keys,['self','fav','bad','list-'+str(self.content_list.pk),'list-'+str(self.second_list.pk)])
        self.assertNotContains(response,'data-module-collection="saved"');self.assertNotContains(response,'data-module-collection="search"')
        for kind in ['element','interface','layout']: self.assertContains(response,'data-module-type="'+kind+'"')
        for subtype in ['field','computed_field','action','account','thread','thread_post','room']:
            self.assertContains(response,'data-module-subtype="'+subtype+'"')
        for type_,subtype,name in [('element','field',self.field.name),('interface','thread',self.interface.name),('layout','account',self.layout.name)]:
            filtered=self.client.get(route('interface','list-detail',self.content_list.pk),{'type':type_,'subtype':subtype})
            self.assertEqual(len(filtered.context['summary_page']),1)
            self.assertContains(filtered,name)
        filtered=self.client.get(route('interface','list-detail',self.content_list.pk),{'type':'element','subtype':'action'})
        self.assertEqual(len(filtered.context['summary_page']),0)
        board=self.client.get(reverse('accounts:boards',args=[self.owner.username]))
        html=board.content.decode()
        self.assertLess(html.index('data-ui-tab="self"'),html.index('data-ui-tab="fav"'))
        self.assertLess(html.index('data-ui-tab="fav"'),html.index('data-ui-tab="bad"'))
        self.assertLess(html.index('data-ui-tab="bad"'),html.index('data-collection-id='))
        tabs=[c.name for c in board.context['collections']];self.assertEqual(tabs[-1],'未分類')

    def test_owner_authorization_guest_reads_and_gets_do_not_write(self):
        for kind,target in self.entries():
            self.assertEqual(self.client.get(route(kind,'picker',target.pk)).status_code,200)
        before={model:list(model.objects.order_by('pk').values()) for model in [InterfaceList,InterfaceListReference,FieldDefinition,AccountLayout,BoardPlacement]}
        self.client.logout()
        for url in [reverse('accounts:module-pane',args=[self.owner.username]),route('interface','list-page',self.content_list.pk),route('interface','list-detail',self.content_list.pk)]+[route(k,'page',t.pk) for k,t in self.entries()]:
            r=self.client.get(url);self.assertEqual(r.status_code,200)
            self.assertNotContains(r,'PRIVATE');self.assertNotContains(r,'data-account-list-form')
            if b'data-content-rate="fav"' in r.content: self.assertContains(r,'data-content-rate="fav" aria-pressed="false" disabled')
        for model,rows in before.items(): self.assertEqual(list(model.objects.order_by('pk').values()),rows)
        self.assertEqual(self.client.post(route('interface','list-add',self.content_list.pk),{'target_url':route('field','page',self.field.pk)}).status_code,401)
        self.client.force_login(self.other)
        for action,data in [('list-add',{'target_url':route('field','page',self.field.pk)}),('list-rename',{'name':'Stolen'}),('list-delete',{})]:
            self.assertEqual(self.client.post(route('interface',action,self.content_list.pk),data).status_code,404)
        ref=self.content_list.field_references.get()
        self.assertEqual(self.client.post(route('field','list-remove',self.content_list.pk,ref.pk)).status_code,404)
        self.client.force_login(self.owner)
        self.assertEqual(Client(enforce_csrf_checks=True).post(route('field','rating',self.field.pk),{'sentiment':'fav'}).status_code,403)
        token=uuid4();data={'name':'New Module List','submission_id':token,'target_url':route('field','page',self.field.pk)}
        first=self.client.post(route('interface','list-create'),data);second=self.client.post(route('interface','list-create'),data)
        self.assertEqual((first.status_code,second.status_code),(201,200));self.assertEqual(first.json()['list_id'],second.json()['list_id'])
        self.assertEqual(self.client.post(route('interface','list-rename',self.content_list.pk),{'name':'Renamed'}).status_code,200)
        self.assertEqual(self.client.post(route('interface','list-delete',self.content_list.pk)).status_code,200)
        self.assertTrue(FieldDefinition.objects.filter(pk=self.field.pk).exists());self.assertTrue(AccountLayout.objects.filter(pk=self.layout.pk).exists())

    def test_unpublished_deleted_and_invalid_publication_pointer_cannot_leak(self):
        private=[('field',FieldDefinition.objects.create(creator=self.other,name='PRIVATE FIELD')),
                 ('interface',Interface.objects.create(creator=self.other,kind='account',name='PRIVATE INTERFACE')),
                 ('layout',AccountLayout.objects.create(creator=self.other,name='PRIVATE LAYOUT'))]
        for kind,target in private:
            KINDS[kind].reference.objects.create(interface_list=self.content_list,target=target)
            KINDS[kind].rating.objects.create(author=self.owner,target=target,sentiment='fav')
            for action in ['page','pane','ratings','picker']:
                self.assertEqual(self.client.get(route(kind,action,target.pk)).status_code,404)
            self.assertEqual(self.client.post(route(kind,'rating',target.pk),{'sentiment':'bad'}).status_code,404)
            self.assertEqual(self.client.post(route('interface','list-add',self.content_list.pk),{'target_url':route(kind,'page',target.pk)}).status_code,400)
        for kind,target in [('field',self.field),('interface',self.interface)]:
            target.status='deleted';target.save()
            self.assertEqual(self.client.get(route(kind,'pane',target.pk)).status_code,404)
        for kind,target in [('layout',self.layout),('field',self.own_field)]:
            other=private[2][1] if kind=='layout' else private[0][1]
            other.current_version=target.current_version;other.save()
            self.assertEqual(self.client.get(route(kind,'page',other.pk)).status_code,404)
        for url in [reverse('accounts:module-pane',args=[self.owner.username]),reverse('accounts:module-pane',args=[self.other.username]),route('interface','list-detail',self.content_list.pk)]:
            self.assertNotContains(self.client.get(url),'PRIVATE')
        AccountMute.objects.create(muter=self.owner,muted_account=self.other)
        self.assertNotContains(self.client.get(route('interface','list-detail',self.content_list.pk)),self.layout.name)
        self.assertEqual(self.content_list.layout_references.count(),2)


class ModuleListMigrationTests(TransactionTestCase):
    def test_only_adds_four_tables_preserving_all_previous_rows_and_schema(self):
        executor=MigrationExecutor(connection);latest=executor.loader.graph.leaf_nodes()
        old=[n for n in latest if n[0]!='interfaces']+[('interfaces','0010_content_lists')]
        try:
            executor.migrate(old);apps=executor.loader.project_state(old).apps
            owner=apps.get_model('auth','User').objects.create(username='legacy_module_owner')
            model=apps.get_model('interfaces','Interface');item=model.objects.create(creator=owner,name='Legacy IF',kind='thread')
            version=apps.get_model('interfaces','InterfaceVersion').objects.create(interface=item,version_number=1,name='Legacy Published IF')
            item.current_version=version;item.save()
            li=apps.get_model('interfaces','InterfaceList').objects.create(owner=owner,name='Legacy List',submission_id=uuid4())
            apps.get_model('interfaces','InterfaceListReference').objects.create(interface_list=li,target=item)
            apps.get_model('interfaces','InterfaceRating').objects.create(author=owner,target=item,sentiment='bad')
            def snapshot():
                with connection.cursor() as cursor:
                    cursor.execute("SELECT name,sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name!='django_migrations'")
                    schema=dict(cursor.fetchall());rows={}
                    for table in schema:
                        cursor.execute('SELECT * FROM '+connection.ops.quote_name(table)+' ORDER BY rowid');rows[table]=cursor.fetchall()
                return schema,rows
            schema,rows=snapshot();MigrationExecutor(connection).migrate(latest);new_schema,new_rows=snapshot()
            added={'interfaces_fieldlistreference','interfaces_fieldrating','interfaces_layoutlistreference','interfaces_layoutrating'}
            self.assertEqual(set(new_schema)-set(schema),added)
            for table in schema:
                self.assertEqual(new_schema[table],schema[table],table);self.assertEqual(new_rows[table],rows[table],table)
            for table in added:self.assertEqual(new_rows[table],[])
        finally:MigrationExecutor(connection).migrate(latest)
