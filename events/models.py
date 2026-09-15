from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Event(models.Model):
    title = models.CharField('Event名', max_length=120)
    description = models.TextField('Event詳細', blank=True)
    capacity = models.PositiveIntegerField(
        '募集人数',
        default=1,
        validators=[MinValueValidator(1)],
    )
    starts_at = models.DateTimeField('開始日時')
    ends_at = models.DateTimeField('終了日時', blank=True, null=True)
    latitude = models.DecimalField(
        '緯度',
        max_digits=9,
        decimal_places=6,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        '経度',
        max_digits=9,
        decimal_places=6,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)

    class Meta:
        ordering = ['starts_at', 'created_at']

    def __str__(self):
        return self.title

class Station(models.Model):
    station_code = models.CharField('駅コード', max_length=16, unique=True)
    group_code = models.CharField('駅グループコード', max_length=16)
    name = models.CharField('駅名', max_length=120, db_index=True)
    line_name = models.CharField('路線名', max_length=120)
    operator_name = models.CharField('運営会社', max_length=120)
    latitude = models.DecimalField('緯度', max_digits=9, decimal_places=6)
    longitude = models.DecimalField('経度', max_digits=9, decimal_places=6)

    class Meta:
        ordering = ['name', 'line_name']

    def __str__(self):
        return f'{self.name} ({self.line_name})'


class Locality(models.Model):
    source_key = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=160, db_index=True)
    full_name = models.CharField(max_length=255, db_index=True)
    detail = models.CharField(max_length=255)
    kind = models.CharField(max_length=16)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)

    class Meta:
        ordering = ['kind', 'full_name']

    def __str__(self):
        return self.full_name
