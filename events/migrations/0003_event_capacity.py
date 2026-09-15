from django.core.validators import MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('events', '0002_station'),
    ]

    operations = [
        migrations.AddField(
            model_name='event',
            name='capacity',
            field=models.PositiveIntegerField(
                default=1,
                validators=[MinValueValidator(1)],
                verbose_name='募集人数',
            ),
        ),
    ]
