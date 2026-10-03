from django.contrib import admin

from .models import Board, BoardPlacement, Collection, Room, RoomMembership, RoomPlacement


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'last_activity_at', 'created_at')
    search_fields = ('name', 'description', 'owner__username')


@admin.register(RoomMembership)
class RoomMembershipAdmin(admin.ModelAdmin):
    list_display = ('room', 'account', 'joined_at')


@admin.register(RoomPlacement)
class RoomPlacementAdmin(admin.ModelAdmin):
    list_display = ('room', 'latitude', 'longitude', 'updated_at')


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ('name', 'account', 'room', 'is_main', 'last_activity_at')


@admin.register(Board)
class BoardAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner_account', 'owner_room', 'last_activity_at')


@admin.register(BoardPlacement)
class BoardPlacementAdmin(admin.ModelAdmin):
    list_display = ('board', 'kind', 'collection', 'latitude', 'longitude')
