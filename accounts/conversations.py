"""Account conversation categories; references never change placement or Policy."""
from types import SimpleNamespace
from urllib.parse import urlencode
from django.core.paginator import Paginator
from django.urls import reverse
from events.models import Thread, ThreadPost, ThreadAccessRule
from events.services import thread_queryset, prepare_thread_for_view
from .content_lists import KINDS, list_query, prepare_list
from .mutes import filter_muted, prepare_muted_posts, muted_account_ids


def prepare_items(query, kind, viewer):
    if kind == 'thread':
        items = list(filter_muted(query, viewer))
        for thread in items:
            prepare_thread_for_view(thread, viewer)
        return items
    posts = list(query.select_related('thread', 'creator__niixy_profile').prefetch_related(
        'thread__access_rules', 'thread__policy_conditions', 'thread__posts'))
    prepare_muted_posts(posts, viewer)
    items, denied = [], set()
    muted = set(muted_account_ids(viewer))
    for post in posts:
        if post.thread.creator_id in muted:
            continue
        post.thread.can_view = post.thread.allows(viewer, ThreadAccessRule.VIEW)
        if not post.thread.can_view:
            if post.thread_id in denied:
                continue
            denied.add(post.thread_id)
        items.append(post)
    return items


def pane_context(request, account, kind):
    spec = KINDS[kind]
    query = thread_queryset() if kind == 'thread' else ThreadPost.objects.filter(number__gt=1)
    page_key = 'created_page' if kind == 'thread' else 'response_page'
    active = request.GET.get('tab', 'created')
    sources = [('created', '作成', query.filter(creator=account).order_by('-created_at'), None)]
    for sentiment in ['fav', 'bad']:
        sources.append((sentiment, sentiment, query.filter(ratings__author=account, ratings__sentiment=sentiment).order_by('-ratings__updated_at', '-pk'), None))
    for item in list_query(kind).filter(owner=account).order_by('created_at', 'pk'):
        prepare_list(kind, item)
        sources.append(('list-'+str(item.pk), item.name,
            query.filter(**{'list_references__'+spec.list_field:item}).order_by('list_references__created_at', 'pk'), item))
    if active not in {source[0] for source in sources}: active = 'created'
    tabs = []
    for key, label, source, content_list in sources:
        rows = prepare_items(source, kind, request.user)
        if content_list:
            by_id = {row.pk:row for row in rows}
            rows = [by_id[target_id] if target_id is not None else SimpleNamespace(deleted=True)
                    for target_id in content_list.references.order_by('created_at', 'pk').values_list('target_id', flat=True)
                    if target_id is None or target_id in by_id]
        page = Paginator(rows, 10).get_page(request.GET.get(page_key) if key == active else 1)
        url = reverse('accounts:'+kind+'-pane', args=[account.username])
        tabs.append({'key':key, 'label':label, 'page':page, 'content_list':content_list,
            'previous_url':url+'?'+urlencode({'tab':key,page_key:page.previous_page_number()}) if page.has_previous() else '',
            'next_url':url+'?'+urlencode({'tab':key,page_key:page.next_page_number()}) if page.has_next() else ''})
    return {'account':account,'kind':kind,'tabs':tabs,'active_tab':active,'created_page' if kind=='thread' else 'response_page':tabs[0]['page'],
        'integrated_fetch':request.get_full_path()}
