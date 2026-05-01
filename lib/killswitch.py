"""Pre- and post-step kill-switch checks."""

from __future__ import annotations

import subprocess
from pathlib import Path

from models import DiffPolicy


class KillSwitchTriggered(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def pre_run_checks(cwd: str = ".") -> None:
    r = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True,
        cwd=cwd,
        check=False,
    )
    if r.returncode != 0:
        raise KillSwitchTriggered(f"git status failed: {(r.stderr or r.stdout).strip()}")
    if r.stdout.strip():
        raise KillSwitchTriggered(
            "Working directory not clean. Commit or stash first, or use --allow-dirty"
        )


def post_step_checks(step_dir: Path, diff_policy: DiffPolicy, cwd: str = ".") -> list[str]:
    from validator import validate_diff

    return validate_diff(diff_policy, cwd=cwd, exclude_under=step_dir)
