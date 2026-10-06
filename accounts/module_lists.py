"""Public definition collections. No Applied values, drafts, or placement writes."""
from .content_lists import MODULE_KINDS, KINDS, describe_target, public_modules, prepare_list, route
from .mutes import muted_account_ids
from config.pagination import paginate_summary_list
from urllib.parse import urlencode


def module_collections(request, account):
    muted = set(muted_account_ids(request.user))
    def summaries(kind, targets):
        return [value for target in targets if target.creator_id not in muted
                for value in [describe_target(kind, target, request.user)] if value]

    groups = [{'key': 'self', 'name': '自作', 'summaries': []},
              {'key': 'fav', 'name': 'fav', 'summaries': []},
              {'key': 'bad', 'name': 'bad', 'summaries': []}]
    for kind in MODULE_KINDS:
        public = public_modules(kind)
        groups[0]['summaries'] += summaries(kind, public.filter(creator=account).order_by('current_version__name', 'pk'))
        for group in groups[1:]:
            groups_by_author = public.filter(ratings__author=account, ratings__sentiment=group['key'])
            group['summaries'] += summaries(kind, groups_by_author.order_by('-ratings__updated_at', 'pk'))
    for item in account.interface_lists.order_by('created_at', 'pk'):
        prepare_list('interface', item)
        group = {'key': 'list-' + str(item.pk), 'name': item.name, 'list_id': item.pk,
                 'detail_url': route('interface', 'list-detail', item.pk), 'summaries': []}
        for kind in MODULE_KINDS:
            refs = KINDS[kind].reference.objects.filter(interface_list=item).select_related('target__current_version')
            group['summaries'] += summaries(kind, [r.target for r in refs if r.target])
        groups.append(group)
    active = (request.GET.get('collection', 'self'), request.GET.get('type', 'element'), request.GET.get('subtype', 'field'))
    categories = [('element', 'field'), ('element', 'computed_field'), ('element', 'action'),
                  ('interface', 'account'), ('interface', 'room'), ('interface', 'thread'), ('interface', 'thread_post'),
                  ('layout', 'account'), ('layout', 'thread_post'), ('layout', 'room')]
    for group in groups:
        group['pages'] = []
        for type_, subtype in categories:
            values = [s for s in group['summaries'] if s['module_type'] == type_ and s['module_subtype'] == subtype]
            group['pages'].append({'type': type_, 'subtype': subtype,
                'page': paginate_summary_list(values, request.GET.get('page') if active == (group['key'], type_, subtype) else 1),
                'query': urlencode({'type': type_, 'subtype': subtype, 'collection': group['key']})})
    return {'module_collections': groups, 'module_fetch_url': request.path,
            'module_lists_url': route('interface', 'list-index', account.username)}
