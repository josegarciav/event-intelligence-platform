from scrapping.diagnostics.classifiers import (
    DiagnosisLabel,
    NextStep,
    diagnose_http_response,
    diagnose_rendered_dom,
)


def test_diagnose_rate_limited():
    res = diagnose_http_response(429, {})
    assert res.label == DiagnosisLabel.RATE_LIMITED
    assert res.next_step == NextStep.TRY_HTTP_TUNING

    res = diagnose_http_response(200, {"Retry-After": "10"})
    assert res.label == DiagnosisLabel.RATE_LIMITED


def test_diagnose_challenge():
    res = diagnose_http_response(200, {}, text="please solve this captcha")
    assert res.label == DiagnosisLabel.CHALLENGE_DETECTED
    assert res.next_step == NextStep.STOP_FOR_HUMAN

    res = diagnose_rendered_dom("Cloudflare Turnstile verification")
    assert res.label == DiagnosisLabel.CHALLENGE_DETECTED


def test_diagnose_js_required():
    res = diagnose_http_response(200, {}, text="Enable JavaScript to continue")
    assert res.label == DiagnosisLabel.JS_REQUIRED_OR_MISSING_CONTENT
    assert res.next_step == NextStep.SWITCH_TO_BROWSER


def test_diagnose_auth():
    res = diagnose_http_response(401, {})
    assert res.label == DiagnosisLabel.REQUIRES_AUTH
    assert res.next_step == NextStep.USE_AUTH

    res = diagnose_http_response(200, {}, text="Please login to view this page")
    assert res.label == DiagnosisLabel.REQUIRES_AUTH


def test_diagnose_ok():
    res = diagnose_http_response(
        200,
        {},
        text="<html><body><h1>Title</h1><p>Content goes here...</p></body></html>" * 10,
    )
    assert res.label == DiagnosisLabel.OK
    assert res.next_step == NextStep.PROCEED
