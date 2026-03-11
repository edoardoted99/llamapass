import secrets

from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    is_approved = models.BooleanField(default=False)
    invite_code_used = models.ForeignKey(
        "InviteCode",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="users_invited",
    )

    def __str__(self):
        status = "approved" if self.is_approved else "pending"
        return f"{self.user.username} ({status})"

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"


class InviteCode(models.Model):
    code = models.CharField(max_length=20, unique=True, db_index=True)
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="invite_codes"
    )
    label = models.CharField(max_length=100, blank=True)
    max_uses = models.IntegerField(default=1, help_text="0 = unlimited")
    times_used = models.IntegerField(default=0)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.code} ({self.label or 'no label'})"

    @property
    def is_valid(self):
        if not self.is_active:
            return False
        if self.max_uses > 0 and self.times_used >= self.max_uses:
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        return True

    @property
    def uses_remaining(self):
        if self.max_uses == 0:
            return None  # unlimited
        return max(0, self.max_uses - self.times_used)

    def use(self):
        self.times_used += 1
        if self.max_uses > 0 and self.times_used >= self.max_uses:
            self.is_active = False
        self.save()

    @classmethod
    def generate_code(cls):
        return f"INV-{secrets.token_hex(4)}"


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(
            user=instance,
            defaults={"is_approved": instance.is_staff or instance.is_superuser},
        )
