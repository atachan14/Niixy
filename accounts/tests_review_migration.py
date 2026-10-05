"""0003 adds Review without rewriting existing schema or rows (SQLite)."""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from accounts.models import AccountCondition


class ReviewMigrationTests(TransactionTestCase):
    def test_existing_tables_rows_and_account_data_are_preserved(self):
        self.assertEqual(settings.DATABASES['default']['ENGINE'], 'django.db.backends.sqlite3')
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        before_targets = [node for node in latest if node[0] != 'accounts'] + [('accounts', '0002_accountcondition')]
        try:
            executor.migrate(before_targets)
            owner = get_user_model().objects.create_user('review_migration_owner')
            owner.niixy_profile.display_name = '保持する表示名'
            owner.niixy_profile.save()
            AccountCondition.objects.create(owner=owner, kind='account', definition={'account_id': owner.pk}, fingerprint='preserved', label='保持する条件')
            with connection.cursor() as cursor:
                cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != 'django_migrations' ORDER BY name")
                schema = cursor.fetchall()
                rows = {}
                for table, _ in schema:
                    cursor.execute(f'SELECT * FROM {connection.ops.quote_name(table)} ORDER BY rowid')
                    rows[table] = cursor.fetchall()
            executor = MigrationExecutor(connection)
            executor.migrate([node for node in latest if node[0] != 'accounts'] + [('accounts', '0003_accountreview')])
            with connection.cursor() as cursor:
                cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT IN ('django_migrations', 'accounts_accountreview') ORDER BY name")
                self.assertEqual(cursor.fetchall(), schema)
                for table, expected in rows.items():
                    cursor.execute(f'SELECT * FROM {connection.ops.quote_name(table)} ORDER BY rowid')
                    self.assertEqual(cursor.fetchall(), expected, table)
                cursor.execute('SELECT COUNT(*) FROM accounts_accountreview')
                self.assertEqual(cursor.fetchone()[0], 0)
        finally:
            MigrationExecutor(connection).migrate(latest)
