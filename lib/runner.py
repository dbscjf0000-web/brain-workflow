"""Moderate route: sequential step execution (Phase 0 orchestrator)."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from adapter import run_agent
from distiller import distill
from models import AgentConfig, State, Step, StepResult, TaskContract
from state import save_state
from validator import changed_files, validate_diff

_ROOT = Path(__file__).resolve().parent.parent


def _is_acting_step(step: Step) -> bool:
    return step.id in ("implement", "patch")


def _is_planning_step(step: Step) -> bool:
    """scan/design and other non-acting, non-verify steps stay in PLANNING."""
    if step.id in ("implement", "patch", "verify", "review"):
        return False
    return True


def _extract_trailing_json_object(text: str) -> dict | None:
    """Parse a JSON object that may be appended after prose (common Codex agent_message shape)."""
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


def _coerce_review_dict(po: object) -> object:
    """Flatten {'text': prose + JSON} from ndjson_last into a review result dict."""
    if not isinstance(po, dict):
        return po
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


def _coerce_verify_dict(po: object) -> object:
    """Flatten {'text': prose + JSON} from ndjson_last into a verify result dict when present."""
    if not isinstance(po, dict):
        return po
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


def _has_real_test_command(tc: object) -> bool:
    if not tc or not isinstance(tc, str):
        return False
    s = tc.strip().lower()
    if not s:
        return False
    placeholders = (
        "n/a",
        "none",
        "no",
        "no tests",
        "no test",
        "no test command",
        "-",
    )
    if s in placeholders or s.startswith("n/a"):
        return False
    return True


def _setup_worktree(
    run_dir: Path, contract: TaskContract, base_sha: str, repo_root: Path
) -> None:
    """Create a detached worktree at run_dir/worktree; sets contract.worktree_path."""
    worktree_path = (run_dir / "worktree").resolve()
    r = subprocess.run(
        ["git", "worktree", "add", "--detach", str(worktree_path), base_sha],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    if r.returncode != 0:
        detail = (r.stderr or r.stdout or "git worktree add failed").strip()
        raise RuntimeError(detail or "git worktree add failed")
    contract.worktree_path = str(worktree_path)


def _teardown_worktree(
    contract: TaskContract, repo_root: Path, run_dir: Path
) -> None:
    """Best-effort removal of this run's linked worktree only; never raises."""
    if not contract.worktree_path:
        return
    wp = Path(contract.worktree_path).resolve()
    expected = (run_dir / "worktree").resolve()
    if wp != expected:
        return
    try:
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(wp)],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        pass


def run(
    contract: TaskContract,
    agents: dict[str, AgentConfig],
    run_dir: Path,
    cfg: dict,
) -> None:
    repo_root = Path.cwd().resolve()
    save_state(run_dir, State.PLANNING)
    try:
        _run_loop(contract, agents, run_dir, cfg, repo_root)
    finally:
        _teardown_worktree(contract, repo_root, run_dir)


