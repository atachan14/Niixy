from django.db import migrations, models


def remove_discover_rules(apps, schema_editor):
    ThreadAccessRule = apps.get_model('events', 'ThreadAccessRule')
    ThreadAccessRule.objects.filter(capability='discover').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('events', '0012_default_to_show_guest_threads'),
    ]

    operations = [
        migrations.RunPython(remove_discover_rules, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='threadaccessrule',
            name='capability',
            field=models.CharField(
                choices=[('view', '閲覧'), ('write', '書込')],
                max_length=16,
            ),
        ),
    ]
