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
        help="route name from config (default: moderate)",
    )
    run.add_argument(
        "--allow-dirty",
        action="store_true",
        help="allow dirty git worktree",
    )
    run.add_argument(
        "--config",
        type=Path,
        default=None,
        help="path to config.json (default: <install_root>/config.json)",
    )
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)
