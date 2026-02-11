from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional

class TrackingStore:
    def __init__(self, tracking_path: str):
        self.path = Path(tracking_path)
        self.data = self._load()

    def _load(self) -> dict[str, Any]:
        if self.path.exists():
            with self.path.open("r", encoding="utf-8") as f:
                return json.load(f)
        return {"items": {}}

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)

    def update_item(self, key: str, status: str, **kwargs):
        item = self.data["items"].get(key, {})
        item.update({
            "status": status,
            "updated_at": time.time(),
            **kwargs
        })
        if "started_at" not in item and status == "running":
            item["started_at"] = time.time()
        if status in ("success", "failed"):
            item["finished_at"] = time.time()

        self.data["items"][key] = item
        self.save()

    def get_item(self, key: str) -> Optional[dict[str, Any]]:
        return self.data["items"].get(key)
