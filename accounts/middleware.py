from django.shortcuts import redirect


class ApprovalMiddleware:
    """Redirect authenticated but unapproved users to the pending page."""

    EXEMPT_PREFIXES = (
        "/accounts/logout/",
        "/accounts/pending/",
        "/admin/",
        "/static/",
        "/ollama/",  # API auth handled separately
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.user.is_authenticated
            and not request.user.is_staff
            and not any(request.path.startswith(p) for p in self.EXEMPT_PREFIXES)
        ):
            try:
                if not request.user.profile.is_approved:
                    return redirect("pending")
            except Exception:
                return redirect("pending")

        return self.get_response(request)
