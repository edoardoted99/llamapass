from django.contrib import admin

from usage.models import DailyAggregate, RequestLog


@admin.register(RequestLog)
class RequestLogAdmin(admin.ModelAdmin):
    list_display = [
        "timestamp", "user", "api_key_prefix", "endpoint", "model",
        "status_code", "latency_ms", "tokens_in", "tokens_out",
    ]
    list_filter = ["status_code", "endpoint", "streaming"]
    search_fields = ["api_key_prefix", "user__username", "model"]
    readonly_fields = [
        "timestamp", "user", "api_key_prefix", "endpoint", "model",
        "status_code", "latency_ms", "ip_address", "user_agent",
        "streaming", "request_size", "response_size", "tokens_in", "tokens_out",
    ]
    date_hierarchy = "timestamp"


@admin.register(DailyAggregate)
class DailyAggregateAdmin(admin.ModelAdmin):
    list_display = [
        "date", "user", "api_key_prefix", "calls_total",
        "calls_chat", "calls_generate", "calls_embeddings",
        "tokens_in_total", "tokens_out_total",
    ]
    list_filter = ["date"]
    search_fields = ["user__username", "api_key_prefix"]
    date_hierarchy = "date"
