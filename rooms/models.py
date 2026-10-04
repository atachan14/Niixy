import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Room(models.Model):
    submission_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='owned_rooms',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name='created_rooms',
    )
    name = models.CharField('Room名', max_length=120)
    description = models.TextField('Description', blank=True, default='', max_length=10000)
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)
    last_activity_at = models.DateTimeField('最終活動日時', auto_now_add=True)

    class Meta:
        ordering = ['-last_activity_at', '-created_at']

    def __str__(self):
        return self.name

    def has_member(self, user):
        return user.is_authenticated and self.memberships.filter(account=user).exists()


class RoomPlacement(models.Model):
    room = models.OneToOneField(Room, on_delete=models.CASCADE, related_name='placement')
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
    created_at = models.DateTimeField('掲載日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)


class RoomMembership(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='memberships')
    account = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='room_memberships',
    )
    joined_at = models.DateTimeField('参加日時', auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['room', 'account'], name='unique_room_membership'),
        ]
        ordering = ['joined_at', 'pk']


class Collection(models.Model):
    name = models.CharField('Collection名', max_length=120)
    account = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.CASCADE,
        related_name='collections',
    )
    room = models.ForeignKey(
        Room,
        blank=True,
        null=True,
        on_delete=models.CASCADE,
        related_name='collections',
    )
    is_uncategorized = models.BooleanField(default=False)
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)
    last_activity_at = models.DateTimeField('最終活動日時', auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(account__isnull=False, room__isnull=True)
                    | models.Q(account__isnull=True, room__isnull=False)
                ),
                name='collection_has_one_container',
            ),
            models.UniqueConstraint(
                fields=['account'],
                condition=models.Q(
                    account__isnull=False,
                    is_uncategorized=True,
                ),
                name='unique_account_uncategorized_collection',
            ),
            models.UniqueConstraint(
                fields=['room'],
                condition=models.Q(
                    is_uncategorized=True,
                    room__isnull=False,
                ),
                name='unique_room_uncategorized_collection',
            ),
        ]
        ordering = ['-last_activity_at', '-created_at']

    def __str__(self):
        return self.name


class Board(models.Model):
    submission_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    name = models.CharField('Board名', max_length=120)
    description = models.TextField('詳細', blank=True, max_length=10000)
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)
    last_activity_at = models.DateTimeField('最終活動日時', auto_now_add=True)

    class Meta:
        ordering = ['-last_activity_at', '-created_at']

    def __str__(self):
        return self.name


class BoardPlacement(models.Model):
    COLLECTION = 'collection'
    NII_MAP = 'niimap'
    KIND_CHOICES = [(COLLECTION, 'Collection'), (NII_MAP, 'NiiMap')]

    board = models.OneToOneField(Board, on_delete=models.CASCADE, related_name='placement')
    kind = models.CharField(max_length=24, choices=KIND_CHOICES)
    collection = models.ForeignKey(
        Collection,
        blank=True,
        null=True,
        on_delete=models.CASCADE,
        related_name='board_placements',
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
    created_at = models.DateTimeField('掲載日時', auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(
                        kind='collection',
                        collection__isnull=False,
                        latitude__isnull=True,
                        longitude__isnull=True,
                    )
                    | models.Q(
                        kind='niimap',
                        collection__isnull=True,
                        latitude__isnull=False,
                        longitude__isnull=False,
                    )
                ),
                name='valid_board_placement_target',
            ),
        ]
