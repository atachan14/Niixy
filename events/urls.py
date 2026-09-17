from django.urls import path

from . import views

app_name = 'events'

urlpatterns = [
    path('', views.map_view, name='map'),
    path('healthz/', views.healthcheck, name='healthcheck'),
    path('events/new/', views.event_create, name='create'),
    path('events/<int:event_id>/edit/', views.event_update, name='update'),
    path('events/<int:event_id>/delete/', views.event_delete, name='delete'),
    path('api/filter-preferences/', views.filter_preferences_update, name='filter-preferences'),
    path('api/locations/', views.location_search, name='location-search'),
]
