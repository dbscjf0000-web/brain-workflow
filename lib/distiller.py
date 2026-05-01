"""시상 필터: 다음 단계 프롬프트용 출력 크기 제한 및 스키마 검증."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MAX_DISTILLED_CHARS = 15000


def distill(raw_output: dict[str, Any], step_dir: Path) -> dict[str, Any]:
    """크기 초과 시 핵심 필드만 추출하고, 검증 실패 시 truncate fallback."""
    step_dir.mkdir(parents=True, exist_ok=True)
    text = json.dumps(raw_output, ensure_ascii=False)
    if len(text) <= MAX_DISTILLED_CHARS:
        distilled = raw_output
    else:
        candidate = _extract_essentials(raw_output)
        candidate_text = json.dumps(candidate, ensure_ascii=False)
        if candidate and candidate is not raw_output and len(candidate_text) <= MAX_DISTILLED_CHARS:
            distilled = candidate
        else:
            distilled = {"raw_truncated": text[:MAX_DISTILLED_CHARS]}
    if not _validate_schema(distilled):
        distilled = {"raw_truncated": text[:MAX_DISTILLED_CHARS]}
    out_path = step_dir / "distilled.json"
    out_path.write_text(
        json.dumps(distilled, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return distilled


def _extract_essentials(data: dict[str, Any]) -> dict[str, Any]:
    essentials: dict[str, Any] = {}
    for key in ("files", "changes", "risks", "plan", "summary"):
        if key in data:
            essentials[key] = data[key]
    return essentials if essentials else data


def _validate_schema(data: Any) -> bool:
    return isinstance(data, dict) and len(data) > 0
