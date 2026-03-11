import json

from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Avg, Count, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from gateway.throttle import parse_rate
from keys.models import ApiKey
from usage.models import DailyAggregate, RequestLog

from .forms import RegisterForm
from .models import InviteCode, UserProfile


def landing(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, "landing.html")


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            raw_code = form.cleaned_data.get("invite_code", "").strip()
            invite = None

            if raw_code:
                try:
                    invite = InviteCode.objects.get(code=raw_code)
                except InviteCode.DoesNotExist:
                    form.add_error("invite_code", "Invalid invite code.")
                    return render(
                        request, "accounts/register.html", {"form": form}
                    )
                if not invite.is_valid:
                    form.add_error(
                        "invite_code", "This invite code has expired or been used up."
                    )
                    return render(
                        request, "accounts/register.html", {"form": form}
                    )

            user = form.save()

            if invite:
                invite.use()
                user.profile.is_approved = True
                user.profile.invite_code_used = invite
                user.profile.save()
                login(request, user)
                messages.success(request, "Account created and approved. Welcome!")
                return redirect("dashboard")
            else:
                messages.info(
                    request,
                    "Account created. An admin will review and approve your registration.",
                )
                return redirect("login")
    else:
        form = RegisterForm()
    return render(request, "accounts/register.html", {"form": form})


