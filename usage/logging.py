from asgiref.sync import sync_to_async
from django.db.models import F
from django.utils import timezone

from usage.models import DailyAggregate, RequestLog


def _log_request(
    user,
    api_key_prefix,
    endpoint,
    model,
    status_code,
    latency_ms,
    ip_address,
    user_agent,
    streaming,
    request_size,
    response_size,
    tokens_in,
    tokens_out,
):
    RequestLog.objects.create(
        user=user,
        api_key_prefix=api_key_prefix,
        endpoint=endpoint,
        model=model or "",
        status_code=status_code,
        latency_ms=latency_ms,
        ip_address=ip_address,
        user_agent=user_agent or "",
        streaming=streaming,
        request_size=request_size,
        response_size=response_size,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
    )

    # Update daily aggregate
    today = timezone.now().date()
    agg, _ = DailyAggregate.objects.get_or_create(
        date=today,
        user=user,
        api_key_prefix=api_key_prefix,
        defaults={"avg_latency_ms": latency_ms},
    )

    updates = {"calls_total": F("calls_total") + 1}

    if "chat" in endpoint:
        updates["calls_chat"] = F("calls_chat") + 1
    elif "generate" in endpoint:
        updates["calls_generate"] = F("calls_generate") + 1
    elif "embed" in endpoint:
        updates["calls_embeddings"] = F("calls_embeddings") + 1

    if 200 <= status_code < 300:
        updates["calls_2xx"] = F("calls_2xx") + 1
    elif 400 <= status_code < 500:
        updates["calls_4xx"] = F("calls_4xx") + 1
    elif 500 <= status_code < 600:
        updates["calls_5xx"] = F("calls_5xx") + 1

    if tokens_in is not None:
        updates["tokens_in_total"] = F("tokens_in_total") + tokens_in
    if tokens_out is not None:
        updates["tokens_out_total"] = F("tokens_out_total") + tokens_out

    DailyAggregate.objects.filter(pk=agg.pk).update(**updates)


log_request_async = sync_to_async(_log_request)
