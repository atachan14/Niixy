import uuid

from django.db import migrations, models


def populate_board_submission_ids(apps, schema_editor):
    board_model = apps.get_model('rooms', 'Board')
    for board in board_model.objects.filter(submission_id__isnull=True).iterator():
        board.submission_id = uuid.uuid4()
        board.save(update_fields=['submission_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('rooms', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='board',
            name='deleted_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='deleted at'),
        ),
        migrations.AddField(
            model_name='board',
            name='status',
            field=models.CharField(
                choices=[('active', 'Active'), ('deleted', 'Deleted')],
                default='active',
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name='board',
            name='submission_id',
            field=models.UUIDField(blank=True, editable=False, null=True),
        ),
        migrations.RunPython(populate_board_submission_ids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='board',
            name='submission_id',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
