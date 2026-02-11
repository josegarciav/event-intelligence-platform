from scrapping.processing.html_to_structured import html_to_structured
from scrapping.processing.quality_filters import evaluate_quality


def test_quality_filters():
    # Too short
    item = {"text": "short", "title": "short"}
    q = evaluate_quality(item, rules={"min_text_len": 10})
    assert q.keep is False
    assert any(i.code == "short_text" for i in q.issues)

    # Block pattern
    item = {"text": "Access Denied by Cloudflare", "title": "Error"}
    q = evaluate_quality(item, rules={"min_text_len": 5})
    assert q.keep is False
    assert any(i.code == "blocked_page" for i in q.issues)

    # OK
    item = {"text": "This is a long enough text for testing quality filters.", "title": "Good Title"}
    q = evaluate_quality(item, rules={"min_text_len": 10})
    assert q.keep is True

def test_html_to_structured_empty():
    res = html_to_structured("")
    assert res.ok is False
    assert res.error == "empty_html"

    res = html_to_structured("   ")
    assert res.ok is False
    assert res.error == "empty_html"
