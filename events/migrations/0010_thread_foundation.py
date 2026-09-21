import uuid

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('events', '0009_niimapfilterpreference_section_state'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Thread',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('submission_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('title', models.CharField(max_length=120, verbose_name='Threadタイトル')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='作成日時')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新日時')),
                ('last_activity_at', models.DateTimeField(auto_now_add=True, verbose_name='最終活動日時')),
                ('creator', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='threads', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-last_activity_at', '-created_at']},
        ),
        migrations.CreateModel(
            name='ThreadAccessRule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('capability', models.CharField(choices=[('discover', '発見'), ('view', '閲覧'), ('write', '書込')], max_length=16)),
                ('audience', models.CharField(choices=[('guest', 'Guest'), ('account', 'NiixyAccount')], max_length=16)),
                ('thread', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='access_rules', to='events.thread')),
            ],
        ),
        migrations.CreateModel(
            name='ThreadPlacement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kind', models.CharField(default='niimap', max_length=24)),
                ('latitude', models.DecimalField(decimal_places=6, max_digits=9, validators=[django.core.validators.MinValueValidator(-90), django.core.validators.MaxValueValidator(90)], verbose_name='緯度')),
                ('longitude', models.DecimalField(decimal_places=6, max_digits=9, validators=[django.core.validators.MinValueValidator(-180), django.core.validators.MaxValueValidator(180)], verbose_name='経度')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='掲載日時')),
                ('thread', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='placements', to='events.thread')),
            ],
        ),
        migrations.CreateModel(
            name='ThreadPost',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('number', models.PositiveIntegerField(verbose_name='投稿番号')),
                ('body', models.TextField(verbose_name='本文')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='投稿日時')),
                ('creator', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='thread_posts', to=settings.AUTH_USER_MODEL)),
                ('thread', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='posts', to='events.thread')),
            ],
            options={'ordering': ['number']},
        ),
        migrations.RenameField(model_name='niimapfilterpreference', old_name='show_guest_events', new_name='show_guest_threads'),
        migrations.RemoveField(model_name='niimapfilterpreference', name='range_filter_enabled'),
        migrations.RemoveField(model_name='niimapfilterpreference', name='show_ongoing'),
        migrations.RemoveField(model_name='niimapfilterpreference', name='show_today'),
        migrations.RemoveField(model_name='niimapfilterpreference', name='show_tomorrow'),
        migrations.RemoveField(model_name='niimapfilterpreference', name='show_ended'),
        migrations.RemoveField(model_name='niimapfilterpreference', name='datetime_section_open'),
        migrations.DeleteModel(name='Event'),
        migrations.AddConstraint(
            model_name='threadpost',
            constraint=models.UniqueConstraint(fields=('thread', 'number'), name='unique_thread_post_number'),
        ),
        migrations.AddConstraint(
            model_name='threadaccessrule',
            constraint=models.UniqueConstraint(fields=('thread', 'capability', 'audience'), name='unique_thread_access_rule'),
        ),
    ]
