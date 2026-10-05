"""AccountList schema additions preserve every pre-existing SQLite table/row."""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from .models import AccountReview, AccountMute


class AccountListMigrationTests(TransactionTestCase):
    def test_additive_schema_and_existing_rows(self):
        self.assertEqual(settings.DATABASES['default']['ENGINE'],'django.db.backends.sqlite3')
        executor=MigrationExecutor(connection);latest=executor.loader.graph.leaf_nodes()
        old=[node for node in latest if node[0]!='accounts']+[('accounts','0004_accountmute')]
        try:
            executor.migrate(old)
            owner=get_user_model().objects.create_user('list_migration_owner')
            target=get_user_model().objects.create_user('list_migration_target')
            AccountReview.objects.create(author=owner,target=target,sentiment='love',body='保持する紹介文')
            AccountMute.objects.create(muter=owner,muted_account=target)
            with connection.cursor() as cursor:
                cursor.execute("SELECT name,sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name!='django_migrations' ORDER BY name")
                schema=cursor.fetchall();rows={}
                for table,_ in schema:
                    cursor.execute(f'SELECT * FROM {connection.ops.quote_name(table)} ORDER BY rowid');rows[table]=cursor.fetchall()
            MigrationExecutor(connection).migrate(latest)
            with connection.cursor() as cursor:
                cursor.execute("SELECT name,sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT IN ('django_migrations','accounts_accountlist','accounts_accountlistreference') ORDER BY name")
                self.assertEqual(cursor.fetchall(),schema)
                for table,expected in rows.items():
                    cursor.execute(f'SELECT * FROM {connection.ops.quote_name(table)} ORDER BY rowid');self.assertEqual(cursor.fetchall(),expected,table)
                for table in ['accounts_accountlist','accounts_accountlistreference']:
                    cursor.execute('SELECT COUNT(*) FROM '+table);self.assertEqual(cursor.fetchone()[0],0)
        finally:
            MigrationExecutor(connection).migrate(latest)
