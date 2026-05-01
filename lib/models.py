from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

class State(str, Enum):
    PLANNING = "PLANNING"
    ACTING = "ACTING"
    VERIFYING = "VERIFYING"
    REVIEW = "REVIEW"
    CORRECTING = "CORRECTING"
    CONSOLIDATING = "CONSOLIDATING"
    ESCALATING = "ESCALATING"
    DONE = "DONE"
    FAILED = "FAILED"

@dataclass
class AgentConfig:
    argv: list[str]
    input_mode: str = "arg"
    output_parser: str = "json"
    timeout_sec: int = 300
    retries: int = 0
    requires_worktree: bool = False
    env: dict[str, str] = field(default_factory=dict)

@dataclass
class Step:
    id: str
    agent: str
    distill: bool = False
    input_from: Optional[str] = None

@dataclass
class DiffPolicy:
    allowed_paths: list[str] = field(default_factory=list)
    forbidden_paths: list[str] = field(default_factory=list)
    forbidden_patterns: list[str] = field(default_factory=list)
    max_files: int = 10
    max_loc: int = 500
    check_added_lines_only: bool = True

@dataclass
class TaskContract:
    id: str
    task: str
    route: str
    base_sha: str
    steps: list[Step]
    diff_policy: DiffPolicy
    worktree_path: Optional[str] = None
    dry_run: bool = False

@dataclass
class StepResult:
    step_id: str
    agent: str
    exit_code: int
    raw_output: str
    parsed_output: Optional[dict]
    parse_error: Optional[str]
    duration_sec: float = 0.0
