from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    path('signup/', views.signup, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('<str:username>/threads/', views.account_thread_pane, name='thread-pane'),
    path('<str:username>/threads/<int:thread_id>/', views.account_thread_detail, name='thread-detail'),
    path('<str:username>/', views.account_page, name='detail'),
]
