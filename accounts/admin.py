from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from .models import UserProfile


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    fields = ("is_approved",)


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


admin.site.unregister(User)
admin.site.register(User, UserAdmin)