def _run_loop(
    contract: TaskContract,
    agents: dict[str, AgentConfig],
    run_dir: Path,
    cfg: dict,
    repo_root: Path,
) -> None:
    previous_output: object | None = None
    max_correct_attempts = int(
        cfg.get("defaults", {})
        .get("runtime", {})
        .get("max_correct_attempts", 1)
    )
    for i, step in enumerate(contract.steps):
        cwd = contract.worktree_path or "."
        step_dir = run_dir / "steps" / f"{i + 1:02d}-{step.id}"
        step_dir.mkdir(parents=True, exist_ok=True)

        agent_config = agents[step.agent]
        prompt = _build_prompt(step, contract, previous_output)

        if _is_planning_step(step):
            save_state(run_dir, State.PLANNING)
        if _is_acting_step(step):
            save_state(run_dir, State.ACTING)
            if agent_config.requires_worktree:
                if not contract.worktree_path:
                    try:
                        _setup_worktree(
                            run_dir, contract, contract.base_sha, repo_root
                        )
                    except Exception as e:
                        _fail(run_dir, f"worktree setup failed: {e}")
                cwd = contract.worktree_path or "."
        elif step.id == "verify":
            save_state(run_dir, State.VERIFYING)
        elif step.id == "review":
            save_state(run_dir, State.REVIEW)

        result = run_agent(
            agent_config, prompt, step_dir, cwd=cwd, dry_run=contract.dry_run
        )

        if result.exit_code == -1:
            _fail(run_dir, "Agent timeout or subprocess failure (exit_code=-1).")
        if result.exit_code == -2:
            _fail(
                run_dir,
                f"agent CLI not found: {agent_config.argv[0]}",
            )

        if result.parsed_output is not None and step.distill:
            try:
                if isinstance(result.parsed_output, dict):
                    previous_output = distill(result.parsed_output, step_dir)
                else:
                    previous_output = result.parsed_output
            except Exception:
                previous_output = {"raw": result.raw_output[:5000]}
        elif result.parsed_output is not None:
            previous_output = result.parsed_output
        else:
            previous_output = {"raw": result.raw_output[:5000]}

        if _is_acting_step(step):
            _save_git_diff(step_dir, cwd)
            if not contract.dry_run:
                changed = changed_files(cwd=cwd)
                if not changed:
                    save_state(
                        run_dir,
                        State.ESCALATING,
                        extra={
                            "failed_reason": f"{step.id} step produced no changes (empty diff). "
                            "Agent may have failed to apply edits."
                        },
                    )
                    _fail(
                        run_dir,
                        f"{step.id} step produced no changes (empty diff). "
                        "Agent may have failed to apply edits.",
                    )
                errors = validate_diff(contract.diff_policy, cwd=cwd)
                if errors:
                    save_state(
                        run_dir,
                        State.ESCALATING,
                        extra={"validation_errors": errors},
                    )
                    _fail(
                        run_dir,
                        "validate_diff failed:\n"
                        + "\n".join(f"  - {e}" for e in errors),
                    )

        if step.id == "verify":
            po = _coerce_verify_dict(result.parsed_output)
            verify_failed = result.exit_code != 0 or po is None
            if not verify_failed and isinstance(po, dict):
                if "task_completed" in po:
                    if po.get("task_completed") is False:
                        verify_failed = True
                else:
                    print(
                        "[brain-workflow] verify: missing task_completed in response; "
                        "not failing (backward compatibility).",
                        file=sys.stderr,
                    )
                    (step_dir / "task_completion_unverified").touch()
                if (
                    not verify_failed
                    and _has_real_test_command(po.get("test_command"))
                    and po.get("tests_passed") is False
                ):
                    verify_failed = True
            if verify_failed:
                recovered = False
                if max_correct_attempts > 0:
                    save_state(run_dir, State.CORRECTING)
                    for _ in range(max_correct_attempts):
                        ok = _attempt_correction(
                            contract,
                            agents,
                            run_dir,
                            result,
                            cwd,
                            step,
                            previous_output,
                        )
                        if ok:
                            recovered = True
                            break
                if not recovered:
                    save_state(run_dir, State.ESCALATING)
                    _fail(
                        run_dir,
                        "verify failed (exit code, parse failure, tests_passed=false, "
                        "or task_completed=false); "
                        "correction did not recover or was disabled (max_correct_attempts=0).",
                    )

        if step.id == "review":
            po = _coerce_review_dict(result.parsed_output)
            review_failed = result.exit_code != 0 or po is None or not isinstance(
                po, dict
            )
            if not review_failed:
                if po.get("approved") is False:
                    review_failed = True
                if po.get("task_completed") is False:
                    review_failed = True
                issues = po.get("issues") or []
                if isinstance(issues, list):
                    for issue in issues:
                        if (
                            isinstance(issue, dict)
                            and issue.get("severity") == "blocking"
                        ):
                            review_failed = True
                            break
            if review_failed:
                save_state(run_dir, State.ESCALATING)
                _fail(
                    run_dir,
                    "review failed (exit code, parse failure, approved=false, "
                    "task_completed=false, or blocking severity in issues).",
                )

    save_state(run_dir, State.CONSOLIDATING)
    consolidate_cwd = contract.worktree_path or "."
    _consolidate(run_dir, contract, consolidate_cwd)
    save_state(run_dir, State.DONE)


