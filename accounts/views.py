from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import redirect, render
from django.utils import timezone

from keys.models import ApiKey
from usage.models import DailyAggregate

from .forms import RegisterForm


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Account created successfully.")
            return redirect("dashboard")
    else:
        form = RegisterForm()
    return render(request, "accounts/register.html", {"form": form})


@login_required
def dashboard(request):
    user = request.user
    today = timezone.now().date()

    keys = ApiKey.objects.filter(user=user)
    active_keys = keys.filter(is_active=True).count()
    total_keys = keys.count()

    thirty_days_ago = today - timezone.timedelta(days=30)
    aggregates = (
        DailyAggregate.objects.filter(user=user, date__gte=thirty_days_ago)
        .order_by("-date")
    )

    totals = aggregates.aggregate(
        total_calls=Sum("calls_total"),
        total_chat=Sum("calls_chat"),
        total_generate=Sum("calls_generate"),
        total_embeddings=Sum("calls_embeddings"),
        total_tokens_in=Sum("tokens_in_total"),
        total_tokens_out=Sum("tokens_out_total"),
    )

    return render(request, "dashboard/index.html", {
        "active_keys": active_keys,
        "total_keys": total_keys,
        "aggregates": aggregates,
        "totals": totals,
    })


@login_required
def usage_guide(request):
    from keys.views import _fetch_available_models

    available_models = _fetch_available_models()
    return render(request, "dashboard/usage.html", {
        "available_models": available_models,
    })
