from django.contrib import admin

from keys.models import ApiKey


@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    list_display = ["name", "prefix", "user", "is_active", "created_at", "last_used_at"]
    list_filter = ["is_active", "created_at"]
    search_fields = ["name", "prefix", "user__username"]
    readonly_fields = ["prefix", "hashed_key", "created_at", "last_used_at", "revoked_at"]
    raw_id_fields = ["user"]
