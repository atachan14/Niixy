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

    @property
    def publication_version_number(self):
        if self.interface_id and self.interface.current_version_id:
            return self.interface.current_version.version_number + 1
        return 1


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


class FieldDefinition(models.Model):
    ACTIVE = 'active'
    DELETED = 'deleted'
    STATUS_CHOICES = [(ACTIVE, 'Active'), (DELETED, 'Deleted')]

    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='field_definitions',
    )
    key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField(max_length=120)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=ACTIVE)
    current_version = models.ForeignKey(
        'FieldVersion',
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower('name'), 'creator', name='unique_field_name_per_creator'),
        ]
        ordering = ['name', 'pk']

    def __str__(self):
        return f'{self.creator.username}/{self.name}'


class FieldVersion(ImmutablePublishedModel):
    definition = models.ForeignKey(FieldDefinition, on_delete=models.CASCADE, related_name='versions')
    version_number = models.PositiveIntegerField()
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, default='')
    field_type = models.CharField(max_length=24, choices=FieldType.choices)
    settings = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['definition', 'version_number'],
                name='unique_field_version_number',
            ),
        ]
        ordering = ['definition_id', 'version_number']

    def __str__(self):
        return f'{self.definition} v{self.version_number}'

    @property
    def field_key(self):
        return self.definition.key

    @property
    def label(self):
        return self.name


class FieldSynonym(ImmutablePublishedModel):
    source_version = models.ForeignKey(FieldVersion, on_delete=models.CASCADE, related_name='synonyms')
    target = models.ForeignKey(FieldDefinition, on_delete=models.PROTECT, related_name='synonym_sources')
    position = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['source_version', 'target'],
                name='unique_field_synonym_target',
            ),
            models.UniqueConstraint(
                fields=['source_version', 'position'],
                name='unique_field_synonym_position',
            ),
        ]
        ordering = ['position', 'pk']


class InterfaceDraftField(models.Model):
    draft = models.ForeignKey(InterfaceDraft, on_delete=models.CASCADE, related_name='fields')
    definition = models.ForeignKey(
        FieldDefinition,
        on_delete=models.PROTECT,
        related_name='draft_interface_bindings',
    )
    required = models.BooleanField(default=False)
    position = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['draft', 'definition'], name='unique_draft_field_definition'),
            models.UniqueConstraint(fields=['draft', 'position'], name='unique_draft_field_position'),
        ]
        ordering = ['position', 'pk']

    @property
    def field_key(self):
        return self.definition.key

    @property
    def label(self):
        return self.definition.current_version.name

    @property
    def field_type(self):
        return self.definition.current_version.field_type

    @property
    def settings(self):
        return self.definition.current_version.settings


class InterfaceField(ImmutablePublishedModel):
    version = models.ForeignKey(InterfaceVersion, on_delete=models.CASCADE, related_name='fields')
    definition = models.ForeignKey(
        FieldDefinition,
        on_delete=models.PROTECT,
        related_name='interface_bindings',
    )
    field_version = models.ForeignKey(
        FieldVersion,
        on_delete=models.PROTECT,
        related_name='interface_bindings',
    )
    required = models.BooleanField(default=False)
    position = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['version', 'definition'], name='unique_version_field_definition'),
            models.UniqueConstraint(fields=['version', 'position'], name='unique_version_field_position'),
        ]
        ordering = ['position', 'pk']

    @property
    def field_key(self):
        return self.definition.key

    @property
    def label(self):
        return self.field_version.name

    @property
    def field_type(self):
        return self.field_version.field_type

    @property
    def settings(self):
        return self.field_version.settings

    def get_field_type_display(self):
        return self.field_version.get_field_type_display()


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


class ThreadFieldValue(models.Model):
    thread = models.ForeignKey('events.Thread', on_delete=models.CASCADE, related_name='field_values')
    value = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class ThreadFieldBinding(models.Model):
    thread = models.ForeignKey('events.Thread', on_delete=models.CASCADE, related_name='field_bindings')
    definition = models.ForeignKey(
        FieldDefinition,
        on_delete=models.PROTECT,
        related_name='thread_bindings',
    )
    value = models.ForeignKey(ThreadFieldValue, on_delete=models.CASCADE, related_name='bindings')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['thread', 'definition'],
                name='unique_thread_field_binding',
            ),
        ]
        ordering = ['created_at', 'pk']


