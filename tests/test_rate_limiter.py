import time
from modules.riot_api.rate_limiter import TokenBucketLimiter


def test_token_bucket_limiter_basic_timing():
    limiter = TokenBucketLimiter(rate=2, capacity=2)  # 2 tokens/sec, capacity 2
    # First two acquires should be immediate
    t0 = time.monotonic()
    assert limiter.acquire() is True
    assert limiter.acquire() is True
    t1 = time.monotonic()
    # elapsed should be very small
    assert (t1 - t0) < 0.1

    # Third acquire should block ~0.5s (since rate=2 tokens/sec -> 0.5s per token)
    t_start = time.monotonic()
    limiter.acquire()
    t_end = time.monotonic()
    assert (t_end - t_start) >= 0.4
