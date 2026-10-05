from django.conf import settings
from django.db import migrations


def initialize_existing_accounts(apps, schema_editor):
    """Seed only untouched Accounts; never reuse or alter existing collections."""
    alias = schema_editor.connection.alias
    Account = apps.get_model(settings.AUTH_USER_MODEL)
    Collection = apps.get_model('rooms', 'Collection')
    Board = apps.get_model('rooms', 'Board')
    Placement = apps.get_model('rooms', 'BoardPlacement')
    Condition = apps.get_model('rooms', 'BoardPolicyCondition')
    existing = Collection.objects.using(alias).filter(account_id__isnull=False).values('account_id')
    accounts = Account.objects.using(alias).exclude(pk__in=existing).order_by('pk')
    for account in accounts.iterator():
        Collection.objects.using(alias).create(account_id=account.pk, name='未分類', is_uncategorized=True)
        main = Collection.objects.using(alias).create(account_id=account.pk, name='Main')
        board = Board.objects.using(alias).create(name='日記')
        Placement.objects.using(alias).create(board_id=board.pk, kind='collection', collection_id=main.pk)
        Condition.objects.using(alias).bulk_create([
            Condition(board_id=board.pk, capability='view', decision='allow', kind='default',
                      definition={'code': code}, label=label)
            for code, label in [('guest', 'Guest'), ('account', 'NiixyAccount')]
        ] + [Condition(board_id=board.pk, capability='create_thread', decision='allow', kind='account',
                       definition={'account_id': account.pk}, label=f'@{account.username}')])


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('rooms', '0008_boardpolicycondition'),
    ]
    # Irreversible: a rollback must not remove user-editable Collections or Boards.
    operations = [migrations.RunPython(initialize_existing_accounts)]
