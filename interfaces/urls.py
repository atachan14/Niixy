from django.urls import path

from . import views

app_name = 'interfaces'

urlpatterns = [
    path('manage/', views.management_list, name='management-list'),
    path('manage/drafts/<int:draft_id>/', views.draft_detail, name='draft-detail'),
    path('manage/<int:interface_id>/', views.published_detail, name='published-detail'),
    path('manage/drafts/<int:draft_id>/add-requires/', views.add_require_list, name='add-require-list'),
    path('manage/drafts/<int:draft_id>/add-requires/<int:interface_id>/', views.add_require_detail, name='add-require-detail'),
    path('drafts/new/', views.draft_create, name='draft-create'),
    path('drafts/<int:draft_id>/', views.draft_update, name='draft-update'),
    path('drafts/<int:draft_id>/discard/', views.draft_discard, name='draft-discard'),
    path('<int:interface_id>/edit/', views.draft_edit, name='draft-edit'),
    path('<int:interface_id>/delete/', views.interface_delete, name='delete'),
    path('<int:interface_id>/restore/', views.interface_restore, name='restore'),
]
