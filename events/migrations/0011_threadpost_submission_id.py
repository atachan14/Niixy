import uuid

from django.db import migrations, models


def assign_submission_ids(apps, schema_editor):
    ThreadPost = apps.get_model('events', 'ThreadPost')
    for post in ThreadPost.objects.filter(submission_id__isnull=True).iterator():
        post.submission_id = uuid.uuid4()
        post.save(update_fields=['submission_id'])


class Migration(migrations.Migration):
    dependencies = [('events', '0010_thread_foundation')]

    operations = [
        migrations.AddField(
            model_name='threadpost',
            name='submission_id',
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.RunPython(assign_submission_ids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='threadpost',
            name='submission_id',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
