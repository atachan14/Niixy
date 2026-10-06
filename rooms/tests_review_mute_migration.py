"""0012 adds two empty tables without rebuilding/revising existing data."""
from uuid import uuid4
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from rooms.services import create_room


class RoomReviewMuteMigrationTests(TransactionTestCase):
    def test_existing_schema_rows_and_sequences_preserved(self):
        self.assertEqual(settings.DATABASES['default']['ENGINE'], 'django.db.backends.sqlite3')
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        before = [node for node in latest if node[0] != 'rooms'] + [('rooms', '0011_content_lists')]
        try:
            executor.migrate(before)
            owner = get_user_model().objects.create_user('room_migration_owner')
            create_room(submission_id=uuid4(), owner=owner, name='Preserved Room', description='keep', latitude='35', longitude='139')
            with connection.cursor() as cursor:
                cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != 'django_migrations' ORDER BY name")
                schema = cursor.fetchall()
                rows = {}
                for table, _ in schema:
                    cursor.execute(f'SELECT * FROM {connection.ops.quote_name(table)} ORDER BY rowid')
                    rows[table] = cursor.fetchall()
                cursor.execute('SELECT name, seq FROM sqlite_sequence ORDER BY name')
                sequences = cursor.fetchall()
            MigrationExecutor(connection).migrate(latest)
            with connection.cursor() as cursor:
                cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT IN ('django_migrations', 'rooms_roomreview', 'rooms_roommute') ORDER BY name")
                self.assertEqual(cursor.fetchall(), schema)
                for table, expected in rows.items():
                    cursor.execute(f'SELECT * FROM {connection.ops.quote_name(table)} ORDER BY rowid')
                    self.assertEqual(cursor.fetchall(), expected, table)
                cursor.execute("SELECT name, seq FROM sqlite_sequence WHERE name != 'django_migrations' ORDER BY name")
                self.assertEqual(cursor.fetchall(), [row for row in sequences if row[0] != 'django_migrations'])
                for table in ['rooms_roomreview', 'rooms_roommute']:
                    cursor.execute(f'SELECT COUNT(*) FROM {table}')
                    self.assertEqual(cursor.fetchone()[0], 0)
        finally:
            MigrationExecutor(connection).migrate(latest)
