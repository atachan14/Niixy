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
