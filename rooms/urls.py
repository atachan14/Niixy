from django.urls import path

from . import views, reviews, mutes

app_name = 'rooms'

urlpatterns = [
    path('<int:room_id>/mute/', mutes.change, name='mute-change'),
    path('<int:room_id>/reviews/', reviews.listing, name='reviews'),
    path('<int:room_id>/reviews/editor/', reviews.editor, name='review-editor'),
    path('<int:room_id>/reviews/save/', reviews.save, name='review-save'),
    path('<int:room_id>/reviews/delete/', reviews.delete, name='review-delete'),
    path('new/', views.room_create, name='create'),
    path('<int:room_id>/', views.room_detail, name='detail'),
    path('<int:room_id>/pane/', views.room_pane, name='pane'),
    path('<int:room_id>/edit/', views.room_edit, name='edit'),
    path('<int:room_id>/join/', views.room_join, name='join'),
    path('<int:room_id>/leave/', views.room_leave, name='leave'),
    path('<int:room_id>/members/', views.room_members, name='members'),
    path('<int:room_id>/boards/', views.room_boards, name='boards'),
    path('<int:room_id>/collections/new/', views.collection_create, name='collection-create'),
    path('<int:room_id>/collections/<int:collection_id>/edit/', views.collection_edit, name='collection-edit'),
    path('<int:room_id>/collections/<int:collection_id>/delete/', views.collection_delete, name='collection-delete'),
    path('<int:room_id>/collections/<int:collection_id>/boards/new/', views.board_create, name='board-create'),
    path('<int:room_id>/boards/<int:board_id>/', views.board_threads, name='board-threads'),
    path('<int:room_id>/boards/<int:board_id>/edit/', views.board_edit, name='board-edit'),
    path('<int:room_id>/boards/<int:board_id>/delete/', views.board_delete, name='board-delete'),
    path('<int:room_id>/boards/<int:board_id>/threads/new/', views.board_thread_create, name='board-thread-create'),
    path('<int:room_id>/threads/<int:thread_id>/', views.room_thread_detail, name='thread-detail'),
]
