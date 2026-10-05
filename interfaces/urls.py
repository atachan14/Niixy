from django.urls import path

from . import views
from . import layout_views

app_name = 'interfaces'

urlpatterns = [
    path('layouts/drafts/new/', layout_views.draft_create, name='layout-draft-create'),
    path('layouts/drafts/<int:draft_id>/', layout_views.draft_detail, name='layout-draft-detail'),
    path('layouts/drafts/<int:draft_id>/save/', layout_views.draft_save, name='layout-draft-save'),
    path('layouts/drafts/<int:draft_id>/discard/', layout_views.draft_discard, name='layout-draft-discard'),
    path('layouts/<int:layout_id>/', layout_views.detail, name='layout-detail'),
    path('layouts/<int:layout_id>/edit/', layout_views.edit, name='layout-edit'),
    path('layouts/require/<str:kind>/<int:definition_id>/', layout_views.requirement_detail, name='layout-requirement'),
    path('manage/modules/', views.module_management_list, name='module-management-list'),
    path('manage/modules/fields/search/', views.field_search, name='field-search'),
    path('manage/drafts/<int:draft_id>/', views.draft_detail, name='draft-detail'),
    path('manage/<int:interface_id>/', views.published_detail, name='published-detail'),
    path('<int:interface_id>/detail/', views.definition_detail, name='definition-detail'),
    path('manage/drafts/<int:draft_id>/add-fields/', views.add_field_list, name='add-field-list'),
    path('manage/drafts/<int:draft_id>/add-fields/<int:field_id>/', views.add_field_detail, name='add-field-detail'),
    path('manage/fields/new/', views.field_create, name='field-create'),
    path('manage/fields/new/publish/', views.field_publish, name='field-publish-new'),
    path('manage/fields/<int:field_id>/', views.field_detail, name='field-detail'),
    path('manage/fields/<int:field_id>/edit/', views.field_edit, name='field-edit'),
    path('manage/fields/<int:field_id>/publish/', views.field_publish, name='field-publish'),
    path('manage/fields/<int:field_id>/delete/', views.field_delete, name='field-delete'),
    path('manage/fields/<int:field_id>/restore/', views.field_restore, name='field-restore'),
    path('manage/fields/add-synonyms/', views.add_synonym_list, name='add-synonym-list'),
    path('manage/fields/add-synonyms/<int:field_id>/', views.add_synonym_detail, name='add-synonym-detail'),
    path('drafts/new/', views.draft_create, name='draft-create'),
    path('drafts/<int:draft_id>/', views.draft_update, name='draft-update'),
    path('drafts/<int:draft_id>/discard/', views.draft_discard, name='draft-discard'),
    path('<int:interface_id>/edit/', views.draft_edit, name='draft-edit'),
    path('<int:interface_id>/delete/', views.interface_delete, name='delete'),
    path('<int:interface_id>/restore/', views.interface_restore, name='restore'),
]
