from django.contrib import admin
from .models import SocialMediaLink

@admin.register(SocialMediaLink)
class SocialMediaLinkAdmin(admin.ModelAdmin):
    """
    Admin configuration for SocialMediaLink.
    Allows editing URLs and toggling active status directly from the list view.
    """
    list_display = ('platform', 'url', 'is_active')
    list_editable = ('url', 'is_active')
    ordering = ('platform',)

    def has_add_permission(self, request):
        # Prevent adding more than the standard choice options
        try:
            if SocialMediaLink.objects.count() >= len(SocialMediaLink.PLATFORM_CHOICES):
                return False
        except Exception:
            pass
        return True

    def has_delete_permission(self, request, obj=None):
        # Disable manual deletion of these standard platform slots to maintain dashboard stability
        return False
