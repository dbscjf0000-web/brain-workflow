from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REQUIRED_TOP = frozenset({"schema_version", "agents", "routes", "defaults"})


def load_config(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    raw = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("config must be a JSON object")
    missing = REQUIRED_TOP - raw.keys()
    if missing:
        raise ValueError(f"config missing keys: {sorted(missing)}")
    ver = raw.get("schema_version")
    if ver != "1.0":
        raise ValueError(f"unsupported schema_version: {ver!r} (expected '1.0')")
    if not isinstance(raw["agents"], dict):
        raise ValueError("agents must be an object")
    if not isinstance(raw["routes"], dict):
        raise ValueError("routes must be an object")
    if not isinstance(raw["defaults"], dict):
        raise ValueError("defaults must be an object")
    return raw
