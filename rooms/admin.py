from django.contrib import admin

from .models import Board, BoardPlacement, BoardPolicyCondition, Collection, Room, RoomMembership, RoomPlacement


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
    list_display = ('name', 'account', 'room', 'is_uncategorized', 'last_activity_at')


@admin.register(Board)
class BoardAdmin(admin.ModelAdmin):
    list_display = ('name', 'placement_target', 'last_activity_at')

    @admin.display(description='配置先')
    def placement_target(self, board):
        try:
            placement = board.placement
        except BoardPlacement.DoesNotExist:
            return '未配置'
        return placement.collection or f'{placement.latitude}, {placement.longitude}'


@admin.register(BoardPlacement)
class BoardPlacementAdmin(admin.ModelAdmin):
    list_display = ('board', 'kind', 'collection', 'latitude', 'longitude')


@admin.register(BoardPolicyCondition)
class BoardPolicyConditionAdmin(admin.ModelAdmin):
    list_display = ('board', 'capability', 'decision', 'label', 'group_key', 'position')
