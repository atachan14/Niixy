import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class IdempotentSubmission(models.Model):
    submission_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    class Meta:
        abstract = True


class Thread(IdempotentSubmission):
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name='threads',
    )
    title = models.CharField('Threadタイトル', max_length=120)
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)
    last_activity_at = models.DateTimeField('最終活動日時', auto_now_add=True)

    class Meta:
        ordering = ['-last_activity_at', '-created_at']

    def __str__(self):
        return self.title

    def allows(self, user, capability):
        if user.is_authenticated and self.creator_id == user.id and capability == ThreadAccessRule.VIEW:
            return True
        audience = ThreadAccessRule.ACCOUNT if user.is_authenticated else ThreadAccessRule.GUEST
        return self.access_rules.filter(capability=capability, audience=audience).exists()


class ThreadPost(IdempotentSubmission):
    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name='posts')
    number = models.PositiveIntegerField('投稿番号')
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name='thread_posts',
    )
    body = models.TextField('本文')
    created_at = models.DateTimeField('投稿日時', auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['thread', 'number'], name='unique_thread_post_number')]
        ordering = ['number']


class ThreadPlacement(models.Model):
    NII_MAP = 'niimap'
    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name='placements')
    kind = models.CharField(max_length=24, default=NII_MAP)
    latitude = models.DecimalField('緯度', max_digits=9, decimal_places=6, validators=[MinValueValidator(-90), MaxValueValidator(90)])
    longitude = models.DecimalField('経度', max_digits=9, decimal_places=6, validators=[MinValueValidator(-180), MaxValueValidator(180)])
    created_at = models.DateTimeField('掲載日時', auto_now_add=True)


class ThreadAccessRule(models.Model):
    DISCOVER = 'discover'
    VIEW = 'view'
    WRITE = 'write'
    GUEST = 'guest'
    ACCOUNT = 'account'
    CAPABILITY_CHOICES = [(DISCOVER, '発見'), (VIEW, '閲覧'), (WRITE, '書込')]
    AUDIENCE_CHOICES = [(GUEST, 'Guest'), (ACCOUNT, 'NiixyAccount')]

    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name='access_rules')
    capability = models.CharField(max_length=16, choices=CAPABILITY_CHOICES)
    audience = models.CharField(max_length=16, choices=AUDIENCE_CHOICES)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['thread', 'capability', 'audience'], name='unique_thread_access_rule')]


class NiiMapFilterPreference(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='niimap_filter_preference')
    show_guest_threads = models.BooleanField(default=True)
    account_ids_enabled = models.BooleanField(default=False)
    account_section_open = models.BooleanField(default=False)


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
