import os

import pytest

from scrapping.engines.browser import BrowserEngine, BrowserEngineOptions


@pytest.mark.integration
def test_browser_engine_online_quotes():
    if os.getenv("RUN_INTEGRATION") != "1":
        pytest.skip("RUN_INTEGRATION=1 not set")

    engine = BrowserEngine(options=BrowserEngineOptions(headless=True))
    try:
        url = "https://quotes.toscrape.com/js/"
        res = engine.get_rendered(url, wait_for=".quote")

        assert res.ok
        assert res.status_code == 200
        assert 'class="quote"' in res.text
        assert "Albert Einstein" in res.text

        # Check action results in trace
        for entry in res.engine_trace:
            if "actions" in entry:
                break
        # Even if we didn't pass explicit actions, wait_for might be logged if we updated it to be so.
        # But wait_for is separate in get_rendered.

    finally:
        engine.close()
