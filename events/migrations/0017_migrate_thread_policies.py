"""Copy old saved rules only; intentionally do not persist the old Room gate."""
import uuid
from django.db import migrations


def copy_saved_rules(apps, schema_editor):
    Rule = apps.get_model('events', 'ThreadAccessRule')
    Condition = apps.get_model('events', 'ThreadPolicyCondition')
    database = schema_editor.connection.alias
    already_migrated = set(Condition.objects.using(database).values_list('thread_id', flat=True))
    batch = []
    for rule in Rule.objects.using(database).filter(capability__in=['view', 'write']).iterator(chunk_size=2000):
        if rule.thread_id in already_migrated:
            continue
        batch.append(Condition(
            thread_id=rule.thread_id, capability=rule.capability, decision='allow',
            group_key=uuid.uuid5(uuid.NAMESPACE_URL, f'niixy:thread-rule:{rule.pk}'),
            position=0, kind='default', definition={'code': rule.audience},
            label='Guest' if rule.audience == 'guest' else 'NiixyAccount',
        ))
        if len(batch) >= 1000:
            Condition.objects.using(database).bulk_create(batch)
            batch = []
    if batch:
        Condition.objects.using(database).bulk_create(batch)


class Migration(migrations.Migration):
    dependencies = [('events', '0016_threadpolicycondition')]
    operations = [migrations.RunPython(copy_saved_rules, migrations.RunPython.noop)]
