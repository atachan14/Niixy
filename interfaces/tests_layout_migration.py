"""0008 -> 0009 is additive and preserves existing Account application data."""
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class AccountLayoutMigrationTests(TransactionTestCase):
    def test_existing_versions_bindings_values_survive_additive_migration(self):
        self.assertEqual(connection.vendor, 'sqlite')
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        try:
            executor.migrate([('interfaces', '0008_account_application_versions')])
            apps = executor.loader.project_state([('interfaces', '0008_account_application_versions')]).apps
            User = apps.get_model('auth', 'User')
            Definition = apps.get_model('interfaces', 'FieldDefinition')
            Version = apps.get_model('interfaces', 'FieldVersion')
            Value = apps.get_model('interfaces', 'AccountFieldValue')
            Binding = apps.get_model('interfaces', 'AccountFieldBinding')
            Direct = apps.get_model('interfaces', 'AccountDirectField')
            account = User.objects.create(username='migration_layout')
            definition = Definition.objects.create(creator_id=account.pk, name='old field')
            version = Version.objects.create(definition=definition, version_number=1, name='old field', field_type='short_text')
            Definition.objects.filter(pk=definition.pk).update(current_version_id=version.pk)
            value = Value.objects.create(account_id=account.pk, value='existing public value')
            binding = Binding.objects.create(account_id=account.pk, definition=definition, version=version, value=value)
            direct = Direct.objects.create(account_id=account.pk, definition=definition, version=version, binding=binding, position=0)
            before = [list(model.objects.values()) for model in [Definition, Version, Value, Binding, Direct]]
            executor = MigrationExecutor(connection)
            executor.migrate([('interfaces', '0009_account_layout')])
            self.assertEqual([list(model.objects.values()) for model in [Definition, Version, Value, Binding, Direct]], before)
            new_apps = executor.loader.project_state([('interfaces', '0009_account_layout')]).apps
            self.assertEqual(new_apps.get_model('interfaces', 'AccountLayoutApplication').objects.count(), 0)
            self.assertEqual(new_apps.get_model('interfaces', 'AccountLayoutVersion').objects.count(), 0)
        finally:
            MigrationExecutor(connection).migrate(latest)
