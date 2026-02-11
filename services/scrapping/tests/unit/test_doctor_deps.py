from unittest.mock import MagicMock, patch

from scrapping.orchestrator import doctor_environment


def test_doctor_detects_missing_os_deps():
    # Simulate a playwright launch failure due to missing shared libraries
    stderr = "/root/.cache/ms-playwright/chromium-1091/chrome-linux/chrome: error while loading shared libraries: libatk-1.0.so.0: cannot open shared object file: No such file or directory"

    mock_pw = MagicMock()
    mock_sync = mock_pw.__enter__.return_value
    mock_sync.chromium.launch.side_effect = Exception(stderr)

    with patch("playwright.sync_api.sync_playwright", return_value=mock_pw):
        # We also need to patch doctor_environment's loop detection to keep it simple
        with patch("asyncio.get_running_loop", side_effect=RuntimeError):
            report = doctor_environment()

    check = report["checks"].get("playwright_browsers", {})
    assert check["ok"] is False
    assert "Missing OS dependencies" in check["msg"]
    assert "playwright install --with-deps chromium" in check["hint"]
    assert "libatk1.0-0" in check.get("fallback_apt", "")
