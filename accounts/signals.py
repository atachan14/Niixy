from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import AccountProfile


@receiver(post_save, sender=get_user_model())
def create_account_profile(sender, instance, created, **kwargs):
    if created:
        AccountProfile.objects.create(user=instance)
