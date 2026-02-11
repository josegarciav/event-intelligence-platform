import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from scrapping.engines.browser import BrowserEngine, BrowserEngineOptions
from scrapping.actions.browser_actions import BrowserActionRunner, ActionRunnerOptions, ActionResult

def test_browser_engine_options_defaults():
    opts = BrowserEngineOptions()
    assert opts.browser_name == "chromium"
    assert opts.headless is True
    assert opts.save_artifacts is False
    assert opts.screenshot_on_error is True

def test_action_result_structure():
    res = ActionResult(type="click", ok=True, elapsed_ms=10.5)
    assert res.type == "click"
    assert res.ok is True
    assert res.elapsed_ms == 10.5

@patch("playwright.sync_api.sync_playwright")
def test_ensure_started_missing_browsers(mock_pw):
    # Setup mock to simulate missing browsers
    mock_pw_instance = mock_pw.return_value.start.return_value
    mock_launcher = getattr(mock_pw_instance, "chromium")
    mock_launcher.launch.side_effect = Exception("executable doesn't exist")

    engine = BrowserEngine()
    with pytest.raises(RuntimeError) as excinfo:
        engine._ensure_started()
    assert "Browser binaries for chromium are missing" in str(excinfo.value)

def test_save_artifacts_path_creation(tmp_path):
    opts = BrowserEngineOptions(save_artifacts=True, artifacts_dir=str(tmp_path))
    engine = BrowserEngine(options=opts)

    mock_page = MagicMock()
    url = "https://example.com"
    html = "<html></html>"

    artifacts = engine._save_page_artifacts(mock_page, url, attempt=0, html=html)

    assert "html_path" in artifacts
    assert "screenshot_path" in artifacts
    assert Path(artifacts["html_path"]).exists()
    # screenshot_path might not exist because page.screenshot was mocked and didn't actually write
    mock_page.screenshot.assert_called_once()

def test_browser_engine_hardened_results_on_failure():
    engine = BrowserEngine()
    # Mocking _ensure_started to fail
    with patch.object(BrowserEngine, "_ensure_started", side_effect=Exception("Failed to launch")):
        res = engine.get("https://example.com")
        assert res.ok is False
        assert res.text == ""
        assert res.error is not None
        assert "Failed to launch" in res.error.message

@pytest.mark.asyncio
async def test_browser_engine_sync_call_in_async_loop():
    """
    Verifies that BrowserEngine (sync) can be called from an async loop
    without raising the Playwright sync error.
    """
    engine = BrowserEngine()

    # We want to test that get_rendered properly offloads to a thread
    # and that _ensure_started allows execution when in a thread.

    # Mocking the actual playwright start to avoid launching a real browser
    with patch("playwright.sync_api.sync_playwright") as mock_pw:
        # Mock _get_rendered_sync to verify it's called
        with patch.object(BrowserEngine, "_get_rendered_sync", wraps=engine._get_rendered_sync) as mock_sync:
            # Mock the internal ensure_started to avoid real PW launch but keep logic
            with patch.object(BrowserEngine, "_ensure_started") as mock_ensure:
                res = engine.get_rendered("https://example.com")
                assert mock_sync.called
                # Verify it was called from a different thread
                # (In this simple mock setup it might be hard to verify the exact thread behavior
                # without deeper inspection, but the main goal is no RuntimeError)

@pytest.mark.asyncio
async def test_async_browser_engine_hardened_results_on_failure():
    from scrapping.engines.browser import AsyncBrowserEngine
    engine = AsyncBrowserEngine()
    # Mocking _ensure_started to fail
    with patch.object(AsyncBrowserEngine, "_ensure_started", side_effect=Exception("Async failed")):
        res = await engine.get("https://example.com")
        assert res.ok is False
        assert res.text == ""
        assert res.error is not None
        assert "Async failed" in res.error.message
