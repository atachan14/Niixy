from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    path('account-conditions/accounts/', views.account_condition_search, name='account-condition-search'),
    path('account-conditions/save/', views.account_condition_save, name='account-condition-save'),
    path('account-conditions/<int:condition_id>/delete/', views.account_condition_delete, name='account-condition-delete'),
    path('signup/', views.signup, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('<str:username>/threads/', views.account_thread_pane, name='thread-pane'),
    path('<str:username>/threads/<int:thread_id>/', views.account_thread_detail, name='thread-detail'),
    path('<str:username>/responses/', views.account_response_pane, name='response-pane'),
    path('<str:username>/rooms/', views.account_room_pane, name='room-pane'),
    path('<str:username>/modules/', views.account_module_pane, name='module-pane'),
    path('<str:username>/modules/fields/<int:field_id>/', views.account_module_field_detail, name='module-field-detail'),
    path('<str:username>/modules/interfaces/<int:interface_id>/', views.account_module_interface_detail, name='module-interface-detail'),
    path('<str:username>/', views.account_page, name='detail'),
]
