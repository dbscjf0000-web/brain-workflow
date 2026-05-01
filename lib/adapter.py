"""Unified agent subprocess adapter: prompt → run → raw.log → optional JSON parse."""

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Optional, Tuple

from models import AgentConfig, StepResult


def _decode_proc_stream(stream: Any) -> str:
    if stream is None:
        return ""
    if isinstance(stream, str):
        return stream or ""
    return stream.decode("utf-8", "replace") if stream else ""


_RAW_PARSE_THRESHOLD = 5_000_000


def _parse_only(config: AgentConfig, raw: str) -> Tuple[Optional[Any], Optional[str]]:
    """Parse agent output in memory; no filesystem writes."""
    parser_name = config.output_parser
    if parser_name == "raw":
        return None, None
    if parser_name not in ("json", "ndjson_last"):
        raise ValueError(f"unsupported output_parser: {parser_name!r}")

    if len(raw) > _RAW_PARSE_THRESHOLD:
        return None, "output exceeds 5MB; skipping parse"

    try:
        if parser_name == "json":
            parsed: Any = json.loads(raw)
        else:
            parsed = _parse_ndjson_last(raw)
        return parsed, None
    except (json.JSONDecodeError, ValueError) as e:
        return None, str(e)


def _persist_step_outputs(
    step_dir: Path,
    raw: str,
    raw_stderr: str,
    config: AgentConfig,
    parsed: Optional[Any],
    parse_error: Optional[str],
) -> None:
    step_dir.mkdir(parents=True, exist_ok=True)
    (step_dir / "raw.log").write_text(raw, encoding="utf-8")
    if raw_stderr:
        (step_dir / "stderr.log").write_text(raw_stderr, encoding="utf-8")

    parser_name = config.output_parser
    if parser_name not in ("json", "ndjson_last", "raw"):
        raise ValueError(f"unsupported output_parser: {parser_name!r}")

    if parser_name != "raw":
        if parse_error is None and parsed is not None:
            (step_dir / "output.json").write_text(
                json.dumps(parsed, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        elif parse_error is not None:
            (step_dir / "parse_error.md").write_text(
                f"Parser: {parser_name}\nError: {parse_error}\n\nRaw output saved in raw.log",
                encoding="utf-8",
            )


def run_agent(
    config: AgentConfig,
    prompt: str,
    step_dir: Path,
    cwd: str = ".",
    dry_run: bool = False,
) -> StepResult:
    step_dir.mkdir(parents=True, exist_ok=True)
    prompt_file = step_dir / "prompt.md"
    prompt_file.write_text(prompt, encoding="utf-8")

    if dry_run:
        return _run_agent_dry_run(config, step_dir)

    cmd, stdin_data = _build_command(config, prompt, prompt_file)
    merged_env = {**os.environ, **config.env} if config.env else None

    max_attempt = config.retries
    stderr_notes: list[str] = []
    total_duration = 0.0

    last_raw = ""
    last_raw_stderr = ""
    last_exit = 0
    last_parsed: Optional[Any] = None
    last_parse_error: Optional[str] = None

    for attempt in range(max_attempt + 1):
        is_last = attempt == max_attempt
        start = time.time()
        raw_stdout = ""
        raw_stderr = ""
        exit_code = 0
        try:
            result = subprocess.run(
                cmd,
                input=stdin_data,
                capture_output=True,
                text=True,
                timeout=config.timeout_sec,
                cwd=cwd,
                env=merged_env,
                check=False,
            )
            raw_stdout = _decode_proc_stream(result.stdout)
            raw_stderr = _decode_proc_stream(result.stderr)
            exit_code = result.returncode
        except FileNotFoundError:
            raw_stdout = ""
            raw_stderr = (
                f"CLI not found: {config.argv[0]}. Make sure it is installed and on PATH."
            )
            exit_code = -2
        except subprocess.TimeoutExpired as e:
            raw_stdout = _decode_proc_stream(e.stdout)
            raw_stderr = _decode_proc_stream(e.stderr)
            exit_code = -1
        attempt_dur = time.time() - start
        total_duration += attempt_dur

        if exit_code == -2:
            combined_stderr = "\n".join([*stderr_notes, raw_stderr]) if stderr_notes else raw_stderr
            _persist_step_outputs(step_dir, "", combined_stderr, config, None, None)
            return StepResult(
                step_id=step_dir.name,
                agent=config.argv[0],
                exit_code=-2,
                raw_output="",
                parsed_output=None,
                parse_error=None,
                duration_sec=total_duration,
            )

        parsed: Optional[Any]
        parse_error: Optional[str]
        parsed, parse_error = _parse_only(config, raw_stdout)

        success = exit_code == 0 and (
            config.output_parser == "raw" or parse_error is None
        )

        if success:
            combined_stderr = "\n".join([*stderr_notes, raw_stderr]) if stderr_notes else raw_stderr
            _persist_step_outputs(
                step_dir, raw_stdout, combined_stderr, config, parsed, parse_error
            )
            return StepResult(
                step_id=step_dir.name,
                agent=config.argv[0],
                exit_code=exit_code,
                raw_output=raw_stdout,
                parsed_output=parsed,
                parse_error=parse_error,
                duration_sec=total_duration,
            )

        last_raw = raw_stdout
        last_raw_stderr = raw_stderr
        last_exit = exit_code
        last_parsed = parsed
        last_parse_error = parse_error

        if not is_last:
            stderr_notes.append(
                f"attempt {attempt + 1}/{max_attempt + 1} failed (exit_code={exit_code}); retrying..."
            )
            continue

        combined_stderr = "\n".join([*stderr_notes, last_raw_stderr]) if stderr_notes else last_raw_stderr
        _persist_step_outputs(
            step_dir, last_raw, combined_stderr, config, last_parsed, last_parse_error
        )
        return StepResult(
            step_id=step_dir.name,
            agent=config.argv[0],
            exit_code=last_exit,
            raw_output=last_raw,
            parsed_output=last_parsed,
            parse_error=last_parse_error,
            duration_sec=total_duration,
        )


def _run_agent_dry_run(config: AgentConfig, step_dir: Path) -> StepResult:
    """Append-only stub: no subprocess; valid JSON for each parser so the route can finish."""
    kind = _step_kind_from_dir(step_dir.name)
    if kind == "scan":
        stub_obj: Any = {
            "files": [],
            "summary": "dry-run: external agents were not invoked",
            "context": {"dry_run": True},
        }
    elif kind == "implement":
        stub_obj = {
            "summary": "dry-run: no code changes from stub",
            "files": [],
        }
    elif kind == "verify":
        stub_obj = {"tests_passed": True, "summary": "dry-run: tests skipped"}
    elif kind == "review":
        stub_obj = {
            "approved": True,
            "task_completed": True,
            "issues": [],
            "summary": "dry-run: meta-review skipped",
        }
    elif kind == "correct":
        stub_obj = {"summary": "dry-run correction stub"}
    else:
        stub_obj = {"summary": f"dry-run stub ({kind})"}

    parser_name = config.output_parser
    if parser_name not in ("json", "ndjson_last", "raw"):
        raise ValueError(f"unsupported output_parser: {parser_name!r}")

    if parser_name == "raw":
        # Dry-run still needs non-empty downstream context (implement prompt); real
        # "raw" skips JSON parse — here we persist stub text as raw and pass stub dict.
        raw = json.dumps(stub_obj, ensure_ascii=False)
        (step_dir / "raw.log").write_text(raw, encoding="utf-8")
        return StepResult(
            step_id=step_dir.name,
            agent=config.argv[0],
            exit_code=0,
            raw_output=raw,
            parsed_output=stub_obj,
            parse_error=None,
            duration_sec=0.0,
        )

    raw = json.dumps(stub_obj, ensure_ascii=False)
    if parser_name == "ndjson_last":
        raw = raw + "\n"
    (step_dir / "raw.log").write_text(raw, encoding="utf-8")

    if parser_name == "json":
        parsed: Any = json.loads(raw)
    else:
        parsed = _parse_ndjson_last(raw)
    (step_dir / "output.json").write_text(
        json.dumps(parsed, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return StepResult(
        step_id=step_dir.name,
        agent=config.argv[0],
        exit_code=0,
        raw_output=raw,
        parsed_output=parsed,
        parse_error=None,
        duration_sec=0.0,
    )


def _step_kind_from_dir(step_dir_name: str) -> str:
    if "implement" in step_dir_name:
        return "implement"
    if "reverify" in step_dir_name:
        return "verify"
    if "review" in step_dir_name:
        return "review"
    if "verify" in step_dir_name:
        return "verify"
    if "correct" in step_dir_name:
        return "correct"
    if "scan" in step_dir_name:
        return "scan"
    return "other"


def _build_command(
    config: AgentConfig,
    prompt: str,
    prompt_file: Path,
) -> Tuple[list[str], Optional[str]]:
    mode = config.input_mode
    base = list(config.argv)

    if mode == "arg":
        return base + [prompt], None
    if mode == "stdin":
        return base, prompt
    if mode == "file":
        return base + ["--file", str(prompt_file)], None

    raise ValueError(f"unsupported input_mode: {mode!r}")


def _maybe_unfence_json_text(text: str) -> str:
    """Strip optional markdown code fence from agent_message text before JSON parse."""
    s = text.strip()
    if not s.startswith("```"):
        return text
    nl = s.find("\n")
    if nl == -1:
        return text
    s = s[nl + 1 :]
    if s.rstrip().endswith("```"):
        s = s.rstrip()
        s = s[:-3].rstrip()
    return s


def _parse_ndjson_last(raw: str) -> Any:
    objs: list[Any] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            objs.append(json.loads(stripped))
        except json.JSONDecodeError:
            continue

    if not objs:
        raise ValueError("no valid JSON object line (starting with '{') in NDJSON output")

    agent_messages: list[str] = []
    for obj in objs:
        if (
            isinstance(obj, dict)
            and obj.get("type") == "item.completed"
            and isinstance(obj.get("item"), dict)
        ):
            item = obj["item"]
            if item.get("type") == "agent_message":
                text = item.get("text")
                if isinstance(text, str):
                    agent_messages.append(text)

    for text in reversed(agent_messages):
        for candidate in (_maybe_unfence_json_text(text), text):
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue

    if agent_messages:
        return {"text": agent_messages[-1]}

    for j in range(len(objs) - 1, -1, -1):
        o = objs[j]
        if isinstance(o, dict) and o.get("type") != "turn.completed":
            return o

    return objs[-1]
