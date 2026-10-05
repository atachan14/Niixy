from django.db import migrations, models
import django.db.models.deletion


def backfill_versions(apps, schema_editor):
    Binding = apps.get_model('interfaces', 'AccountFieldBinding')
    Direct = apps.get_model('interfaces', 'AccountDirectField')
    Reference = apps.get_model('interfaces', 'AccountInterfaceValue')
    Implementation = apps.get_model('interfaces', 'AccountInterfaceImplementation')
    alias = schema_editor.connection.alias
    for binding in Binding.objects.using(alias).select_related('definition').iterator():
        references = [
            ((item.created_at, item.pk, 0), item.version_id)
            for item in Direct.objects.using(alias).filter(binding_id=binding.pk)
        ]
        references += [
            ((item.implementation.created_at, item.implementation_id, 1), item.field.field_version_id)
            for item in Reference.objects.using(alias).filter(binding_id=binding.pk)
                .select_related('implementation', 'field')
        ]
        version_id = min(references)[1] if references else binding.definition.current_version_id
        if version_id is None:
            raise RuntimeError('Account binding has no published FieldVersion; inspect before migrating.')
        Binding.objects.using(alias).filter(pk=binding.pk).update(version_id=version_id)
    # Mark incompatible applications without upgrading references or changing values.
    for item in Implementation.objects.using(alias).select_related('interface').iterator():
        current = item.interface.current_version
        compatible = current is not None and all(
            field.definition.status == 'active' and field.definition.current_version_id == field.field_version_id
            for field in current.fields.select_related('definition').all()
        )
        if not compatible:
            Implementation.objects.using(alias).filter(pk=item.pk).update(state='frozen')
        elif (any(field.definition.current_version_id != field.field_version_id
                  for field in item.version.fields.select_related('definition').all())
              or any(value.binding.version_id != value.field.field_version_id
                     for value in item.values.select_related('binding', 'field').all())):
            Implementation.objects.using(alias).filter(pk=item.pk).update(state='pending')


class Migration(migrations.Migration):
    dependencies = [('interfaces', '0007_accountfieldvalue_accountfieldbinding_and_more')]
    operations = [
        migrations.AddField(model_name='accountinterfaceimplementation', name='state',
            field=models.CharField(choices=[('active', '有効'), ('frozen', '凍結'), ('pending', '復帰待ち')],
                                   default='active', db_default='active', max_length=16)),
        migrations.AddField(model_name='accountfieldbinding', name='version',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT,
                                    related_name='account_bindings', to='interfaces.fieldversion')),
        migrations.RunPython(backfill_versions, migrations.RunPython.noop),
    ]
