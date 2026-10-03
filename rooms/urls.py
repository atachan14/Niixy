from django.urls import path

from . import views

app_name = 'rooms'

urlpatterns = [
    path('new/', views.room_create, name='create'),
    path('<int:room_id>/', views.room_detail, name='detail'),
    path('<int:room_id>/pane/', views.room_pane, name='pane'),
    path('<int:room_id>/edit/', views.room_edit, name='edit'),
    path('<int:room_id>/join/', views.room_join, name='join'),
    path('<int:room_id>/leave/', views.room_leave, name='leave'),
    path('<int:room_id>/members/', views.room_members, name='members'),
    path('<int:room_id>/boards/', views.room_boards, name='boards'),
    path('<int:room_id>/boards/<int:board_id>/', views.board_threads, name='board-threads'),
    path('<int:room_id>/boards/<int:board_id>/threads/new/', views.board_thread_create, name='board-thread-create'),
    path('<int:room_id>/threads/<int:thread_id>/', views.room_thread_detail, name='thread-detail'),
]
