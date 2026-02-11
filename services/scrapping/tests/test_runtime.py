import time
from scrapping.runtime.resilience import RetryPolicy, RateLimiter
from scrapping.runtime.results import FetchResult, EngineError
from scrapping.runtime.blocks import classify_blocks

def test_retry_policy_backoff():
    policy = RetryPolicy(base_delay_s=0.1, max_delay_s=1.0, backoff_mode="exp")
    # attempt 1: base * 2^0 = 0.1
    # attempt 2: base * 2^1 = 0.2
    # attempt 3: base * 2^2 = 0.4

    b1 = policy.compute_backoff_s(1)
    assert 0.05 <= b1 <= 0.15 # with jitter

    b2 = policy.compute_backoff_s(2)
    assert 0.15 <= b2 <= 0.25

def test_rate_limiter():
    limiter = RateLimiter(rps=10, min_delay_s=0.01)
    t0 = time.time()
    for _ in range(5):
        limiter.wait()
    elapsed = time.time() - t0
    assert elapsed >= 0.04

def test_fetch_result_ok():
    res = FetchResult(final_url="http://a", status_code=200)
    assert res.ok is True
    assert res.is_retryable is False

def test_fetch_result_retryable():
    res = FetchResult(final_url="http://a", status_code=429)
    assert res.ok is False
    assert res.is_retryable is True

    res = FetchResult(final_url="http://a", error=EngineError(type="T", message="M", is_retryable=True))
    assert res.ok is False
    assert res.is_retryable is True

def test_block_detection():
    signals = classify_blocks("Access Denied by Cloudflare")
    assert "captcha_present" in [s.value for s in signals] or "likely_blocked" in [s.value for s in signals]

    signals = classify_blocks("Please login to continue")
    assert "login_required" in [s.value for s in signals]
