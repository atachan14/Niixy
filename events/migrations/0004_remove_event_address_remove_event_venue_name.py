from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('events', '0003_event_capacity'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='event',
            name='address',
        ),
        migrations.RemoveField(
            model_name='event',
            name='venue_name',
        ),
    ]
