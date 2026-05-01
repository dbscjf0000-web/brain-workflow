"""Load run metadata from .brain/runs for CLI status/show/apply."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_STEP_DIR_RE = re.compile(r"^(\d{2})-(.+)$")


def runs_root(cwd: Path) -> Path:
    return cwd / ".brain" / "runs"


def list_run_dirs(cwd: Path) -> list[Path]:
    root = runs_root(cwd)
    if not root.is_dir():
        return []
    out: list[Path] = []
    for p in root.iterdir():
        if p.is_dir() and p.name.startswith("run-") and (p / "task.json").exists():
            out.append(p)
    out.sort(key=lambda x: x.name, reverse=True)
    return out


def resolve_latest_run_dir(cwd: Path) -> Path | None:
    dirs = list_run_dirs(cwd)
    return dirs[0] if dirs else None


def resolve_run_dir(cwd: Path, run_ref: str) -> Path:
    ref = (run_ref or "").strip()
    if ref.lower() == "latest":
        d = resolve_latest_run_dir(cwd)
        if d is None:
            raise FileNotFoundError(
                f"no runs found under {runs_root(cwd)} (expected run-* directories with task.json)"
            )
        return d
    root = runs_root(cwd)
    d = root / ref
    if not d.is_dir():
        raise FileNotFoundError(f"run not found: {ref!r} (expected {d})")
    if not (d / "task.json").exists():
        raise FileNotFoundError(f"run {ref!r} has no task.json: {d}")
    return d


def _read_json(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    return data if isinstance(data, dict) else {}


def _step_duration_sec(step_dir: Path) -> float | None:
    out_json = step_dir / "output.json"
    if out_json.exists():
        try:
            o = _read_json(out_json)
        except (OSError, json.JSONDecodeError):
            o = {}
        if isinstance(o.get("duration_ms"), (int, float)):
            return float(o["duration_ms"]) / 1000.0
        if isinstance(o.get("duration_sec"), (int, float)):
            return float(o["duration_sec"])
    raw = step_dir / "raw.log"
    if raw.exists():
        try:
            line = raw.read_text(encoding="utf-8", errors="replace").splitlines()
            first = line[0] if line else ""
            if first.startswith("{"):
                o = json.loads(first)
                if isinstance(o, dict) and isinstance(
                    o.get("duration_ms"), (int, float)
                ):
                    return float(o["duration_ms"]) / 1000.0
        except (OSError, json.JSONDecodeError, ValueError):
            pass
    return None


def _agent_for_step_id(task_steps: list[dict], step_id: str) -> str:
    if step_id == "reverify":
        return _agent_for_step_id(task_steps, "verify")
    if step_id == "correct":
        for s in task_steps:
            if isinstance(s, dict) and s.get("id") == "verify":
                a = s.get("agent")
                return str(a) if a is not None else "?"
        return "?"
    for s in task_steps:
        if isinstance(s, dict) and s.get("id") == step_id:
            a = s.get("agent")
            return str(a) if a is not None else "?"
    return "?"


def _step_ok(step_dir: Path) -> bool:
    if (step_dir / "parse_error.md").exists():
        return False
    cfg = step_dir / "output.json"
    raw = step_dir / "raw.log"
    if cfg.exists():
        return True
    return raw.exists()


def _parse_steps(run_dir: Path, task_steps: list[dict]) -> list[dict[str, Any]]:
    steps_dir = run_dir / "steps"
    if not steps_dir.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for sd in sorted(steps_dir.iterdir(), key=lambda p: p.name):
        if not sd.is_dir():
            continue
        m = _STEP_DIR_RE.match(sd.name)
        if not m:
            continue
        _num, step_id = m.group(1), m.group(2)
        agent = _agent_for_step_id(task_steps, step_id)
        ok = _step_ok(sd)
        dur = _step_duration_sec(sd)
        rows.append(
            {
                "folder": sd.name,
                "step_id": step_id,
                "agent": agent,
                "ok": ok,
                "duration_sec": dur,
            }
        )
    return rows


def _extract_trailing_json_object(text: str) -> dict | None:
    i = text.rfind("{")
    if i < 0:
        return None
    tail = text[i:]
    depth = 0
    end = -1
    for j, ch in enumerate(tail):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = j
                break
    if end < 0:
        return None
    try:
        out = json.loads(tail[: end + 1])
    except json.JSONDecodeError:
        return None
    return out if isinstance(out, dict) else None


def _coerce_verify_dict(po: object) -> dict | None:
    if not isinstance(po, dict):
        return None
    if "tests_passed" in po or "task_completed" in po:
        return po
    t = po.get("text")
    if isinstance(t, str):
        extracted = _extract_trailing_json_object(t)
        if extracted is not None and (
            "tests_passed" in extracted or "task_completed" in extracted
        ):
            return extracted
    return po


def _coerce_review_dict(po: object) -> dict | None:
    if not isinstance(po, dict):
        return None
    if "approved" in po or "task_completed" in po:
        return po
    t = po.get("text")
    if isinstance(t, str):
        extracted = _extract_trailing_json_object(t)
        if extracted is not None and (
            "approved" in extracted or "task_completed" in extracted
        ):
            return extracted
    return po


def _failed_reason_from_md(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    for line in lines[:5]:
        s = line.strip()
        if not s:
            continue
        if s.startswith("#"):
            s = s.lstrip("#").strip()
            if not s:
                continue
        return s
    return ""


def _find_step_output(run_dir: Path, predicate) -> dict | None:
    steps_dir = run_dir / "steps"
    if not steps_dir.is_dir():
        return None
    for sd in sorted(steps_dir.iterdir(), key=lambda p: p.name, reverse=True):
        if not sd.is_dir():
            continue
        if not predicate(sd.name):
            continue
        op = sd / "output.json"
        if not op.exists():
            continue
        try:
            data = _read_json(op)
        except (OSError, json.JSONDecodeError):
            continue
        return data
    return None


def _load_verify_review(run_dir: Path) -> tuple[dict | None, dict | None]:
    def is_verify(name: str) -> bool:
        return "verify" in name

    def is_review(name: str) -> bool:
        return "review" in name and "reverify" not in name

    v_raw = _find_step_output(run_dir, is_verify)
    r_raw = _find_step_output(run_dir, is_review)
    return (
        _coerce_verify_dict(v_raw) if v_raw is not None else None,
        _coerce_review_dict(r_raw) if r_raw is not None else None,
    )


def _first_path_token(line: str) -> str:
    """Extract path from '--- a/foo' or '+++ b/foo' (strip tab junk)."""
    rest = line[4:].strip()
    if not rest:
        return ""
    # Git may use 'a/foo\t (...' or 'a/foo'
    tok = rest.split("\t", 1)[0].strip()
    return tok


def parse_final_patch_files(patch_text: str) -> list[tuple[str, str]]:
    """Return list of (status, path) with status in M/A/D from unified diff text."""
    if not patch_text or not patch_text.strip():
        return []
    lines = patch_text.splitlines()
    i = 0
    out: list[tuple[str, str]] = []
    while i < len(lines):
        line = lines[i]
        if line.startswith("diff --git "):
            parts = line.split()
            b_path = parts[-1] if len(parts) >= 4 else ""
            path = b_path[2:] if b_path.startswith("b/") else b_path
            status = "M"
            j = i + 1
            old_p: str | None = None
            new_p: str | None = None
            while j < len(lines) and not lines[j].startswith("diff --git "):
                lj = lines[j]
                if lj.startswith("new file mode"):
                    status = "A"
                elif lj.startswith("deleted file mode"):
                    status = "D"
                elif lj.startswith("--- "):
                    old_p = _first_path_token(lj)
                elif lj.startswith("+++ "):
                    new_p = _first_path_token(lj)
                j += 1
            if old_p == "/dev/null" and new_p and new_p != "/dev/null":
                status = "A"
                path = new_p[2:] if new_p.startswith("b/") else new_p
            elif new_p == "/dev/null" and old_p and old_p != "/dev/null":
                status = "D"
                path = old_p[2:] if old_p.startswith("a/") else old_p
            elif old_p and new_p and old_p != "/dev/null" and new_p != "/dev/null":
                path = new_p[2:] if new_p.startswith("b/") else new_p
            if path:
                out.append((status, path))
            i = j
            continue
        i += 1
    return out


def load_run_info(run_dir: Path) -> dict[str, Any]:
    task = _read_json(run_dir / "task.json")
    state_path = run_dir / "state.json"
    state_obj: dict[str, Any] = {}
    if state_path.exists():
        try:
            state_obj = _read_json(state_path)
        except (OSError, json.JSONDecodeError):
            state_obj = {}
    raw_steps = task.get("steps") or []
    task_steps = raw_steps if isinstance(raw_steps, list) else []
    steps = _parse_steps(run_dir, [s for s in task_steps if isinstance(s, dict)])
    last_step_dir = steps[-1]["folder"] if steps else ""
    verify, review = _load_verify_review(run_dir)
    patch_path = run_dir / "artifacts" / "final.patch"
    patch_text = ""
    if patch_path.exists():
        try:
            patch_text = patch_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            patch_text = ""
    changed = parse_final_patch_files(patch_text)
    summary_line = ""
    sm = run_dir / "artifacts" / "summary.md"
    if sm.exists():
        try:
            slines = sm.read_text(encoding="utf-8", errors="replace").splitlines()
            summary_line = next((x.strip() for x in slines if x.strip()), "")
        except OSError:
            summary_line = ""
    failed_reason = ""
    failed_reason_state = state_obj.get("failed_reason")
    if isinstance(failed_reason_state, str) and failed_reason_state.strip():
        failed_reason = failed_reason_state.strip()
    else:
        failed_reason = _failed_reason_from_md(run_dir / "failed_reason.md")

    return {
        "run_id": task.get("id") or run_dir.name,
        "task": task.get("task") or "",
        "route": task.get("route") or "",
        "base_sha": task.get("base_sha") or "",
        "state": state_obj.get("state") or "UNKNOWN",
        "steps": steps,
        "verify": verify,
        "review": review,
        "changed_files": changed,
        "summary_first_line": summary_line,
        "final_patch_path": patch_path,
        "final_patch_text": patch_text,
        "failed_reason": failed_reason,
        "last_step_dir": last_step_dir,
    }


def format_status_table_rows(run_dirs: list[Path], limit: int) -> list[tuple[str, str, str, str]]:
    rows: list[tuple[str, str, str, str]] = []
    for rd in run_dirs[:limit]:
        try:
            info = load_run_info(rd)
        except (OSError, json.JSONDecodeError):
            continue
        tid = str(info["run_id"])
        route = str(info["route"])[:40]
        state = str(info["state"])
        tsk = str(info["task"])
        if len(tsk) > 50:
            tsk = tsk[:47] + "..."
        rows.append((tid, route, state, tsk))
    return rows


def print_status_table(run_dirs: list[Path], limit: int = 5) -> None:
    rows = format_status_table_rows(run_dirs, limit)
    if not rows:
        print("(no runs)")
        return
    c1, c2, c3, c4 = 24, 10, 14, 50
    header = (
        "ID".ljust(c1)
        + "ROUTE".ljust(c2)
        + "STATE".ljust(c3)
        + "TASK"
    )
    print(header)
    print("-" * len(header))
    for tid, route, state, tsk in rows:
        print(
            tid.ljust(c1)
            + route.ljust(c2)
            + state.ljust(c3)
            + tsk
        )
