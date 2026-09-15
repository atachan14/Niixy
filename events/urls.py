from django.urls import path

from . import views

app_name = 'events'

urlpatterns = [
    path('', views.map_view, name='map'),
    path('healthz/', views.healthcheck, name='healthcheck'),
    path('events/new/', views.event_create, name='create'),
    path('api/locations/', views.location_search, name='location-search'),
]
