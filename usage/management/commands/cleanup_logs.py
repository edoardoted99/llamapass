from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from usage.models import RequestLog


class Command(BaseCommand):
    help = "Delete request logs older than LOG_RETENTION_DAYS"

    def handle(self, *args, **options):
        days = settings.LOG_RETENTION_DAYS
        cutoff = timezone.now() - timezone.timedelta(days=days)
        count, _ = RequestLog.objects.filter(timestamp__lt=cutoff).delete()
        self.stdout.write(f"Deleted {count} request logs older than {days} days.")
