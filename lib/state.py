"""Lightweight run state persistence (state.json)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from models import State


def save_state(run_dir: Path, state: State, extra: dict[str, Any] | None = None) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "state": state.value,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        **(extra or {}),
    }
    (run_dir / "state.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def read_state(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "state.json"
    if not path.exists():
        return {}
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}
