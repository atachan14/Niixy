from django.conf import settings
from django.db import models


class AccountProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='niixy_profile')
    display_name = models.CharField(max_length=24, blank=True, default='')

    @property
    def display_label(self):
        if self.display_name:
            return f'{self.display_name} @{self.user.username}'
        return f'@{self.user.username}'


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
