from django.urls import path

from . import views
from rooms import views as board_views

app_name = 'events'

urlpatterns = [
    path('', views.map_view, name='map'),
    path('boards/new/', board_views.map_board_create, name='board-create'),
    path('boards/<int:board_id>/pane/', board_views.board_threads, name='board-pane'),
    path('boards/<int:board_id>/threads/new/', board_views.board_thread_create, name='board-thread-create'),
    path('boards/<int:board_id>/threads/<int:thread_id>/', board_views.map_board_thread_detail, name='board-thread-detail'),
    path('healthz/', views.healthcheck, name='healthcheck'),
    path('threads/new/', views.thread_create, name='thread-create'),
    path('threads/<int:thread_id>/posts/', views.thread_post_create, name='thread-post-create'),
    path('api/filter-preferences/', views.filter_preferences_update, name='filter-preferences'),
    path('api/threads/search/', views.thread_search, name='thread-search'),
    path('api/locations/', views.location_search, name='location-search'),
]