def custom_login(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    error = None
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            if user.is_staff or (
                hasattr(user, "profile") and user.profile.is_approved
            ):
                login(request, user)
                return redirect(request.GET.get("next", "dashboard"))
            else:
                error = "pending"
        else:
            error = "invalid"
    return render(request, "accounts/login.html", {"error": error})


def pending(request):
    return render(request, "accounts/pending.html")


@login_required
def dashboard(request):
    user = request.user
    now = timezone.now()
    today = now.date()
    thirty_days_ago = today - timezone.timedelta(days=30)
    month_start = today.replace(day=1)

    # ── API Keys ──
    keys = ApiKey.objects.filter(user=user)
    active_keys_qs = keys.filter(is_active=True)
    active_keys = active_keys_qs.count()
    total_keys = keys.count()
    last_key_used = active_keys_qs.order_by("-last_used_at").first()

    # ── Rate Limits (current window usage per key, from DB) ──
    rate_limits = []
    now_ts = timezone.now()
    for key in active_keys_qs:
        rate_string = key.get_rate_limit()
        max_requests, window = parse_rate(rate_string)
        window_start = now_ts - timezone.timedelta(seconds=window)
        current = RequestLog.objects.filter(
            api_key_prefix=key.prefix,
            timestamp__gte=window_start,
        ).count()
        pct = round(current / max_requests * 100) if max_requests else 0
        period_labels = {1: "sec", 60: "min", 3600: "hour", 86400: "day"}
        period_label = period_labels.get(window, f"{window}s")
        rate_limits.append({
            "name": key.name,
            "prefix": key.prefix,
            "rate_string": rate_string,
            "current": current,
            "max": max_requests,
            "pct": min(pct, 100),
            "period_label": period_label,
        })

    # ── Aggregates (30 days, per key — for table) ──
    aggregates = (
        DailyAggregate.objects.filter(user=user, date__gte=thirty_days_ago)
        .order_by("-date")
    )

    # ── Totals (30 days) ──
    totals_30d = aggregates.aggregate(
        total_calls=Sum("calls_total"),
        total_chat=Sum("calls_chat"),
        total_generate=Sum("calls_generate"),
        total_embeddings=Sum("calls_embeddings"),
        total_tokens_in=Sum("tokens_in_total"),
        total_tokens_out=Sum("tokens_out_total"),
        total_2xx=Sum("calls_2xx"),
        total_4xx=Sum("calls_4xx"),
        total_5xx=Sum("calls_5xx"),
        avg_latency=Avg("avg_latency_ms"),
    )

    # ── Requests today ──
    today_agg = (
        DailyAggregate.objects.filter(user=user, date=today)
        .aggregate(calls_today=Sum("calls_total"))
    )

    # ── Requests this month ──
    month_agg = (
        DailyAggregate.objects.filter(user=user, date__gte=month_start)
        .aggregate(
            calls_month=Sum("calls_total"),
            tokens_in_month=Sum("tokens_in_total"),
            tokens_out_month=Sum("tokens_out_total"),
        )
    )

    # ── Error rate ──
    total_calls = totals_30d["total_calls"] or 0
    total_errors = (totals_30d["total_4xx"] or 0) + (totals_30d["total_5xx"] or 0)
    error_rate = round(total_errors / total_calls * 100, 1) if total_calls else 0

    # ── Most used model (from RequestLog) ──
    top_model_row = (
        RequestLog.objects.filter(user=user, timestamp__date__gte=thirty_days_ago)
        .exclude(model="")
        .values("model")
        .annotate(cnt=Count("id"))
        .order_by("-cnt")
        .first()
    )
    top_model = top_model_row["model"] if top_model_row else None
    top_model_count = top_model_row["cnt"] if top_model_row else 0

    # ── Usage per model (top 10) ──
    models_usage = list(
        RequestLog.objects.filter(user=user, timestamp__date__gte=thirty_days_ago)
        .exclude(model="")
        .values("model")
        .annotate(
            cnt=Count("id"),
            tok_in=Sum("tokens_in"),
            tok_out=Sum("tokens_out"),
            avg_lat=Avg("latency_ms"),
        )
        .order_by("-cnt")[:10]
    )
    for m in models_usage:
        m["avg_lat"] = round(m["avg_lat"] or 0, 0)

    # ── Recent errors (last 15) ──
    recent_errors = list(
        RequestLog.objects.filter(user=user, status_code__gte=400)
        .values("timestamp", "endpoint", "model", "status_code", "latency_ms",
                "api_key_prefix")
        .order_by("-timestamp")[:15]
    )

    # ── Daily chart data (aggregated across keys) ──
    daily_chart = list(
        DailyAggregate.objects.filter(user=user, date__gte=thirty_days_ago)
        .values("date")
        .annotate(
            calls=Sum("calls_total"),
            chat=Sum("calls_chat"),
            generate=Sum("calls_generate"),
            embeddings=Sum("calls_embeddings"),
            tokens_in=Sum("tokens_in_total"),
            tokens_out=Sum("tokens_out_total"),
            latency=Avg("avg_latency_ms"),
            ok=Sum("calls_2xx"),
            err4=Sum("calls_4xx"),
            err5=Sum("calls_5xx"),
        )
        .order_by("date")
    )
    for row in daily_chart:
        row["date"] = row["date"].isoformat()
        row["latency"] = round(row["latency"] or 0, 1)

    return render(request, "dashboard/index.html", {
        # Cards
        "calls_today": today_agg["calls_today"] or 0,
        "calls_month": month_agg["calls_month"] or 0,
        "tokens_month": (month_agg["tokens_in_month"] or 0)
                        + (month_agg["tokens_out_month"] or 0),
        "avg_latency": round(totals_30d["avg_latency"] or 0, 0),
        "error_rate": error_rate,
        "top_model": top_model,
        "top_model_count": top_model_count,
        # Rate limits
        "rate_limits": rate_limits,
        # Keys
        "active_keys": active_keys,
        "total_keys": total_keys,
        "keys": active_keys_qs,
        "last_key_used": last_key_used,
        # Totals for doughnuts
        "totals": totals_30d,
        # Models breakdown
        "models_usage": models_usage,
        # Recent errors
        "recent_errors": recent_errors,
        # Table
        "aggregates": aggregates,
        # Charts
        "daily_chart_json": json.dumps(daily_chart),
        "models_chart_json": json.dumps(
            [{"model": m["model"], "count": m["cnt"]} for m in models_usage]
        ),
    })


@login_required
def test_api(request):
    from keys.views import _fetch_available_models

    available_models = _fetch_available_models()
    active_keys = ApiKey.objects.filter(user=request.user, is_active=True)
    return render(request, "dashboard/test.html", {
        "available_models": available_models,
        "keys": active_keys,
    })


@login_required
def usage_guide(request):
    from keys.views import _fetch_available_models

    available_models = _fetch_available_models()
    return render(request, "dashboard/usage.html", {
        "available_models": available_models,
    })


@login_required
def user_management(request):
    if not request.user.is_staff:
        return redirect("dashboard")

    if request.method == "POST":
        action = request.POST.get("action")

        # ── Invite code actions ──
        if action == "create_invite":
            label = request.POST.get("label", "").strip()
            max_uses = int(request.POST.get("max_uses", 1) or 1)
            expires_days = request.POST.get("expires_days", "")
            expires_at = None
            if expires_days:
                expires_at = timezone.now() + timezone.timedelta(
                    days=int(expires_days)
                )
            code = InviteCode.generate_code()
            InviteCode.objects.create(
                code=code,
                created_by=request.user,
                label=label,
                max_uses=max_uses,
                expires_at=expires_at,
            )
            messages.success(request, f"Invite code created: {code}")
            return redirect("user_management")

        if action == "deactivate_invite":
            invite_id = request.POST.get("invite_id")
            invite = get_object_or_404(InviteCode, pk=invite_id)
            invite.is_active = False
            invite.save()
            messages.warning(request, f"Invite code {invite.code} deactivated.")
            return redirect("user_management")

        # ── User actions ──
        user_id = request.POST.get("user_id")
        target_user = get_object_or_404(User, pk=user_id)

        if target_user.is_staff or target_user.is_superuser:
            messages.error(request, "Cannot modify admin users.")
            return redirect("user_management")

        profile, _ = UserProfile.objects.get_or_create(
            user=target_user,
            defaults={"is_approved": False},
        )

        if action == "approve":
            profile.is_approved = True
            profile.save()
            messages.success(request, f"User '{target_user.username}' approved.")
        elif action == "revoke":
            profile.is_approved = False
            profile.save()
            messages.warning(request, f"Access revoked for '{target_user.username}'.")

        return redirect("user_management")

    users = (
        User.objects.filter(is_staff=False)
        .select_related("profile", "profile__invite_code_used")
        .order_by("-date_joined")
    )

    pending_count = UserProfile.objects.filter(
        is_approved=False, user__is_staff=False
    ).count()
    approved_count = UserProfile.objects.filter(
        is_approved=True, user__is_staff=False
    ).count()

    invite_codes = InviteCode.objects.select_related("created_by").order_by(
        "-created_at"
    )

    return render(request, "dashboard/users.html", {
        "users": users,
        "pending_count": pending_count,
        "approved_count": approved_count,
        "invite_codes": invite_codes,
    })
