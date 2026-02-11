import pytest
from pathlib import Path
from scrapping.cli import main

def test_scaffold_test_command(tmp_path):
    fixture_path = tmp_path / "test.html"
    fixture_path.write_text("<html><a href='/1'>1</a></html>")

    test_path = tmp_path / "test_gen.py"

    argv = [
        "scaffold-test",
        "--fixture", str(fixture_path),
        "--extract", "css",
        "--pattern", "a",
        "--expect-count", "1",
        "--out", str(test_path)
    ]

    exit_code = main(argv)
    assert exit_code == 0
    assert test_path.exists()

    content = test_path.read_text()
    assert "LinkExtractRequest" in content
    assert "assert len(links) == 1" in content

def test_capture_fixture_http_offline(tmp_path, monkeypatch):
    # Mocking HttpEngine to avoid network
    from scrapping.engines.http import HttpEngine, FetchResult
    from scrapping.runtime.results import ResponseMeta, RequestMeta

    def mock_get(self, url, ctx=None):
        return FetchResult(
            final_url=url,
            status_code=200,
            text="<html>mock</html>",
            response_meta=ResponseMeta(headers={}),
            request_meta=RequestMeta(method="GET", headers={})
        )

    monkeypatch.setattr(HttpEngine, "get", mock_get)

    out_path = tmp_path / "captured.html"
    argv = [
        "capture-fixture",
        "--url", "http://example.com",
        "--engine", "http",
        "--out", str(out_path)
    ]

    exit_code = main(argv)
    assert exit_code == 0
    assert out_path.exists()
    assert out_path.read_text() == "<html>mock</html>"
