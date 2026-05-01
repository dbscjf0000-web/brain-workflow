"""Integration tests v2: moderate route with dry-run stubs (no external CLIs)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _init_clean_git_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "brain-itest@local"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "brain-itest"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    (path / "README.txt").write_text("integration v2 fixture\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.txt"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=path,
        check=True,
        capture_output=True,
    )


class TestIntegrationV2(unittest.TestCase):
    def test_cli_dry_run_moderate_completes_with_done_state(self) -> None:
        root = _repo_root()
        main_py = root / "lib" / "main.py"
        env = {**os.environ, "PYTHONPATH": str(root / "lib")}
        with tempfile.TemporaryDirectory() as td:
            t = Path(td)
            _init_clean_git_repo(t)
            r = subprocess.run(
                [
                    sys.executable,
                    str(main_py),
                    "run",
                    "integration test v2 smoke",
                    "--route",
                    "moderate",
                    "--dry-run",
                ],
                cwd=t,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(r.returncode, 0, msg=r.stderr or r.stdout)
            runs_dir = t / ".brain" / "runs"
            self.assertTrue(runs_dir.is_dir())
            run_dirs = sorted(runs_dir.glob("run-*"))
            self.assertEqual(len(run_dirs), 1)
            run_dir = run_dirs[0]
            st = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(st.get("state"), "DONE")
            self.assertTrue((run_dir / "artifacts" / "summary.md").is_file())
            self.assertTrue((run_dir / "task.json").is_file())

    def test_runner_dry_run_inprocess_same_outcome(self) -> None:
        root = _repo_root()
        lib = str(root / "lib")
        if lib not in sys.path:
            sys.path.insert(0, lib)

        from config import load_config
        from main import _diff_policy_from_defaults, _steps_from_route
        from models import AgentConfig, State, TaskContract
        from runner import run as run_route

        cfg = load_config(root / "config.json")
        with tempfile.TemporaryDirectory() as td:
            t = Path(td)
            _init_clean_git_repo(t)
            base_sha = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=t,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()

            steps = _steps_from_route(cfg, "moderate")
            diff_policy = _diff_policy_from_defaults(cfg)
            contract = TaskContract(
                id="run-integration-inproc",
                task="integration test v2 in-process",
                route="moderate",
                base_sha=base_sha,
                steps=steps,
                diff_policy=diff_policy,
                worktree_path=str(t),
                dry_run=True,
            )
            run_dir = t / ".brain" / "runs" / contract.id
            run_dir.mkdir(parents=True)
            (run_dir / "task.json").write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "id": contract.id,
                        "task": contract.task,
                        "route": contract.route,
                        "base_sha": contract.base_sha,
                        "steps": [
                            {
                                "id": s.id,
                                "agent": s.agent,
                                "distill": s.distill,
                                "input_from": s.input_from,
                            }
                            for s in contract.steps
                        ],
                        "diff_policy": {
                            "allowed_paths": contract.diff_policy.allowed_paths,
                            "forbidden_paths": contract.diff_policy.forbidden_paths,
                            "forbidden_patterns": contract.diff_policy.forbidden_patterns,
                            "max_files": contract.diff_policy.max_files,
                            "max_loc": contract.diff_policy.max_loc,
                            "check_added_lines_only": contract.diff_policy.check_added_lines_only,
                        },
                        "worktree_path": contract.worktree_path,
                        "dry_run": contract.dry_run,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            agents_dict = {
                name: AgentConfig(**data) for name, data in cfg["agents"].items()
            }
            run_route(contract, agents_dict, run_dir, cfg)

            st = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(st.get("state"), State.DONE.value)
            self.assertTrue((run_dir / "artifacts" / "summary.md").is_file())
            scan_dirs = sorted(
                p for p in (run_dir / "steps").iterdir() if p.is_dir() and p.name.endswith("-scan")
            )
            self.assertTrue(scan_dirs)
            self.assertTrue((scan_dirs[0] / "distilled.json").is_file())


if __name__ == "__main__":
    unittest.main()
