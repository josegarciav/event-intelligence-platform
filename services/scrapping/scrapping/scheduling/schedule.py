"""
scrapping.scheduling.schedule

Scheduling semantics for scraping sources.
Supports interval-based and cron-based schedules.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Schedule:
    type: str  # "interval" | "cron"
    value: str | int

    def summary(self) -> str:
        return f"{self.type}: {self.value}"


def parse_schedule(spec: dict[str, Any]) -> Schedule | None:
    """
    Parse schedule from config dict.
    Expected formats:
      {"frequency": "1h"}
      {"frequency": "3600"} (seconds)
      {"frequency": "0 0 * * *"} (cron)
    """
    freq = spec.get("frequency")
    if freq is None:
        return None

    if isinstance(freq, int):
        return Schedule(type="interval", value=freq)

    s_freq = str(freq).strip()
    if not s_freq:
        return None

    # Try interval parsing (e.g., "1h", "30m", "10s")
    if s_freq.endswith("h") and s_freq[:-1].isdigit():
        return Schedule(type="interval", value=int(s_freq[:-1]) * 3600)
    if s_freq.endswith("m") and s_freq[:-1].isdigit():
        return Schedule(type="interval", value=int(s_freq[:-1]) * 60)
    if s_freq.endswith("s") and s_freq[:-1].isdigit():
        return Schedule(type="interval", value=int(s_freq[:-1]))
    if s_freq.isdigit():
        return Schedule(type="interval", value=int(s_freq))

    # Otherwise assume cron
    if len(s_freq.split()) == 5:
        return Schedule(type="cron", value=s_freq)

    return None


def next_run_times(
    schedule: Schedule, start_ts: float, n: int = 5
) -> list[datetime.datetime]:
    """
    Calculate next N run times starting from start_ts.
    """
    out = []
    base_dt = datetime.datetime.fromtimestamp(start_ts, tz=datetime.timezone.utc)

    if schedule.type == "interval":
        interval = int(schedule.value)
        for i in range(1, n + 1):
            out.append(base_dt + datetime.timedelta(seconds=interval * i))

    elif schedule.type == "cron":
        # Simple placeholder for cron logic if croniter missing
        try:
            from croniter import croniter

            it = croniter(str(schedule.value), base_dt)
            for _ in range(n):
                out.append(it.get_next(datetime.datetime))
        except ImportError:
            # fallback: cannot calculate next times for cron without croniter
            pass

    return out
