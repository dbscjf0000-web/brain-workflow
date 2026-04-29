from __future__ import annotations

import dataclasses
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from cli import parse_args
from config import load_config
from models import DiffPolicy, Step, TaskContract


def _install_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _git_output(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def _resolve_base_sha(cwd: Path) -> str:
    r = _git_output(["rev-parse", "HEAD"], cwd)
    if r.returncode != 0:
        msg = (r.stderr or r.stdout or "git rev-parse failed").strip()
        raise RuntimeError(msg)
    sha = r.stdout.strip()
    if not sha:
        raise RuntimeError("empty base_sha from git")
    return sha


def _assert_clean_or_allow(cwd: Path, allow_dirty: bool) -> None:
    if allow_dirty:
        return
    r = _git_output(["status", "--porcelain"], cwd)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout or "git status failed").strip())
    if r.stdout.strip():
        sys.stderr.write(
            "error: dirty worktree; commit or stash first, or pass --allow-dirty\n"
        )
        sys.exit(2)


def _steps_from_route(cfg: dict, route: str) -> list[Step]:
    routes = cfg.get("routes") or {}
    if route not in routes:
        names = ", ".join(sorted(routes.keys())) or "(none)"
        raise ValueError(f"unknown route {route!r}; available: {names}")
    spec = routes[route]
    if not isinstance(spec, dict) or "steps" not in spec:
        raise ValueError(f"route {route!r} must have 'steps' array")
    raw_steps = spec["steps"]
    if not isinstance(raw_steps, list):
        raise ValueError(f"route {route!r} steps must be a list")
    out: list[Step] = []
    for i, s in enumerate(raw_steps):
        if not isinstance(s, dict):
            raise ValueError(f"route {route!r} step {i} must be an object")
        sid = s.get("id")
        agent = s.get("agent")
        if not isinstance(sid, str) or not isinstance(agent, str):
            raise ValueError(f"route {route!r} step {i} needs string id and agent")
        out.append(
            Step(
                id=sid,
                agent=agent,
                distill=bool(s.get("distill", False)),
                input_from=s.get("input_from"),
            )
        )
    return out


def _diff_policy_from_defaults(cfg: dict) -> DiffPolicy:
    defaults = cfg.get("defaults") or {}
    dp = defaults.get("diff_policy") or {}
    if not isinstance(dp, dict):
        raise ValueError("defaults.diff_policy must be an object")
    return DiffPolicy(
        allowed_paths=list(dp.get("allowed_paths") or []),
        forbidden_paths=list(dp.get("forbidden_paths") or []),
        forbidden_patterns=list(dp.get("forbidden_patterns") or []),
        max_files=int(dp.get("max_files", 10)),
        max_loc=int(dp.get("max_loc", 500)),
        check_added_lines_only=bool(dp.get("check_added_lines_only", True)),
    )


def _task_contract_to_json_obj(tc: TaskContract) -> dict:
    d = dataclasses.asdict(tc)
    return {"schema_version": "1.0", **d}


def cmd_run(args) -> None:
    root = _install_root()
    cfg_path = args.config if args.config is not None else root / "config.json"
    cfg = load_config(cfg_path)
    cwd = Path.cwd()

    _assert_clean_or_allow(cwd, args.allow_dirty)
    base_sha = _resolve_base_sha(cwd)

    steps = _steps_from_route(cfg, args.route)
    diff_policy = _diff_policy_from_defaults(cfg)

    run_id = f"run-{datetime.now():%Y%m%d-%H%M%S}"
    contract = TaskContract(
        id=run_id,
        task=args.task,
        route=args.route,
        base_sha=base_sha,
        steps=steps,
        diff_policy=diff_policy,
        worktree_path=None,
    )

    run_dir = cwd / ".brain" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    payload = _task_contract_to_json_obj(contract)
    (run_dir / "task.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    raise NotImplementedError("Day 5 작업: runner 미구현")


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if args.command == "run":
        cmd_run(args)
    else:
        raise SystemExit(f"unknown command: {args.command!r}")


if __name__ == "__main__":
    main()
