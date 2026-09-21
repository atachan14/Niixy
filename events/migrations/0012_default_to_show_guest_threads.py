from django.db import migrations, models


def enable_guest_threads(apps, schema_editor):
    Preference = apps.get_model('events', 'NiiMapFilterPreference')
    Preference.objects.update(show_guest_threads=True)


class Migration(migrations.Migration):
    dependencies = [('events', '0011_threadpost_submission_id')]

    operations = [
        migrations.AlterField(
            model_name='niimapfilterpreference',
            name='show_guest_threads',
            field=models.BooleanField(default=True),
        ),
        migrations.RunPython(enable_guest_threads, migrations.RunPython.noop),
    ]
