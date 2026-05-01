from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REQUIRED_TOP = frozenset({"schema_version", "agents", "routes", "defaults"})

INPUT_MODES = frozenset({"arg", "stdin", "file"})
OUTPUT_PARSERS = frozenset({"json", "ndjson_last", "raw"})


def _expect_positive_int(value: Any, path: str) -> None:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{path} must be a positive int")


def _expect_non_negative_int(value: Any, path: str) -> None:
    if type(value) is not int or value < 0:
        raise ValueError(f"{path} must be a non-negative int")


def _validate_agent(name: str, ac: Any) -> None:
    prefix = f"agents.{name}"
    if not isinstance(ac, dict):
        raise ValueError(f"{prefix} must be an object")

    if "argv" not in ac:
        raise ValueError(f"{prefix}.argv is required")
    argv = ac["argv"]
    if not isinstance(argv, list) or len(argv) == 0:
        raise ValueError(f"{prefix}.argv must be non-empty list of strings")
    for part in argv:
        if not isinstance(part, str) or part == "":
            raise ValueError(f"{prefix}.argv must be non-empty list of strings")

    im = ac.get("input_mode")
    if im is not None and im not in INPUT_MODES:
        raise ValueError(
            f"{prefix}.input_mode must be one of {sorted(INPUT_MODES)}"
        )

    op = ac.get("output_parser")
    if op is not None and op not in OUTPUT_PARSERS:
        raise ValueError(
            f"{prefix}.output_parser must be one of {sorted(OUTPUT_PARSERS)}"
        )

    ts = ac.get("timeout_sec")
    if ts is not None:
        _expect_positive_int(ts, f"{prefix}.timeout_sec")

    ret = ac.get("retries")
    if ret is not None:
        _expect_non_negative_int(ret, f"{prefix}.retries")

    rw = ac.get("requires_worktree")
    if rw is not None and not isinstance(rw, bool):
        raise ValueError(f"{prefix}.requires_worktree must be a bool")

    env = ac.get("env")
    if env is not None:
        if not isinstance(env, dict):
            raise ValueError(f"{prefix}.env must be an object/dict")
        for k, v in env.items():
            if not isinstance(k, str) or not isinstance(v, str):
                raise ValueError(
                    f"{prefix}.env: keys and values must be strings, "
                    f"got {type(k).__name__}={type(v).__name__}"
                )


def _validate_route(route_name: str, route: Any, agent_names: set[str]) -> None:
    prefix = f"routes.{route_name}"
    if not isinstance(route, dict):
        raise ValueError(f"{prefix} must be an object")

    if "steps" not in route:
        raise ValueError(f"{prefix}.steps is required")
    steps = route["steps"]
    if not isinstance(steps, list) or len(steps) == 0:
        raise ValueError(f"{prefix}.steps must be a non-empty list")

    preceding_ids: set[str] = set()
    for i, step in enumerate(steps):
        sp = f"{prefix}.steps[{i}]"
        if not isinstance(step, dict):
            raise ValueError(f"{sp} must be an object")
        if "id" not in step:
            raise ValueError(f"{sp}.id is required")
        if "agent" not in step:
            raise ValueError(f"{sp}.agent is required")
        sid = step["id"]
        ag = step["agent"]
        if not isinstance(sid, str) or sid == "":
            raise ValueError(f"{sp}.id must be a non-empty string")
        if not isinstance(ag, str) or ag == "":
            raise ValueError(f"{sp}.agent must be a non-empty string")
        if ag not in agent_names:
            raise ValueError(
                f"{sp}.agent {ag!r} is not defined under agents"
            )
        if step.get("distill") is not None and not isinstance(
            step["distill"], bool
        ):
            raise ValueError(f"{sp}.distill must be a bool")
        inf = step.get("input_from")
        if inf is not None:
            if not isinstance(inf, str):
                raise ValueError(f"{sp}.input_from must be a string")
            if inf not in preceding_ids:
                raise ValueError(
                    f"route {route_name!r} step {i}: input_from {inf!r} does not refer to a preceding step id"
                )
        preceding_ids.add(sid)


def _validate_defaults(defaults: Any) -> None:
    if not isinstance(defaults, dict):
        raise ValueError("defaults must be an object")

    dp = defaults.get("diff_policy")
    if dp is not None:
        if not isinstance(dp, dict):
            raise ValueError("defaults.diff_policy must be an object")
        if "max_files" in dp:
            _expect_positive_int(dp["max_files"], "defaults.diff_policy.max_files")
        if "max_loc" in dp:
            _expect_positive_int(dp["max_loc"], "defaults.diff_policy.max_loc")

    rt = defaults.get("runtime")
    if rt is not None:
        if not isinstance(rt, dict):
            raise ValueError("defaults.runtime must be an object")
        if "max_total_sec" in rt:
            _expect_positive_int(rt["max_total_sec"], "defaults.runtime.max_total_sec")
        if "max_correct_attempts" in rt:
            _expect_non_negative_int(
                rt["max_correct_attempts"],
                "defaults.runtime.max_correct_attempts",
            )


def load_config(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    raw = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("config must be a JSON object")
    missing = REQUIRED_TOP - raw.keys()
    if missing:
        raise ValueError(f"config missing keys: {sorted(missing)}")
    ver = raw.get("schema_version")
    if ver != "1.0":
        raise ValueError(f"unsupported schema_version: {ver!r} (expected '1.0')")
    if not isinstance(raw["agents"], dict):
        raise ValueError("agents must be an object")
    if not isinstance(raw["routes"], dict):
        raise ValueError("routes must be an object")
    if not isinstance(raw["defaults"], dict):
        raise ValueError("defaults must be an object")

    for name, ac in raw["agents"].items():
        if not isinstance(name, str):
            raise ValueError("agents keys must be strings")
        _validate_agent(name, ac)

    agent_names = set(raw["agents"].keys())
    for route_name, route in raw["routes"].items():
        if not isinstance(route_name, str):
            raise ValueError("routes keys must be strings")
        _validate_route(route_name, route, agent_names)

    _validate_defaults(raw["defaults"])

    return raw
