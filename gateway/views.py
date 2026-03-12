import json
import time

import httpx
from django.conf import settings
from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt

from gateway.throttle import check_rate_limit
from keys.authentication import authenticate_api_key
from usage.logging import log_request_async


STREAMING_ENDPOINTS = ("api/chat", "api/generate", "api/pull", "api/push", "api/create", "v1/messages")

SAFE_FORWARD_HEADERS = {"content-type", "accept", "user-agent"}


def _build_upstream_headers(request):
    headers = {}
    for name in SAFE_FORWARD_HEADERS:
        value = request.headers.get(name)
        if value:
            headers[name] = value
    return headers


def _get_client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _parse_body(body):
    if not body:
        return {}
    try:
        return json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}


@csrf_exempt
async def proxy_ollama(request, path):
    # 1. Authenticate
    from asgiref.sync import sync_to_async

    api_key = await sync_to_async(authenticate_api_key)(request)
    if api_key is None:
        return JsonResponse({"error": "unauthorized"}, status=401)

    user = api_key.user

    # 1.5 Check user approval
    if not user.is_staff:
        is_approved = await sync_to_async(
            lambda: hasattr(user, "profile") and user.profile.is_approved
        )()
        if not is_approved:
            return JsonResponse({"error": "account_not_approved"}, status=403)

    # 2. Admin-only endpoint check
    if path in settings.ADMIN_ONLY_ENDPOINTS:
        is_staff = await sync_to_async(lambda: api_key.user.is_staff)()
        if not is_staff:
            return JsonResponse({"error": "admin_only"}, status=403)

    # 3. Parse body and check model allowlist
    body = request.body
    body_data = _parse_body(body)
    model = body_data.get("model")

    allowed = api_key.allowed_models
    if model and allowed and model not in allowed:
        return JsonResponse(
            {"error": "model_not_allowed", "model": model}, status=403
        )

    # 4. Rate limiting
    rate = api_key.get_rate_limit()
    if not check_rate_limit(api_key.prefix, rate):
        return JsonResponse({"error": "rate_limited"}, status=429)

    # 5. Proxy to upstream
    upstream_url = f"{settings.OLLAMA_UPSTREAM_BASE_URL}/{path}"
    forward_headers = _build_upstream_headers(request)
    # Anthropic endpoints default to non-streaming; Ollama defaults to streaming
    is_anthropic = path.startswith("v1/")
    if is_anthropic:
        stream_requested = body_data.get("stream", False)
    else:
        stream_requested = body_data.get("stream", True)
    is_streaming = (
        path in STREAMING_ENDPOINTS
        and settings.ENABLE_STREAMING
        and stream_requested is not False
    )
    start_time = time.time()
    client_ip = _get_client_ip(request)
    user_agent = request.headers.get("User-Agent", "")

    try:
        client = httpx.AsyncClient(timeout=None)

        if is_streaming:
            upstream_resp = await client.send(
                client.build_request(
                    request.method,
                    upstream_url,
                    content=body,
                    headers=forward_headers,
                ),
                stream=True,
            )

            async def stream_chunks():
                last_data = None
                total_size = 0
                _tokens_in = None
                _tokens_out = None
                try:
                    async for chunk in upstream_resp.aiter_bytes():
                        total_size += len(chunk)
                        text = chunk.decode(errors="replace")
                        if is_anthropic:
                            # Anthropic SSE: parse event data lines
                            for line in text.split("\n"):
                                if not line.startswith("data: "):
                                    continue
                                try:
                                    event_data = json.loads(line[6:])
                                    evt_type = event_data.get("type")
                                    if evt_type == "message_start":
                                        usage = event_data.get("message", {}).get("usage", {})
                                        if usage.get("input_tokens") is not None:
                                            _tokens_in = usage["input_tokens"]
                                    elif evt_type == "message_delta":
                                        usage = event_data.get("usage", {})
                                        if usage.get("output_tokens") is not None:
                                            _tokens_out = usage["output_tokens"]
                                except (json.JSONDecodeError, KeyError):
                                    pass
                        else:
                            # Ollama NDJSON: parse last JSON line
                            try:
                                lines = text.strip().split("\n")
                                last_data = json.loads(lines[-1])
                            except (json.JSONDecodeError, IndexError):
                                pass
                        yield chunk
                finally:
                    status_code = upstream_resp.status_code
                    try:
                        await upstream_resp.aclose()
                        await client.aclose()
                    except RuntimeError:
                        pass

                    latency_ms = int((time.time() - start_time) * 1000)
                    if not is_anthropic and last_data:
                        _tokens_in = last_data.get("prompt_eval_count")
                        _tokens_out = last_data.get("eval_count")

                    await log_request_async(
                        user=user,
                        api_key_prefix=api_key.prefix,
                        endpoint=path,
                        model=model,
                        status_code=status_code,
                        latency_ms=latency_ms,
                        ip_address=client_ip,
                        user_agent=user_agent,
                        streaming=True,
                        request_size=len(body) if body else 0,
                        response_size=total_size,
                        tokens_in=_tokens_in,
                        tokens_out=_tokens_out,
                    )

            response = StreamingHttpResponse(
                streaming_content=stream_chunks(),
                status=upstream_resp.status_code,
                content_type=upstream_resp.headers.get(
                    "content-type", "application/x-ndjson"
                ),
            )
            return response

        else:
            # Non-streaming request
            upstream_resp = await client.request(
                request.method,
                upstream_url,
                content=body,
                headers=forward_headers,
                timeout=httpx.Timeout(120.0),
            )
            await client.aclose()

            latency_ms = int((time.time() - start_time) * 1000)

            tokens_in = None
            tokens_out = None
            try:
                resp_data = upstream_resp.json()
                if is_anthropic:
                    usage = resp_data.get("usage", {})
                    tokens_in = usage.get("input_tokens")
                    tokens_out = usage.get("output_tokens")
                else:
                    tokens_in = resp_data.get("prompt_eval_count")
                    tokens_out = resp_data.get("eval_count")
            except (json.JSONDecodeError, ValueError):
                pass

            await log_request_async(
                user=user,
                api_key_prefix=api_key.prefix,
                endpoint=path,
                model=model,
                status_code=upstream_resp.status_code,
                latency_ms=latency_ms,
                ip_address=client_ip,
                user_agent=user_agent,
                streaming=False,
                request_size=len(body) if body else 0,
                response_size=len(upstream_resp.content),
                tokens_in=tokens_in,
                tokens_out=tokens_out,
            )

            return HttpResponse(
                upstream_resp.content,
                status=upstream_resp.status_code,
                content_type=upstream_resp.headers.get(
                    "content-type", "application/json"
                ),
            )

    except httpx.ConnectError:
        latency_ms = int((time.time() - start_time) * 1000)
        await log_request_async(
            user=user,
            api_key_prefix=api_key.prefix,
            endpoint=path,
            model=model,
            status_code=502,
            latency_ms=latency_ms,
            ip_address=client_ip,
            user_agent=user_agent,
            streaming=is_streaming,
            request_size=len(body) if body else 0,
            response_size=0,
            tokens_in=None,
            tokens_out=None,
        )
        return JsonResponse({"error": "upstream_unavailable"}, status=502)