class ThreadDirectField(models.Model):
    thread = models.ForeignKey('events.Thread', on_delete=models.CASCADE, related_name='direct_fields')
    definition = models.ForeignKey(
        FieldDefinition,
        on_delete=models.PROTECT,
        related_name='direct_thread_implementations',
    )
    version = models.ForeignKey(
        FieldVersion,
        on_delete=models.PROTECT,
        related_name='direct_thread_implementations',
    )
    binding = models.ForeignKey(
        ThreadFieldBinding,
        on_delete=models.PROTECT,
        related_name='direct_implementations',
    )
    position = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['thread', 'definition'], name='unique_thread_direct_field'),
            models.UniqueConstraint(fields=['thread', 'position'], name='unique_thread_direct_field_position'),
        ]
        ordering = ['position', 'pk']

    @property
    def value(self):
        return self.binding.value.value

    @property
    def display_value(self):
        value = self.value
        if isinstance(value, bool):
            return 'はい' if value else 'いいえ'
        if isinstance(value, list):
            return ' / '.join(str(item) for item in value)
        return str(value)


class ThreadInterfaceValue(models.Model):
    implementation = models.ForeignKey(
        ThreadInterfaceImplementation,
        on_delete=models.CASCADE,
        related_name='values',
    )
    field = models.ForeignKey(InterfaceField, on_delete=models.PROTECT, related_name='thread_values')
    binding = models.ForeignKey(
        ThreadFieldBinding,
        on_delete=models.PROTECT,
        related_name='interface_values',
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['implementation', 'field'], name='unique_thread_interface_field_value'),
        ]

    @property
    def value(self):
        return self.binding.value.value

    @property
    def display_value(self):
        value = self.value
        if isinstance(value, bool):
            return 'はい' if value else 'いいえ'
        if isinstance(value, list):
            return ' / '.join(str(item) for item in value)
        return str(value)


class AccountInterfaceImplementation(models.Model):
    ACTIVE = 'active'
    FROZEN = 'frozen'
    PENDING = 'pending'
    STATE_CHOICES = [(ACTIVE, '有効'), (FROZEN, '凍結'), (PENDING, '復帰待ち')]
    state = models.CharField(max_length=16, choices=STATE_CHOICES, default=ACTIVE, db_default=ACTIVE)

    account = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='interface_implementations')
    interface = models.ForeignKey(Interface, on_delete=models.PROTECT, related_name='account_implementations')
    version = models.ForeignKey(InterfaceVersion, on_delete=models.PROTECT, related_name='account_implementations')
    position = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['account', 'interface'], name='unique_account_interface'),
            models.UniqueConstraint(fields=['account', 'position'], name='unique_account_interface_position'),
        ]
        ordering = ['position', 'pk']


class AccountFieldValue(models.Model):
    account = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='field_values')
    value = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class AccountFieldBinding(models.Model):
    # The one applied FieldVersion for this definition on this Account.
    version = models.ForeignKey(FieldVersion, null=True, on_delete=models.PROTECT, related_name='account_bindings')

    account = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='field_bindings')
    definition = models.ForeignKey(
        FieldDefinition,
        on_delete=models.PROTECT,
        related_name='account_bindings',
    )
    value = models.ForeignKey(AccountFieldValue, on_delete=models.CASCADE, related_name='bindings')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['account', 'definition'],
                name='unique_account_field_binding',
            ),
        ]
        ordering = ['created_at', 'pk']


class AccountDirectField(models.Model):
    account = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='direct_fields')
    definition = models.ForeignKey(
        FieldDefinition,
        on_delete=models.PROTECT,
        related_name='direct_account_implementations',
    )
    version = models.ForeignKey(
        FieldVersion,
        on_delete=models.PROTECT,
        related_name='direct_account_implementations',
    )
    binding = models.ForeignKey(
        AccountFieldBinding,
        on_delete=models.PROTECT,
        related_name='direct_implementations',
    )
    position = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['account', 'definition'], name='unique_account_direct_field'),
            models.UniqueConstraint(fields=['account', 'position'], name='unique_account_direct_field_position'),
        ]
        ordering = ['position', 'pk']

    @property
    def value(self):
        return self.binding.value.value

    @property
    def display_value(self):
        value = self.value
        if isinstance(value, bool):
            return 'はい' if value else 'いいえ'
        if isinstance(value, list):
            return ' / '.join(str(item) for item in value)
        return str(value)


class AccountInterfaceValue(models.Model):
    implementation = models.ForeignKey(
        AccountInterfaceImplementation,
        on_delete=models.CASCADE,
        related_name='values',
    )
    field = models.ForeignKey(InterfaceField, on_delete=models.PROTECT, related_name='account_values')
    binding = models.ForeignKey(
        AccountFieldBinding,
        on_delete=models.PROTECT,
        related_name='interface_values',
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['implementation', 'field'], name='unique_account_interface_field_value'),
        ]

    @property
    def value(self):
        return self.binding.value.value

    @property
    def display_value(self):
        value = self.value
        if isinstance(value, bool):
            return 'はい' if value else 'いいえ'
        if isinstance(value, list):
            return ' / '.join(str(item) for item in value)
        return str(value)
