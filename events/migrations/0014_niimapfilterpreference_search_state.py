from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('events', '0013_remove_thread_discover_rules'),
    ]

    operations = [
        migrations.AddField(
            model_name='niimapfilterpreference',
            name='search_state',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
