from __future__ import annotations

import argparse
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="brain")
    subs = parser.add_subparsers(dest="command", required=True)

    run = subs.add_parser("run", help="run workflow for a task")
    run.add_argument("task", type=str, help="task description")
    run.add_argument(
        "--route",
        default="moderate",
        choices=["auto", "moderate", "simple", "complex"],
        help="route name from config, or 'auto' for keyword-based classification (default: moderate)",
    )
    run.add_argument(
        "--allow-dirty",
        action="store_true",
        help="allow dirty git worktree",
    )
    run.add_argument(
        "--dry-run",
        action="store_true",
        help="simulate agent steps without invoking external CLIs (stub JSON)",
    )
    run.add_argument(
        "--config",
        type=Path,
        default=None,
        help="path to config.json (default: <install_root>/config.json)",
    )

    ap = subs.add_parser(
        "apply",
        help="git apply final.patch from a completed worktree run into the current repo",
    )
    ap.add_argument(
        "run_ref",
        type=str,
        help="run id (e.g. run-20260430-093015) or 'latest'",
    )
    ap.add_argument(
        "--check",
        action="store_true",
        help="run git apply --check only (preview whether the patch applies cleanly)",
    )

    sh = subs.add_parser("show", help="show summary for one run")
    sh.add_argument(
        "run_ref",
        type=str,
        help="run id or 'latest'",
    )

    st = subs.add_parser("status", help="list recent runs in this repo")
    st.add_argument(
        "--limit",
        type=int,
        default=5,
        help="max runs to print (default: 5)",
    )
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run" and (
        not args.task or not str(args.task).strip()
    ):
        parser.error("task description must be non-empty")
    if args.command in ("apply", "show") and (
        not args.run_ref or not str(args.run_ref).strip()
    ):
        parser.error("run id or 'latest' is required")
    return args
