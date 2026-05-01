"""Git diff and artifact validation."""

from __future__ import annotations

import re
import subprocess
from fnmatch import fnmatch
from pathlib import Path

from models import DiffPolicy


class ValidationError(Exception):
    """Reserved; not raised by this module."""


def _run_git(args: list[str], cwd: str) -> str:
    r = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if r.returncode != 0:
        detail = r.stderr.strip() or r.stdout.strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {detail}")
    return r.stdout


def _is_under(file_resolved: Path, root_resolved: Path) -> bool:
    try:
        file_resolved.relative_to(root_resolved)
        return True
    except ValueError:
        return False


def _exclude_path(rel: str, cwd: str, exclude_under: Path | None) -> bool:
    if exclude_under is None:
        return False
    return _is_under((Path(cwd).resolve() / rel).resolve(), exclude_under.resolve())


def _changed_paths(cwd: str, exclude_under: Path | None = None) -> list[str]:
    """Paths from git diff against HEAD plus untracked (--exclude-standard)."""
    names = [
        line
        for line in _run_git(["diff", "--name-only", "HEAD"], cwd).splitlines()
        if line.strip()
    ]
    others = [
        line
        for line in _run_git(["ls-files", "--others", "--exclude-standard"], cwd).splitlines()
        if line.strip()
    ]
    seen: dict[str, None] = {}
    for p in names + others:
        if _exclude_path(p, cwd, exclude_under):
            continue
        if p not in seen:
            seen[p] = None
    return list(seen.keys())


def changed_files(cwd: str = ".") -> list[str]:
    return _changed_paths(cwd)


def _total_loc(cwd: str) -> int:
    stat = _run_git(["diff", "--numstat", "HEAD"], cwd)
    total = 0
    for line in stat.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        added_s, deleted_s = parts[0], parts[1]
        if added_s.isdigit() and deleted_s.isdigit():
            total += int(added_s) + int(deleted_s)
    return total


def _pattern_lines_added_only(cwd: str, exclude_under: Path | None) -> list[str]:
    lines: list[str] = []
    diff = _run_git(["diff", "-U0", "HEAD"], cwd)
    for line in diff.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            lines.append(line)
    root = Path(cwd)
    for rel in _run_git(["ls-files", "--others", "--exclude-standard"], cwd).splitlines():
        rel = rel.strip()
        if not rel or _exclude_path(rel, cwd, exclude_under):
            continue
        p = root / rel
        if not p.is_file():
            continue
        for body in p.read_text(errors="replace").splitlines():
            lines.append("+" + body)
    return lines


def _pattern_lines_full_diff(cwd: str, exclude_under: Path | None) -> list[str]:
    lines: list[str] = []
    diff = _run_git(["diff", "HEAD"], cwd)
    lines.extend(diff.splitlines())
    root = Path(cwd)
    for rel in _run_git(["ls-files", "--others", "--exclude-standard"], cwd).splitlines():
        rel = rel.strip()
        if not rel or _exclude_path(rel, cwd, exclude_under):
            continue
        p = root / rel
        if not p.is_file():
            continue
        lines.extend(p.read_text(errors="replace").splitlines())
    return lines


def _first_matching_pattern(line: str, patterns: list[str]) -> str | None:
    for pat in patterns:
        if re.search(pat, line):
            return pat
    return None


def validate_diff(
    policy: DiffPolicy,
    cwd: str = ".",
    *,
    exclude_under: Path | None = None,
) -> list[str]:
    errors: list[str] = []
    changed_files = _changed_paths(cwd, exclude_under)

    if len(changed_files) > policy.max_files:
        errors.append(
            f"Too many changed files: {len(changed_files)} > {policy.max_files}"
        )

    if policy.allowed_paths:
        for f in changed_files:
            if not any(fnmatch(f, p) for p in policy.allowed_paths):
                errors.append(f"Outside allowed paths: {f}")

    if policy.forbidden_paths:
        for f in changed_files:
            if any(fnmatch(f, p) for p in policy.forbidden_paths):
                errors.append(f"Forbidden path: {f}")

    total_loc = _total_loc(cwd)
    if total_loc > policy.max_loc:
        errors.append(f"Too many diff lines (added+deleted): {total_loc} > {policy.max_loc}")

    if policy.forbidden_patterns:
        if policy.check_added_lines_only:
            for line in _pattern_lines_added_only(cwd, exclude_under):
                pat = _first_matching_pattern(line, policy.forbidden_patterns)
                if pat is not None:
                    errors.append(f"Forbidden pattern ({pat}): {line[:200]}")
        else:
            for line in _pattern_lines_full_diff(cwd, exclude_under):
                pat = _first_matching_pattern(line, policy.forbidden_patterns)
                if pat is not None:
                    errors.append(f"Forbidden pattern ({pat}): {line[:200]}")

    return errors


def validate_artifacts(run_dir: Path, required: list[str]) -> list[str]:
    errors: list[str] = []
    base = run_dir / "artifacts"
    for name in required:
        if not (base / name).exists():
            errors.append(f"Missing artifact: {name}")
    return errors
