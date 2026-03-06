from django.conf import settings
from django.db import models


class RequestLog(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="request_logs",
    )
    api_key_prefix = models.CharField(max_length=8)
    endpoint = models.CharField(max_length=200)
    model = models.CharField(max_length=100, blank=True, default="")
    status_code = models.IntegerField()
    latency_ms = models.IntegerField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")
    streaming = models.BooleanField(default=False)
    request_size = models.IntegerField(null=True, blank=True)
    response_size = models.IntegerField(null=True, blank=True)
    tokens_in = models.IntegerField(null=True, blank=True)
    tokens_out = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["user", "-timestamp"]),
            models.Index(fields=["api_key_prefix", "-timestamp"]),
        ]

    def __str__(self):
        return f"{self.timestamp} {self.endpoint} {self.status_code}"


class DailyAggregate(models.Model):
    date = models.DateField(db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="daily_aggregates",
    )
    api_key_prefix = models.CharField(max_length=8, blank=True, default="")
    calls_total = models.IntegerField(default=0)
    calls_generate = models.IntegerField(default=0)
    calls_chat = models.IntegerField(default=0)
    calls_embeddings = models.IntegerField(default=0)
    calls_2xx = models.IntegerField(default=0)
    calls_4xx = models.IntegerField(default=0)
    calls_5xx = models.IntegerField(default=0)
    avg_latency_ms = models.FloatField(default=0)
    tokens_in_total = models.IntegerField(default=0)
    tokens_out_total = models.IntegerField(default=0)

    class Meta:
        unique_together = ["date", "user", "api_key_prefix"]
        ordering = ["-date"]

    def __str__(self):
        return f"{self.date} {self.user} ({self.api_key_prefix})"
