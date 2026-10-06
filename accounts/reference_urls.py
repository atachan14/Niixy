from django.urls import path
from . import content_lists as views

app_name = 'references'
urlpatterns = []
for kind, plural in [('board', 'boards'), ('interface', 'interfaces'), ('field', 'fields'), ('layout', 'layouts'), ('thread', 'threads'), ('response', 'responses')]:
    kwargs = {'kind': kind}
    paths = [
        path(plural + '/<int:target_id>/', views.target_page, kwargs, name=kind + '-page'),
        path(plural + '/<int:target_id>/' + ('reference/' if kind == 'board' else 'pane/'), views.target_pane, kwargs, name=kind + '-pane'),
        path(plural + '/<int:target_id>/references/threads/<int:thread_id>/', views.target_thread, kwargs, name=kind + '-thread'),
        path(plural + '/<int:target_id>/rating/', views.rate, kwargs, name=kind + '-rating'),
        path(plural + '/<int:target_id>/ratings/', views.ratings, kwargs, name=kind + '-ratings'),
        path(plural + '/<int:target_id>/picker/', views.picker, kwargs, name=kind + '-picker'),
        path(kind + '-lists/create/', views.create, kwargs, name=kind + '-list-create'),
        path(kind + '-lists/<int:list_id>/', views.list_page, kwargs, name=kind + '-list-page'),
        path(kind + '-lists/<int:list_id>/pane/', views.detail, kwargs, name=kind + '-list-detail'),
        path(kind + '-lists/<int:list_id>/rename/', views.rename, kwargs, name=kind + '-list-rename'),
        path(kind + '-lists/<int:list_id>/delete/', views.delete, kwargs, name=kind + '-list-delete'),
        path(kind + '-lists/<int:list_id>/add/', views.add, kwargs, name=kind + '-list-add'),
        path(kind + '-lists/<int:list_id>/references/<int:reference_id>/remove/', views.remove, kwargs, name=kind + '-list-remove'),
        path('accounts/<str:username>/' + kind + '-lists/', views.listing, kwargs, name=kind + '-list-index'),
    ]

    if kind in {'field', 'layout'}:
        paths = [p for p in paths if '-list-' not in p.name or p.name.endswith('-list-remove')]
    urlpatterns += paths
