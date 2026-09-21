from django.urls import path

from . import views

app_name = 'events'

urlpatterns = [
    path('', views.map_view, name='map'),
    path('healthz/', views.healthcheck, name='healthcheck'),
    path('threads/new/', views.thread_create, name='thread-create'),
    path('threads/<int:thread_id>/posts/', views.thread_post_create, name='thread-post-create'),
    path('api/filter-preferences/', views.filter_preferences_update, name='filter-preferences'),
    path('api/locations/', views.location_search, name='location-search'),
]
