from django.contrib import admin

from .models import Interface, InterfaceDraft, InterfaceField, InterfaceRequirement, InterfaceVersion


admin.site.register(Interface)
admin.site.register(InterfaceDraft)
class ImmutablePublishedAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return ()
        return tuple(field.name for field in self.model._meta.fields)

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(InterfaceVersion, ImmutablePublishedAdmin)
admin.site.register(InterfaceField, ImmutablePublishedAdmin)
admin.site.register(InterfaceRequirement, ImmutablePublishedAdmin)
