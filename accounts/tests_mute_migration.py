"""Only add Mute/nullable Board.creator; preserve existing rows and policies."""
from django.conf import settings
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class MuteMigrationTests(TransactionTestCase):
    def test_existing_rows_and_boards_are_preserved_without_backfill(self):
        self.assertEqual(settings.DATABASES['default']['ENGINE'], 'django.db.backends.sqlite3')
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        before = [node for node in latest if node[0] not in {'accounts', 'rooms'}] + [('accounts', '0003_accountreview'), ('rooms', '0009_initial_account_boards')]
        try:
            executor.migrate(before)
            apps = executor.loader.project_state(before).apps
            User = apps.get_model('auth', 'User'); Board = apps.get_model('rooms', 'Board')
            user = User.objects.create(username='legacy_mute_account')
            board = Board.objects.create(name='Legacy unknown creator')
            apps.get_model('accounts', 'AccountReview').objects.create(author=user, target=User.objects.create(username='legacy_target'), sentiment='love', body='Preserved review')
            apps.get_model('rooms', 'BoardPolicyCondition').objects.create(board=board, capability='view', decision='allow', kind='default', definition={'code': 'guest'}, label='Guest')
            with connection.cursor() as cursor:
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != 'django_migrations' ORDER BY name")
                tables = [row[0] for row in cursor.fetchall()]
                rows, schemas = {}, {}
                for table in tables:
                    cursor.execute(f'PRAGMA table_info({connection.ops.quote_name(table)})')
                    schemas[table] = cursor.fetchall()
                    columns = ', '.join(connection.ops.quote_name(row[1]) for row in schemas[table])
                    cursor.execute(f'SELECT {columns} FROM {connection.ops.quote_name(table)} ORDER BY rowid')
                    rows[table] = cursor.fetchall()
            MigrationExecutor(connection).migrate(latest)
            with connection.cursor() as cursor:
                for table in tables:
                    cursor.execute(f'PRAGMA table_info({connection.ops.quote_name(table)})')
                    after = cursor.fetchall()
                    self.assertEqual(after[:len(schemas[table])], schemas[table], table)
                    columns = ', '.join(connection.ops.quote_name(row[1]) for row in schemas[table])
                    cursor.execute(f'SELECT {columns} FROM {connection.ops.quote_name(table)} ORDER BY rowid')
                    self.assertEqual(cursor.fetchall(), rows[table], table)
                cursor.execute('SELECT creator_id FROM rooms_board'); self.assertTrue(all(row[0] is None for row in cursor.fetchall()))
                cursor.execute('SELECT COUNT(*) FROM accounts_accountmute'); self.assertEqual(cursor.fetchone()[0], 0)
        finally:
            MigrationExecutor(connection).migrate(latest)
