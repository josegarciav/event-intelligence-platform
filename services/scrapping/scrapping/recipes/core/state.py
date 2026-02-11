from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

@dataclass
class StateManager:
    output_dir: str
    phase: str = "init"
    current_page: int = 1
    processed_urls: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    last_updated: float = field(default_factory=time.time)

    def save(self):
        p = Path(self.output_dir) / "state.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        self.last_updated = time.time()
        with p.open("w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2)

    @classmethod
    def load(cls, output_dir: str) -> Optional[StateManager]:
        p = Path(output_dir) / "state.json"
        if not p.exists():
            return None
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
            return cls(**data)

    def mark_phase(self, phase: str):
        self.phase = phase
        self.save()

    def add_processed_url(self, url: str):
        if url not in self.processed_urls:
            self.processed_urls.append(url)
            # We don't save every URL to avoid IO overhead in tight loops,
            # the caller should call save() at checkpoints.
