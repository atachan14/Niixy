"""Migration 0008 preserves historical references, values, and timestamps."""
from datetime import timedelta
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class AccountVersionMigrationTests(TransactionTestCase):
    def test_backfill_earliest_reference_and_freeze_without_value_or_ref_changes(self):
        old_target = [('interfaces', '0007_accountfieldvalue_accountfieldbinding_and_more')]
        new_target = [('interfaces', '0008_account_application_versions')]
        executor = MigrationExecutor(connection)
        executor.migrate(old_target)
        old = executor.loader.project_state(old_target).apps
        try:
            User = old.get_model('auth', 'User')
            owner = User.objects.create(username='migration_owner')
            Definition = old.get_model('interfaces', 'FieldDefinition')
            Version = old.get_model('interfaces', 'FieldVersion')
            definition = Definition.objects.create(creator_id=owner.pk, name='Old')
            v1 = Version.objects.create(definition=definition, version_number=1, name='Old', field_type='short_text')
            v2 = Version.objects.create(definition=definition, version_number=2, name='New', field_type='short_text')
            definition.current_version = v2; definition.save()
            Value = old.get_model('interfaces', 'AccountFieldValue')
            Binding = old.get_model('interfaces', 'AccountFieldBinding')
            value = Value.objects.create(account_id=owner.pk, value='unchanged')
            binding = Binding.objects.create(account_id=owner.pk, definition=definition, value=value)
            interface = old.get_model('interfaces', 'Interface').objects.create(creator_id=owner.pk, kind='account', name='IF')
            iv = old.get_model('interfaces', 'InterfaceVersion').objects.create(interface=interface, version_number=1, name='IF')
            interface.current_version = iv; interface.save()
            field = old.get_model('interfaces', 'InterfaceField').objects.create(version=iv, definition=definition,
                field_version=v1, position=0, required=True)
            item = old.get_model('interfaces', 'AccountInterfaceImplementation').objects.create(account_id=owner.pk,
                interface=interface, version=iv, position=0)
            ref = old.get_model('interfaces', 'AccountInterfaceValue').objects.create(implementation=item, field=field, binding=binding)
            direct = old.get_model('interfaces', 'AccountDirectField').objects.create(account_id=owner.pk,
                definition=definition, version=v2, binding=binding, position=0)
            old.get_model('interfaces', 'AccountDirectField').objects.filter(pk=direct.pk).update(
                created_at=item.created_at + timedelta(seconds=1))
            timestamp = value.updated_at
            executor = MigrationExecutor(connection); executor.migrate(new_target)
            new = executor.loader.project_state(new_target).apps
            self.assertEqual(new.get_model('interfaces', 'AccountFieldBinding').objects.get(pk=binding.pk).version_id, v1.pk)
            current_value = new.get_model('interfaces', 'AccountFieldValue').objects.get(pk=value.pk)
            self.assertEqual((current_value.value, current_value.updated_at), ('unchanged', timestamp))
            self.assertEqual(new.get_model('interfaces', 'AccountInterfaceImplementation').objects.get(pk=item.pk).state, 'frozen')
            self.assertEqual(new.get_model('interfaces', 'AccountInterfaceValue').objects.get(pk=ref.pk).field_id, field.pk)
            self.assertEqual(new.get_model('interfaces', 'AccountDirectField').objects.get(pk=direct.pk).version_id, v2.pk)
            self.assertEqual(new.get_model('interfaces', 'AccountFieldValue').objects.count(), 1)
            # The old deployment can still INSERT without either new column.
            legacy_owner = User.objects.create(username='legacy_writer')
            legacy_value = Value.objects.create(account_id=legacy_owner.pk, value='legacy')
            legacy_binding = Binding.objects.create(account_id=legacy_owner.pk, definition=definition, value=legacy_value)
            legacy_item = old.get_model('interfaces', 'AccountInterfaceImplementation').objects.create(
                account_id=legacy_owner.pk, interface=interface, version=iv, position=0)
            self.assertIsNone(new.get_model('interfaces', 'AccountFieldBinding').objects.get(pk=legacy_binding.pk).version_id)
            self.assertEqual(new.get_model('interfaces', 'AccountInterfaceImplementation').objects.get(pk=legacy_item.pk).state, 'active')
        finally:
            MigrationExecutor(connection).migrate(executor.loader.graph.leaf_nodes())
