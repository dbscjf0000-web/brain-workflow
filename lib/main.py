from __future__ import annotations

import dataclasses
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from cli import parse_args
from config import load_config
from models import AgentConfig, DiffPolicy, Step, TaskContract
from runner import run as run_route
from runinfo import (
    list_run_dirs,
    load_run_info,
    print_status_table,
    resolve_run_dir,
)


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


def _require_clean_worktree(cwd: Path, context: str) -> None:
    r = _git_output(["status", "--porcelain"], cwd)
    if r.returncode != 0:
        sys.stderr.write(
            f"error: {context}: git status failed: "
            f"{(r.stderr or r.stdout or '').strip()}\n"
        )
        sys.exit(2)
    if r.stdout.strip():
        sys.stderr.write(
            f"error: {context}: working tree has uncommitted changes. "
            "Commit or stash first. (--force not implemented)\n"
        )
        sys.exit(2)


def _short_sha(sha: str, n: int = 7) -> str:
    s = (sha or "").strip()
    return s[:n] if len(s) >= n else s


def _format_bool_key(d: dict | None, key: str) -> str | None:
    if d is None or key not in d:
        return None
    v = d.get(key)
    return f"{key}={v!r}"


def cmd_apply(args) -> None:
    cwd = Path.cwd().resolve()
    _require_clean_worktree(cwd, "brain apply")
    rrev = _git_output(["rev-parse", "--git-dir"], cwd)
    if rrev.returncode != 0:
        sys.stderr.write(
            "error: brain apply must be run inside a git repository "
            f"({(rrev.stderr or rrev.stdout or '').strip()})\n"
        )
        sys.exit(2)

    try:
        run_dir = resolve_run_dir(cwd, args.run_ref)
    except FileNotFoundError as e:
        sys.stderr.write(f"error: {e}\n")
        sys.exit(2)

    info = load_run_info(run_dir)
    st = str(info.get("state") or "")
    if st != "DONE":
        sys.stderr.write(
            f"error: run {info.get('run_id')} is not DONE (state={st!r}); "
            "cannot apply final.patch. (--force not implemented)\n"
        )
        sys.exit(2)

    patch_path: Path = info["final_patch_path"]
    if not patch_path.exists():
        sys.stderr.write(f"error: missing {patch_path} (no final.patch for this run)\n")
        sys.exit(2)

    route = str(info.get("route") or "")
    patch_text: str = info.get("final_patch_text") or ""
    changed = info.get("changed_files") or []

    if route == "simple":
        print(
            "brain apply: route 'simple' applies edits in the repo during the run; "
            "there is nothing to apply from final.patch here (already on the working tree)."
        )
        return

    if not patch_text.strip():
        print("brain apply: final.patch is empty; nothing to do.")
        return

    print("Changes from final.patch:")
    for status, path in changed:
        print(f"  {status} {path}")
    if not changed:
        print("  (could not parse file list; still attempting git apply)")

    if args.check:
        chk = subprocess.run(
            ["git", "apply", "--check", str(patch_path)],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=False,
        )
        if chk.returncode != 0:
            err = (chk.stderr or chk.stdout or "").strip()
            sys.stderr.write(
                "error: git apply --check failed (patch does not apply cleanly to "
                f"current HEAD). Possible causes: wrong base commit, conflicting local "
                f"changes (unexpected if tree was clean), or line-ending/path mismatch.\n\n"
                f"git stderr/stdout:\n{err}\n"
            )
            sys.exit(2)
        print("git apply --check: OK (patch would apply cleanly).")
        return

    ap = subprocess.run(
        ["git", "apply", str(patch_path)],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    if ap.returncode != 0:
        err = (ap.stderr or ap.stdout or "").strip()
        sys.stderr.write(
            "error: git apply failed. Common causes: patch already applied, "
            "branch moved, or merge conflicts with hunks below.\n\n"
            f"git stderr/stdout:\n{err}\n"
        )
        sys.exit(2)

    names = _git_output(["diff", "--name-only", "HEAD"], cwd)
    if names.returncode != 0:
        sys.stderr.write(
            f"warning: patch applied but could not list files: "
            f"{(names.stderr or '').strip()}\n"
        )
        return
    files = [ln for ln in names.stdout.splitlines() if ln.strip()]
    print("Applied. Changed files:")
    for f in files:
        print(f"  {f}")


def cmd_show(args) -> None:
    cwd = Path.cwd().resolve()
    try:
        run_dir = resolve_run_dir(cwd, args.run_ref)
    except FileNotFoundError as e:
        sys.stderr.write(f"error: {e}\n")
        sys.exit(2)

    info = load_run_info(run_dir)
    print(f"  Run: {info['run_id']}")
    print(f"  Task: {info['task']}")
    print(f"  Route: {info['route']}")
    print(f"  State: {info['state']}")
    if str(info.get("state") or "") == "FAILED":
        reason = str(info.get("failed_reason") or "").strip()
        if reason:
            print(f"  failed_reason: {reason}")
        failed_at = str(info.get("last_step_dir") or "").strip() or "(unknown)"
        print(f"  Failed at step: {failed_at}")
    print(f"  Base SHA: {_short_sha(str(info.get('base_sha') or ''))}")
    print("")
    print("  Steps:")
    for s in info.get("steps") or []:
        folder = s.get("folder") or ""
        agent = s.get("agent") or "?"
        ok = s.get("ok")
        status = "OK" if ok else "FAIL"
        dur = s.get("duration_sec")
        dur_s = f"{dur:.1f}s" if isinstance(dur, (int, float)) else "?"
        print(f"    {folder:<14} ({agent}, {status}, {dur_s})")
    print("")
    cfs = info.get("changed_files") or None
    if info.get("final_patch_path") and (
        Path(info["final_patch_path"]).exists() or cfs
    ):
        print("  Changed files (final.patch):")
        if cfs:
            for status, path in cfs:
                print(f"    {status} {path}")
        else:
            print("    (patch present but no files parsed)")
    print("")

    v = info.get("verify")
    vparts = [
        x for x in (_format_bool_key(v, "task_completed"), _format_bool_key(v, "tests_passed")) if x
    ]
    print(f"  Verify: {', '.join(vparts) if vparts else '(no verify output)'}")

    task_path = run_dir / "task.json"
    try:
        raw_task = json.loads(task_path.read_text(encoding="utf-8"))
        step_ids = [
            s.get("id")
            for s in (raw_task.get("steps") or [])
            if isinstance(s, dict)
        ]
    except (OSError, json.JSONDecodeError):
        step_ids = []
    has_review = "review" in step_ids
    r = info.get("review")
    if has_review or r is not None:
        rparts = [
            x for x in (_format_bool_key(r, "approved"), _format_bool_key(r, "task_completed")) if x
        ]
        print(f"  Review: {', '.join(rparts) if rparts else '(no review output)'}")

    summ = info.get("summary_first_line") or ""
    print(f"  Summary: {summ}")


def cmd_status(args) -> None:
    cwd = Path.cwd().resolve()
    dirs = list_run_dirs(cwd)
    print_status_table(dirs, limit=max(1, int(args.limit)))


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

    if args.route == "auto":
        from classifier import classify

        route = classify(args.task)
        print(f"  auto-classified route: {route}")
    else:
        route = args.route

    steps = _steps_from_route(cfg, route)
    diff_policy = _diff_policy_from_defaults(cfg)

    run_id = f"run-{datetime.now():%Y%m%d-%H%M%S}"
    contract = TaskContract(
        id=run_id,
        task=args.task,
        route=route,
        base_sha=base_sha,
        steps=steps,
        diff_policy=diff_policy,
        worktree_path=None,
        dry_run=bool(args.dry_run),
    )

    run_dir = cwd / ".brain" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    payload = _task_contract_to_json_obj(contract)
    (run_dir / "task.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    agents_dict = {
        name: AgentConfig(**cfg_data) for name, cfg_data in cfg["agents"].items()
    }
    run_route(contract, agents_dict, run_dir, cfg)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if args.command == "run":
        cmd_run(args)
    elif args.command == "apply":
        cmd_apply(args)
    elif args.command == "show":
        cmd_show(args)
    elif args.command == "status":
        cmd_status(args)
    else:
        raise SystemExit(f"unknown command: {args.command!r}")


if __name__ == "__main__":
    main()
