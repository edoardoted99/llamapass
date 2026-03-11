from .models import UserProfile


def pending_users(request):
    if request.user.is_authenticated and request.user.is_staff:
        return {
            "pending_count": UserProfile.objects.filter(
                is_approved=False, user__is_staff=False
            ).count()
        }
    return {}
