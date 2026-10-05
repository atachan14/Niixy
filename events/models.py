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

    def policy_conditions_for_evaluation(self):
        from .policies import legacy_conditions
        conditions = getattr(self, '_prefetched_objects_cache', {}).get('policy_conditions')
        if conditions is None:
            conditions = list(self.policy_conditions.all())
        if conditions:
            return conditions
        # Empty new policies have no legacy rows and correctly deny access.
        return legacy_conditions(self)

    def evaluate_policy(self, user, capability):
        from accounts.policies import evaluate_policy
        return evaluate_policy(
            (item for item in self.policy_conditions_for_evaluation() if item.capability == capability),
            user,
        )

    def allows(self, user, capability):
        if user.is_authenticated and self.creator_id == user.id and capability == ThreadAccessRule.VIEW:
            return True
        return self.evaluate_policy(user, capability).allowed

    @property
    def access_policy_rows(self):
        from .policies import policy_rows
        return policy_rows(self.policy_conditions_for_evaluation())


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
    BOARD = 'board'
    KIND_CHOICES = [(NII_MAP, 'NiiMap'), (BOARD, 'Board')]

    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name='placements')
    kind = models.CharField(max_length=24, choices=KIND_CHOICES, default=NII_MAP)
    board = models.ForeignKey(
        'rooms.Board',
        blank=True,
        null=True,
        on_delete=models.CASCADE,
        related_name='thread_placements',
    )
    latitude = models.DecimalField(
        '緯度',
        blank=True,
        null=True,
        max_digits=9,
        decimal_places=6,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        '経度',
        blank=True,
        null=True,
        max_digits=9,
        decimal_places=6,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    is_primary = models.BooleanField(default=True)
    created_at = models.DateTimeField('掲載日時', auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(
                        kind='niimap',
                        board__isnull=True,
                        latitude__isnull=False,
                        longitude__isnull=False,
                    )
                    | models.Q(
                        kind='board',
                        board__isnull=False,
                        latitude__isnull=True,
                        longitude__isnull=True,
                    )
                ),
                name='valid_thread_placement_target',
            ),
            models.UniqueConstraint(
                fields=['thread'],
                condition=models.Q(is_primary=True),
                name='unique_primary_thread_placement',
            ),
        ]


class ThreadAccessRule(models.Model):
    VIEW = 'view'
    WRITE = 'write'
    GUEST = 'guest'
    ACCOUNT = 'account'
    CAPABILITY_CHOICES = [(VIEW, '閲覧'), (WRITE, '書込')]
    AUDIENCE_CHOICES = [(GUEST, 'Guest'), (ACCOUNT, 'NiixyAccount')]

    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name='access_rules')
    capability = models.CharField(max_length=16, choices=CAPABILITY_CHOICES)
    audience = models.CharField(max_length=16, choices=AUDIENCE_CHOICES)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['thread', 'capability', 'audience'], name='unique_thread_access_rule')]


class ThreadPolicyCondition(models.Model):
    VIEW = 'view'
    WRITE = 'write'
    ALLOW = 'allow'
    DENY = 'deny'
    CAPABILITY_CHOICES = [(VIEW, '閲覧'), (WRITE, '書込')]
    DECISION_CHOICES = [(ALLOW, '可能'), (DENY, '不可')]

    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name='policy_conditions')
    capability = models.CharField(max_length=16, choices=CAPABILITY_CHOICES)
    decision = models.CharField(max_length=8, choices=DECISION_CHOICES)
    group_key = models.UUIDField(default=uuid.uuid4)
    position = models.PositiveSmallIntegerField(default=0)
    kind = models.CharField(max_length=24)
    definition = models.JSONField(default=dict)
    label = models.CharField(max_length=255)

    class Meta:
        ordering = ['capability', 'decision', 'group_key', 'position', 'pk']


class NiiMapFilterPreference(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='niimap_filter_preference')
    show_guest_threads = models.BooleanField(default=True)
    account_ids_enabled = models.BooleanField(default=False)
    account_section_open = models.BooleanField(default=False)
    search_state = models.JSONField(default=dict, blank=True)


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
