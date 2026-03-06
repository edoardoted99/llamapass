import time

from django.core.cache import cache


def parse_rate(rate_string):
    """Parse rate string like '60/min' into (count, seconds)."""
    count, period = rate_string.split("/")
    count = int(count)
    periods = {"sec": 1, "min": 60, "hour": 3600, "day": 86400}
    seconds = periods.get(period, 60)
    return count, seconds


def check_rate_limit(prefix, rate_string):
    """
    Fixed-window rate limiter using Django cache.
    Returns True if request is allowed, False if rate limited.
    """
    max_requests, window = parse_rate(rate_string)
    window_key = int(time.time()) // window
    cache_key = f"rl:{prefix}:{window_key}"

    current = cache.get(cache_key)
    if current is None:
        cache.set(cache_key, 1, timeout=window)
        return True

    if current >= max_requests:
        return False

    cache.incr(cache_key)
    return True
