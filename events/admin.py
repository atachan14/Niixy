from django.contrib import admin

from .models import Locality, Station, Thread, ThreadAccessRule, ThreadPlacement, ThreadPost


class ThreadPostInline(admin.TabularInline):
    model = ThreadPost
    extra = 0
    readonly_fields = ('number', 'creator', 'body', 'created_at')


@admin.register(Thread)
class ThreadAdmin(admin.ModelAdmin):
    list_display = ('title', 'creator', 'last_activity_at', 'created_at')
    search_fields = ('title',)
    inlines = [ThreadPostInline]


@admin.register(ThreadPlacement)
class ThreadPlacementAdmin(admin.ModelAdmin):
    list_display = ('thread', 'kind', 'latitude', 'longitude', 'created_at')


@admin.register(ThreadAccessRule)
class ThreadAccessRuleAdmin(admin.ModelAdmin):
    list_display = ('thread', 'capability', 'audience')
    list_filter = ('capability', 'audience')


@admin.register(Station)
class StationAdmin(admin.ModelAdmin):
    list_display = ('name', 'line_name', 'operator_name', 'station_code')
    search_fields = ('name', 'line_name', 'operator_name')


@admin.register(Locality)
class LocalityAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'kind')
    list_filter = ('kind',)
    search_fields = ('name', 'full_name')
