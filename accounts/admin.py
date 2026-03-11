from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from .models import InviteCode, UserProfile


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    fields = ("is_approved", "invite_code_used")
    raw_id_fields = ("invite_code_used",)


class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = BaseUserAdmin.list_display + ("is_approved_display",)
    list_filter = BaseUserAdmin.list_filter + ("profile__is_approved",)

    @admin.display(boolean=True, description="Approved")
    def is_approved_display(self, obj):
        try:
            return obj.profile.is_approved
        except UserProfile.DoesNotExist:
            return False

    @admin.action(description="Approve selected users")
    def approve_users(self, request, queryset):
        UserProfile.objects.filter(user__in=queryset).update(is_approved=True)

    @admin.action(description="Revoke approval for selected users")
    def revoke_users(self, request, queryset):
        UserProfile.objects.filter(user__in=queryset).update(is_approved=False)

    actions = [approve_users, revoke_users]


@admin.register(InviteCode)
class InviteCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "label", "created_by", "times_used", "max_uses", "is_active", "expires_at", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("code", "label")
    readonly_fields = ("code", "times_used", "created_at")


admin.site.unregister(User)
admin.site.register(User, UserAdmin)
