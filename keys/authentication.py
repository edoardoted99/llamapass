from keys.models import ApiKey


def authenticate_api_key(request):
    """
    Extract and verify API key from request headers.
    Supports: Authorization: Api-Key <key> and X-API-Key: <key>
    Returns the ApiKey instance or None.
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Api-Key "):
        raw_key = auth_header[8:].strip()
    elif auth_header.startswith("Bearer "):
        raw_key = auth_header[7:].strip()
    elif "X-API-Key" in request.headers:
        raw_key = request.headers["X-API-Key"].strip()
    else:
        return None

    if not raw_key.startswith("oah_"):
        return None

    secret_part = raw_key[4:]  # strip "oah_"
    prefix = secret_part[:8]

    try:
        api_key = ApiKey.objects.select_related("user").get(
            prefix=prefix, is_active=True
        )
    except ApiKey.DoesNotExist:
        return None

    if not api_key.verify(raw_key):
        return None

    if api_key.is_expired:
        return None

    api_key.touch()
    return api_key
