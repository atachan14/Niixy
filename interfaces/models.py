import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower


class Interface(models.Model):
    ACCOUNT = 'account'
    ROOM = 'room'
    THREAD = 'thread'
    THREAD_POST = 'thread_post'
    KIND_CHOICES = [
        (ACCOUNT, 'AccountIF'),
        (ROOM, 'RoomIF'),
        (THREAD, 'ThreadIF'),
        (THREAD_POST, 'ResponseIF'),
    ]
    ACTIVE = 'active'
    DELETED = 'deleted'
    STATUS_CHOICES = [(ACTIVE, 'Active'), (DELETED, 'Deleted')]

    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='interfaces')
    kind = models.CharField(max_length=24, choices=KIND_CHOICES)
    name = models.CharField(max_length=120)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=ACTIVE)
    current_version = models.ForeignKey(
        'InterfaceVersion',
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower('name'), 'creator', name='unique_interface_name_per_creator'),
        ]
        ordering = ['name', 'pk']

    def __str__(self):
        return f'{self.creator.username}/{self.name}'


class ImmutablePublishedModel(models.Model):
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError('公開済みの定義は変更できません。')
        return super().save(*args, **kwargs)


class InterfaceVersion(ImmutablePublishedModel):
    interface = models.ForeignKey(Interface, on_delete=models.CASCADE, related_name='versions')
    version_number = models.PositiveIntegerField()
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['interface', 'version_number'], name='unique_interface_version_number'),
        ]
        ordering = ['interface_id', 'version_number']

    def __str__(self):
        return f'{self.interface} v{self.version_number}'


class InterfaceDraft(models.Model):
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='interface_drafts')
    interface = models.OneToOneField(
        Interface,
        blank=True,
        null=True,
        on_delete=models.CASCADE,
        related_name='draft',
    )
    kind = models.CharField(max_length=24, choices=Interface.KIND_CHOICES, default=Interface.THREAD)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at', '-pk']

    def __str__(self):
        return f'Draft: {self.creator.username}/{self.name}'


class FieldType(models.TextChoices):
    SHORT_TEXT = 'short_text', '一行テキスト'
    LONG_TEXT = 'long_text', '複数行テキスト'
    INTEGER = 'integer', '整数'
    DECIMAL = 'decimal', '小数'
    DATE = 'date', '日付'
    DATETIME = 'datetime', '日時'
    BOOLEAN = 'boolean', '真偽値'
    SINGLE_CHOICE = 'single_choice', '単一選択'
    MULTIPLE_CHOICE = 'multiple_choice', '複数選択'


class InterfaceDraftField(models.Model):
    draft = models.ForeignKey(InterfaceDraft, on_delete=models.CASCADE, related_name='fields')
    field_key = models.UUIDField(default=uuid.uuid4, editable=False)
    label = models.CharField(max_length=120)
    field_type = models.CharField(max_length=24, choices=FieldType.choices)
    required = models.BooleanField(default=False)
    settings = models.JSONField(default=dict, blank=True)
    position = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['draft', 'field_key'], name='unique_draft_field_key'),
            models.UniqueConstraint(fields=['draft', 'position'], name='unique_draft_field_position'),
        ]
        ordering = ['position', 'pk']


class InterfaceField(ImmutablePublishedModel):
    version = models.ForeignKey(InterfaceVersion, on_delete=models.CASCADE, related_name='fields')
    field_key = models.UUIDField(default=uuid.uuid4, editable=False)
    label = models.CharField(max_length=120)
    field_type = models.CharField(max_length=24, choices=FieldType.choices)
    required = models.BooleanField(default=False)
    settings = models.JSONField(default=dict, blank=True)
    position = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['version', 'field_key'], name='unique_version_field_key'),
            models.UniqueConstraint(fields=['version', 'position'], name='unique_version_field_position'),
        ]
        ordering = ['position', 'pk']


class InterfaceDraftRequirement(models.Model):
    draft = models.ForeignKey(InterfaceDraft, on_delete=models.CASCADE, related_name='requirements')
    required_interface = models.ForeignKey(Interface, on_delete=models.PROTECT, related_name='draft_dependents')
    position = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['draft', 'required_interface'], name='unique_draft_requirement'),
            models.UniqueConstraint(fields=['draft', 'position'], name='unique_draft_requirement_position'),
        ]
        ordering = ['position', 'pk']


class InterfaceRequirement(ImmutablePublishedModel):
    version = models.ForeignKey(InterfaceVersion, on_delete=models.CASCADE, related_name='requirements')
    required_interface = models.ForeignKey(Interface, on_delete=models.PROTECT, related_name='version_dependents')
    required_version = models.ForeignKey(InterfaceVersion, on_delete=models.PROTECT, related_name='resolved_dependents')
    position = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['version', 'required_interface'], name='unique_version_requirement'),
            models.UniqueConstraint(fields=['version', 'position'], name='unique_version_requirement_position'),
        ]
        ordering = ['position', 'pk']


class ThreadInterfaceImplementation(models.Model):
    thread = models.ForeignKey('events.Thread', on_delete=models.CASCADE, related_name='interface_implementations')
    interface = models.ForeignKey(Interface, on_delete=models.PROTECT, related_name='thread_implementations')
    version = models.ForeignKey(InterfaceVersion, on_delete=models.PROTECT, related_name='thread_implementations')
    position = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['thread', 'interface'], name='unique_thread_interface'),
            models.UniqueConstraint(fields=['thread', 'position'], name='unique_thread_interface_position'),
        ]
        ordering = ['position', 'pk']


class ThreadInterfaceValue(models.Model):
    implementation = models.ForeignKey(
        ThreadInterfaceImplementation,
        on_delete=models.CASCADE,
        related_name='values',
    )
    field = models.ForeignKey(InterfaceField, on_delete=models.PROTECT, related_name='thread_values')
    value = models.JSONField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['implementation', 'field'], name='unique_thread_interface_field_value'),
        ]

    @property
    def display_value(self):
        if isinstance(self.value, bool):
            return 'はい' if self.value else 'いいえ'
        if isinstance(self.value, list):
            return ' / '.join(str(item) for item in self.value)
        return str(self.value)
