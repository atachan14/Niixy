from django.urls import path

from . import views
from . import reviews, mutes
from rooms import views as board_views
from interfaces import layout_views

app_name = 'accounts'

urlpatterns = [
    path('<str:username>/mute/', mutes.change, name='mute-change'),
    path('<str:username>/reviews/', reviews.listing, name='reviews'),
    path('<str:username>/reviews/editor/', reviews.editor, name='review-editor'),
    path('<str:username>/reviews/save/', reviews.save, name='review-save'),
    path('<str:username>/reviews/delete/', reviews.delete, name='review-delete'),
    path('<str:username>/layout/change/', layout_views.apply, name='layout-change'),
    path('account-conditions/', views.account_condition_list, name='account-condition-list'),
    path('account-conditions/accounts/', views.account_condition_search, name='account-condition-search'),
    path('account-conditions/rooms/', views.account_condition_room_search, name='account-condition-room-search'),
    path('account-conditions/save/', views.account_condition_save, name='account-condition-save'),
    path('account-conditions/<int:condition_id>/delete/', views.account_condition_delete, name='account-condition-delete'),
    path('signup/', views.signup, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('<str:username>/applied/', views.account_applied, name='applied'),
    path('<str:username>/applied/data/', views.account_applied_data, name='applied-data'),
    path('<str:username>/applied/change/', views.account_applied_change, name='applied-change'),
    path('<str:username>/boards/', board_views.room_boards, name='boards'),
    path('<str:username>/collections/new/', board_views.collection_create, name='collection-create'),
    path('<str:username>/collections/<int:collection_id>/edit/', board_views.collection_edit, name='collection-edit'),
    path('<str:username>/collections/<int:collection_id>/delete/', board_views.collection_delete, name='collection-delete'),
    path('<str:username>/collections/<int:collection_id>/boards/new/', board_views.board_create, name='board-create'),
    path('<str:username>/boards/<int:board_id>/', board_views.board_threads, name='board-threads'),
    path('<str:username>/boards/<int:board_id>/edit/', board_views.board_edit, name='board-edit'),
    path('<str:username>/boards/<int:board_id>/delete/', board_views.board_delete, name='board-delete'),
    path('<str:username>/boards/<int:board_id>/threads/new/', board_views.board_thread_create, name='board-thread-create'),
    path('<str:username>/board-threads/<int:thread_id>/', board_views.account_board_thread_detail, name='board-thread-detail'),
    path('<str:username>/pane/', views.account_pane, name='pane'),
    path('<str:username>/threads/', views.account_thread_pane, name='thread-pane'),
    path('<str:username>/threads/<int:thread_id>/', views.account_thread_detail, name='thread-detail'),
    path('<str:username>/responses/', views.account_response_pane, name='response-pane'),
    path('<str:username>/rooms/', views.account_room_pane, name='room-pane'),
    path('<str:username>/modules/', views.account_module_pane, name='module-pane'),
    path('<str:username>/modules/fields/<int:field_id>/', views.account_module_field_detail, name='module-field-detail'),
    path('<str:username>/modules/interfaces/<int:interface_id>/', views.account_module_interface_detail, name='module-interface-detail'),
    path('<str:username>/', views.account_page, name='detail'),
]
