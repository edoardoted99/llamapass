import httpx
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from keys.models import ApiKey


def _fetch_available_models():
    try:
        resp = httpx.get(
            f"{settings.OLLAMA_UPSTREAM_BASE_URL}/api/tags", timeout=5.0
        )
        resp.raise_for_status()
        return sorted(m["name"] for m in resp.json().get("models", []))
    except Exception:
        return []


@login_required
def key_list(request):
    keys = ApiKey.objects.filter(user=request.user)
    available_models = _fetch_available_models()
    new_api_key = request.session.pop("new_api_key", None)
    return render(request, "dashboard/keys.html", {
        "keys": keys,
        "available_models": available_models,
        "new_api_key": new_api_key,
    })


@login_required
def key_create(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        allowed_models = request.POST.getlist("allowed_models")
        rate_limit = request.POST.get("rate_limit", "").strip()
        expires_days = request.POST.get("expires_days", "").strip()

        if not name:
            messages.error(request, "Key name is required.")
            return redirect("key_list")

        expires_at = None
        if expires_days:
            try:
                days = int(expires_days)
                if days > 0:
                    expires_at = timezone.now() + timezone.timedelta(days=days)
            except ValueError:
                pass

        full_key, prefix, hashed_key = ApiKey.generate_key()

        ApiKey.objects.create(
            user=request.user,
            name=name,
            prefix=prefix,
            hashed_key=hashed_key,
            allowed_models=allowed_models,
            rate_limit=rate_limit,
            expires_at=expires_at,
        )

        request.session["new_api_key"] = full_key
        return redirect("key_list")

    return redirect("key_list")


@login_required
def key_revoke(request, pk):
    if request.method == "POST":
        api_key = get_object_or_404(ApiKey, pk=pk, user=request.user)
        api_key.revoke()
        messages.success(request, f"Key '{api_key.name}' has been revoked.")
    return redirect("key_list")
