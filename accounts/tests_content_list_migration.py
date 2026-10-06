from django.conf import settings
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class ContentListMigrationTests(TransactionTestCase):
    def test_existing_rows_and_schema_preserved(self):
        self.assertEqual(settings.DATABASES['default']['ENGINE'],'django.db.backends.sqlite3')
        executor=MigrationExecutor(connection);latest=executor.loader.graph.leaf_nodes()
        old=[node for node in latest if node[0] not in {'rooms','interfaces'}]+[('rooms','0010_board_creator'),('interfaces','0009_account_layout')]
        try:
            executor.migrate(old);apps=executor.loader.project_state(old).apps
            User=apps.get_model('auth','User');owner=User.objects.create(username='migration_owner')
            Collection=apps.get_model('rooms','Collection');Board=apps.get_model('rooms','Board');Placement=apps.get_model('rooms','BoardPlacement')
            collection=Collection.objects.create(account=owner,name='保持する配置')
            board=Board.objects.create(name='保持Board',creator=owner)
            Placement.objects.create(board=board,kind='collection',collection=collection)
            Interface=apps.get_model('interfaces','Interface');Version=apps.get_model('interfaces','InterfaceVersion')
            interface=Interface.objects.create(creator=owner,kind='account',name='保持IF');version=Version.objects.create(interface=interface,version_number=1,name=interface.name)
            interface.current_version=version;interface.save()
            with connection.cursor() as cursor:
                cursor.execute("SELECT name,sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name!='django_migrations' ORDER BY name")
                schema=dict(cursor.fetchall());rows={};columns={}
                for table in schema:
                    quoted=connection.ops.quote_name(table);cursor.execute('PRAGMA table_info('+quoted+')');columns[table]=[row[1] for row in cursor.fetchall()]
                    cursor.execute('SELECT * FROM '+quoted+' ORDER BY rowid');rows[table]=cursor.fetchall()
            MigrationExecutor(connection).migrate(latest)
            with connection.cursor() as cursor:
                cursor.execute("SELECT name,sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name!='django_migrations' ORDER BY name")
                new_schema=dict(cursor.fetchall())
                self.assertEqual(set(new_schema)-set(schema),{'rooms_boardlistreference','rooms_boardrating','interfaces_interfacelist','interfaces_interfacelistreference','interfaces_interfacerating','interfaces_fieldlistreference','interfaces_fieldrating','interfaces_layoutlistreference','interfaces_layoutrating'})
                for table,expected in rows.items():
                    if table!='rooms_collection':self.assertEqual(new_schema[table],schema[table],table)
                    fields=','.join(connection.ops.quote_name(column) for column in columns[table]);cursor.execute('SELECT '+fields+' FROM '+connection.ops.quote_name(table)+' ORDER BY rowid');self.assertEqual(cursor.fetchall(),expected,table)
                cursor.execute('SELECT list_submission_id FROM rooms_collection');self.assertTrue(all(row==(None,) for row in cursor.fetchall()))
                for table in set(new_schema)-set(schema):cursor.execute('SELECT COUNT(*) FROM '+table);self.assertEqual(cursor.fetchone()[0],0)
        finally:MigrationExecutor(connection).migrate(latest)