def _build_prompt(step: Step, contract: TaskContract, prev_output: object | None) -> str:
    template_path = _ROOT / "prompts" / f"{step.id}.md"
    if template_path.exists():
        text = template_path.read_text(encoding="utf-8")
    else:
        text = ""

    allowed = ", ".join(contract.diff_policy.allowed_paths) or (
        "(no restriction; only forbidden_paths apply)"
    )
    if prev_output is None:
        prev_s = "없음"
    elif isinstance(prev_output, str):
        prev_s = prev_output
    else:
        prev_s = json.dumps(prev_output, ensure_ascii=False)

    return (
        text.replace("{{task}}", contract.task)
        .replace("{{allowed_paths}}", allowed)
        .replace("{{previous_output}}", prev_s)
    )


def _save_git_diff(step_dir: Path, cwd: str) -> None:
    r = subprocess.run(
        ["git", "diff", "HEAD"],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    out = r.stdout if r.returncode == 0 else (r.stdout or r.stderr or "")
    (step_dir / "diff.patch").write_text(out, encoding="utf-8")


def _attempt_correction(
    contract: TaskContract,
    agents: dict[str, AgentConfig],
    run_dir: Path,
    failed_result: StepResult,
    cwd: str,
    verify_step: Step,
    previous_output_for_verify: object | None,
) -> bool:
    if "codex_patch" in agents:
        patch_agent = agents["codex_patch"]
    else:
        patch_agent = agents["codex_verify"]

    correct_dir = run_dir / "steps" / "04-correct"
    correct_dir.mkdir(parents=True, exist_ok=True)

    po = failed_result.parsed_output
    raw = failed_result.raw_output or ""
    ec = failed_result.exit_code
    detail = json.dumps(
        {"exit_code": ec, "parsed": po, "raw_excerpt": raw[:4000]},
        ensure_ascii=False,
    )
    patch_prompt = (
        "The verification step failed. Fix the code so tests pass.\n\n"
        f"Task: {contract.task}\n\nFailure detail (JSON):\n{detail}\n\n"
        "Make minimal fixes. Respond with JSON describing what you changed."
    )

    patch_res = run_agent(
        patch_agent, patch_prompt, correct_dir, cwd=cwd, dry_run=contract.dry_run
    )
    if patch_res.exit_code == -1:
        return False
    if patch_res.exit_code == -2:
        return False

    reverify_dir = run_dir / "steps" / "05-reverify"
    reverify_dir.mkdir(parents=True, exist_ok=True)

    verify_agent = agents[verify_step.agent]
    merged_prev: object
    if patch_res.parsed_output is not None:
        merged_prev = {
            "prior_context": previous_output_for_verify,
            "patch_output": patch_res.parsed_output,
        }
    else:
        merged_prev = {
            "prior_context": previous_output_for_verify,
            "patch_raw": patch_res.raw_output[:3000],
        }

    vprompt = _build_prompt(verify_step, contract, merged_prev)
    vres = run_agent(
        verify_agent, vprompt, reverify_dir, cwd=cwd, dry_run=contract.dry_run
    )
    if vres.exit_code == -1:
        return False
    if vres.exit_code == -2:
        return False
    if vres.exit_code != 0:
        return False
    if vres.parsed_output is None:
        return False
    vpo = _coerce_verify_dict(vres.parsed_output)
    if isinstance(vpo, dict):
        if "task_completed" in vpo and vpo.get("task_completed") is False:
            return False
        if "task_completed" not in vpo:
            print(
                "[brain-workflow] reverify: missing task_completed in response; "
                "not failing correction (backward compatibility).",
                file=sys.stderr,
            )
            (reverify_dir / "task_completion_unverified").touch()
        if _has_real_test_command(vpo.get("test_command")) and vpo.get(
            "tests_passed"
        ) is False:
            return False
    return True


def _consolidate(run_dir: Path, contract: TaskContract, cwd: str) -> None:
    art = run_dir / "artifacts"
    art.mkdir(parents=True, exist_ok=True)

    summary_lines = [
        f"# Run {contract.id}",
        "",
        f"- **Task**: {contract.task}",
        f"- **Route**: {contract.route}",
        f"- **base_sha**: {contract.base_sha}",
        "",
    ]
    (art / "summary.md").write_text("\n".join(summary_lines), encoding="utf-8")

    r = subprocess.run(
        ["git", "diff", "HEAD"],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    diff_text = r.stdout if r.returncode == 0 else (r.stdout or r.stderr or "")
    (art / "final.patch").write_text(diff_text, encoding="utf-8")

    verify_dirs = sorted(
        d
        for d in (run_dir / "steps").iterdir()
        if d.is_dir() and "verify" in d.name
    )
    test_src: Path | None = None
    if verify_dirs:
        last = verify_dirs[-1]
        if (last / "raw.log").exists():
            test_src = last / "raw.log"
    if test_src is not None:
        shutil.copy2(test_src, art / "test.log")
    else:
        (art / "test.log").write_text("(no verify raw.log found)\n", encoding="utf-8")

    _append_decision(run_dir, contract)


def _append_decision(run_dir: Path, contract: TaskContract) -> None:
    """Append a DONE entry to <cwd>/.brain/decisions.md (best-effort; never raises)."""
    try:
        cwd = Path.cwd()
        decisions = cwd / ".brain" / "decisions.md"
        decisions.parent.mkdir(parents=True, exist_ok=True)

        patch = run_dir / "artifacts" / "final.patch"
        n_files = 0
        if patch.exists():
            for line in patch.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.startswith("diff --git "):
                    n_files += 1

        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = (
            f"\n## {ts} - {contract.id}\n"
            f"- **route**: {contract.route}\n"
            f"- **task**: {contract.task}\n"
            f"- **result**: DONE\n"
            f"- **changed_files**: {n_files}\n"
        )

        if not decisions.exists():
            decisions.write_text(
                "# decisions log\n\n"
                "History of completed brain runs in this project.\n"
                + entry,
                encoding="utf-8",
            )
        else:
            with decisions.open("a", encoding="utf-8") as f:
                f.write(entry)
    except OSError:
        pass


def _fail(run_dir: Path, reason: str) -> None:
    body = "\n".join(
        [
            "# Failure",
            "",
            reason,
            "",
            "## repro_command",
            "Re-run from repository root with the same task and flags as this run "
            "(see task.json for the exact contract).",
        ]
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "failed_reason.md").write_text(body, encoding="utf-8")

    art = run_dir / "artifacts"
    art.mkdir(parents=True, exist_ok=True)
    steps_lines: list[str] = []
    steps_dir = run_dir / "steps"
    if steps_dir.is_dir():
        for sd in sorted(steps_dir.iterdir()):
            if sd.is_dir():
                steps_lines.append(f"- {sd.name}")
    steps_block = (
        "\n".join(steps_lines) if steps_lines else "(no step directories yet)"
    )
    summary_md = f"# Run FAILED\n\n{reason}\n\n## Steps reached\n{steps_block}\n"
    (art / "summary.md").write_text(summary_md, encoding="utf-8")

    if steps_dir.is_dir():
        with_patch = sorted(
            (
                sd
                for sd in steps_dir.iterdir()
                if sd.is_dir() and (sd / "diff.patch").exists()
            ),
            key=lambda p: p.name,
        )
        if with_patch:
            shutil.copy2(with_patch[-1] / "diff.patch", art / "final.patch")

    save_state(run_dir, State.FAILED, extra={"failed_reason": reason})
    raise SystemExit(1)
