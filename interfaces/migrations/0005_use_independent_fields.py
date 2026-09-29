import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('interfaces', '0004_field_definition_foundation'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='interfacedraftfield',
            name='unique_draft_field_key',
        ),
        migrations.RemoveConstraint(
            model_name='interfacefield',
            name='unique_version_field_key',
        ),
        migrations.DeleteModel(name='InterfaceDraftRequirement'),
        migrations.DeleteModel(name='InterfaceRequirement'),
        migrations.RemoveField(model_name='interfacedraftfield', name='field_key'),
        migrations.RemoveField(model_name='interfacedraftfield', name='label'),
        migrations.RemoveField(model_name='interfacedraftfield', name='field_type'),
        migrations.RemoveField(model_name='interfacedraftfield', name='settings'),
        migrations.RemoveField(model_name='interfacefield', name='field_key'),
        migrations.RemoveField(model_name='interfacefield', name='label'),
        migrations.RemoveField(model_name='interfacefield', name='field_type'),
        migrations.RemoveField(model_name='interfacefield', name='settings'),
        migrations.RemoveField(model_name='threadinterfacevalue', name='value'),
        migrations.AlterField(
            model_name='interfacedraftfield',
            name='definition',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='draft_interface_bindings',
                to='interfaces.fielddefinition',
            ),
        ),
        migrations.AlterField(
            model_name='interfacefield',
            name='definition',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='interface_bindings',
                to='interfaces.fielddefinition',
            ),
        ),
        migrations.AlterField(
            model_name='interfacefield',
            name='field_version',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='interface_bindings',
                to='interfaces.fieldversion',
            ),
        ),
        migrations.AlterField(
            model_name='threadinterfacevalue',
            name='binding',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='interface_values',
                to='interfaces.threadfieldbinding',
            ),
        ),
        migrations.AddConstraint(
            model_name='interfacedraftfield',
            constraint=models.UniqueConstraint(
                fields=('draft', 'definition'),
                name='unique_draft_field_definition',
            ),
        ),
        migrations.AddConstraint(
            model_name='interfacefield',
            constraint=models.UniqueConstraint(
                fields=('version', 'definition'),
                name='unique_version_field_definition',
            ),
        ),
    ]
