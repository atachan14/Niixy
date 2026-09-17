from django.contrib import admin

from .models import Event, Locality, Station


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('title', 'creator', 'starts_at', 'capacity', 'created_at')
    list_filter = ('starts_at', 'created_at')
    search_fields = ('title', 'description')
    ordering = ('starts_at',)


@admin.register(Station)
class StationAdmin(admin.ModelAdmin):
    list_display = ('name', 'line_name', 'operator_name', 'station_code')
    search_fields = ('name', 'line_name', 'operator_name')
    ordering = ('name', 'line_name')


@admin.register(Locality)
class LocalityAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'kind')
    list_filter = ('kind',)
    search_fields = ('name', 'full_name')
    ordering = ('kind', 'full_name')
