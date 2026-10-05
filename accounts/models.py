from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator


class AccountProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='niixy_profile')
    display_name = models.CharField(max_length=24, blank=True, default='')

    @property
    def display_label(self):
        if self.display_name:
            return f'{self.display_name} @{self.user.username}'
        return f'@{self.user.username}'


class AccountReview(models.Model):
    LOVE = 'love'
    HATE = 'hate'
    SENTIMENT_CHOICES = [(LOVE, 'Love'), (HATE, 'Hate')]
    BODY_MAX_LENGTH = 10000  # Same limit as a Response (ThreadPostForm).

    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='written_reviews')
    target = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='received_reviews')
    sentiment = models.CharField(max_length=4, choices=SENTIMENT_CHOICES)
    body = models.TextField(max_length=BODY_MAX_LENGTH, validators=[MaxLengthValidator(BODY_MAX_LENGTH)])
    revision = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at', '-pk']
        constraints = [
            models.UniqueConstraint(fields=['author', 'target'], name='unique_account_review'),
            models.CheckConstraint(condition=~models.Q(author=models.F('target')), name='account_review_not_self'),
            models.CheckConstraint(condition=models.Q(sentiment__in=['love', 'hate']), name='account_review_sentiment'),
            models.CheckConstraint(condition=~models.Q(body=''), name='account_review_body_required'),
        ]
        indexes = [models.Index(fields=['target', '-updated_at', '-id'], name='account_review_recent')]

    def clean(self):
        super().clean()
        self.body = self.body.strip()
        if not self.body:
            raise ValidationError({'body': '紹介文を入力してください。'})
        if self.author_id == self.target_id:
            raise ValidationError('自分のAccountにはReviewできません。')


class AccountCondition(models.Model):
    DEFAULT = 'default'
    ACCOUNT = 'account'
    ACCOUNT_INTERFACE = 'account_interface'
    FIELD = 'field'
    ROOM = 'room'
    KIND_CHOICES = [
        (DEFAULT, 'Default'),
        (ACCOUNT, 'Account'),
        (ACCOUNT_INTERFACE, 'AccountIF'),
        (FIELD, 'Field'),
        (ROOM, 'Room'),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='account_conditions',
    )
    kind = models.CharField(max_length=24, choices=KIND_CHOICES)
    definition = models.JSONField(default=dict)
    fingerprint = models.CharField(max_length=64)
    label = models.CharField(max_length=255)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['owner', 'fingerprint'], name='unique_account_condition'),
        ]
        ordering = ['-last_used_at', '-pk']
