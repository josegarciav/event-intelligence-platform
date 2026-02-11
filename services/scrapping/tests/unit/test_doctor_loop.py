import pytest
import asyncio
from scrapping.orchestrator import doctor_environment

@pytest.mark.asyncio
async def test_doctor_environment_in_loop():
    # doctor_environment should not raise "Playwright Sync API cannot be used inside an asyncio loop"
    # because we wrap the check in a thread.

    # We need to ensure playwright is installed for this test to be meaningful,
    # but even if not, it shouldn't crash with the Loop error.

    res = doctor_environment()
    assert "playwright" in res["checks"]
    # If playwright is installed, playwright_browsers check should have run without loop error.
    if res["checks"]["playwright"]["ok"]:
        assert "playwright_browsers" in res["checks"]
        # It might be ok: False if browsers are missing, but it shouldn't be a crash.
