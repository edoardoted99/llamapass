import hashlib
import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone

KEY_PREFIX_LENGTH = 8
KEY_SECRET_LENGTH = 32  # 32 bytes = 64 hex chars


class ApiKey(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="api_keys",
    )
    name = models.CharField(max_length=100)
    prefix = models.CharField(max_length=KEY_PREFIX_LENGTH, unique=True, db_index=True)
    hashed_key = models.CharField(max_length=128)
    is_active = models.BooleanField(default=True)
    allowed_models = models.JSONField(default=list, blank=True)
    rate_limit = models.CharField(max_length=20, blank=True, default="")
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.prefix}...)"

    @staticmethod
    def generate_key():
        """Generate a new API key. Returns (full_key, prefix, hashed_key)."""
        raw_secret = secrets.token_hex(KEY_SECRET_LENGTH)
        prefix = raw_secret[:KEY_PREFIX_LENGTH]
        full_key = f"oah_{raw_secret}"
        hashed_key = hashlib.sha256(full_key.encode()).hexdigest()
        return full_key, prefix, hashed_key

    @staticmethod
    def hash_key(full_key):
        return hashlib.sha256(full_key.encode()).hexdigest()

    def verify(self, full_key):
        return self.hashed_key == self.hash_key(full_key)

    def revoke(self):
        self.is_active = False
        self.revoked_at = timezone.now()
        self.save(update_fields=["is_active", "revoked_at"])

    def touch(self):
        self.last_used_at = timezone.now()
        ApiKey.objects.filter(pk=self.pk).update(last_used_at=self.last_used_at)

    @property
    def is_expired(self):
        if self.expires_at is None:
            return False
        return timezone.now() >= self.expires_at

    def get_rate_limit(self):
        return self.rate_limit or settings.DEFAULT_RATE_LIMIT
