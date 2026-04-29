# v3: Python 구현 명세 (현재 작업본)

> 작성일: 2026-04-28
> 기반: [03-architecture-v2.md](03-architecture-v2.md) + 2차 피드백
> 언어: Python 3.10+ (표준 라이브러리만, 외부 pip 의존성 0)
> 상태: 설계 완료, 구현 대기

---

## v2 → v3 변경점

| 항목 | v2 | v3 (최종) |
|------|-----|-----------|
| 언어 | bash + jq | Python 3 |
| config | YAML (yq 의존) | JSON (파싱 내장) |
| 상태 관리 | state.sh 일반화 | 순차 함수 + state.json |
| events.ndjson | 포함 | 삭제 (step 폴더로 충분) |
| 비용 kill-switch | hard fail | soft limit (사후 기록) |
| 금지 패턴 | 전체 diff 대상 | 추가 라인만 (`+` lines) |
| Phase 0 범위 | simple/moderate/complex | **moderate만** |
| diff 생성 | 에이전트 출력 | `git diff`로 생성 |
| 출력 저장 | output.json만 | raw.log + output.json + parse_error.md |
| agent adapter | argv만 | argv + input_mode + output_parser |
| worktree | 옵션 | 기본값 (ACT 단계 필수) |
| decisions.md | 매 실행 업데이트 | 정책 변경 시에만 |

---

## 1. 의존성

```
Python 3.10+  (macOS 기본 포함)
  json, subprocess, pathlib, dataclasses,
  argparse, shutil, fnmatch, signal, textwrap (모두 내장)

외부 의존성: 없음
선택적: jq (디버깅용)
```

---

## 2. 파일 구조 (목표)

```
brain-workflow/
├── bin/
│   └── brain                    # bash 래퍼 (3줄)
├── lib/
│   ├── __init__.py
│   ├── main.py                  # 진입점
│   ├── cli.py                   # CLI 인자 파싱
│   ├── config.py                # config.json 로드/검증
│   ├── models.py                # dataclass: TaskContract, AgentConfig
│   ├── runner.py                # 오케스트레이터
│   ├── adapter.py               # 에이전트 어댑터
│   ├── distiller.py             # 시상 필터
│   ├── validator.py             # diff/artifact 검증
│   ├── killswitch.py            # timeout, paths
│   └── state.py                 # state.json CRUD
├── prompts/
│   ├── scan.md
│   ├── implement.md
│   ├── verify.md
│   ├── design.md                # Phase 1+
│   └── review.md                # Phase 1+
├── config.json                  # 에이전트 설정
└── .brain/                      # 프로젝트별 (gitignore)
    ├── decisions.md
    └── runs/
```

### bin/brain (래퍼)

```bash
#!/bin/bash
exec python3 "$(dirname "$(realpath "$0")")/../lib/main.py" "$@"
```

---

## 3. config.json (실제 사용본)

```json
{
  "schema_version": "1.0",

  "agents": {
    "gemini_scan": {
      "argv": ["gemini", "-p", "--output-format", "json"],
      "input_mode": "arg",
      "output_parser": "json",
      "timeout_sec": 120,
      "retries": 0
    },
    "claude_design": {
      "argv": ["claude", "-p", "--output-format", "json", "--max-turns", "3"],
      "input_mode": "arg",
      "output_parser": "json",
      "timeout_sec": 300,
      "retries": 1
    },
    "cursor_edit": {
      "argv": ["cursor-agent", "-p", "--output-format", "json"],
      "input_mode": "arg",
      "output_parser": "json",
      "timeout_sec": 600,
      "retries": 0,
      "requires_worktree": true
    },
    "codex_verify": {
      "argv": ["codex", "exec", "--json"],
      "input_mode": "stdin",
      "output_parser": "ndjson_last",
      "timeout_sec": 300,
      "retries": 1
    },
    "codex_patch": {
      "argv": ["codex", "exec", "--json"],
      "input_mode": "stdin",
      "output_parser": "ndjson_last",
      "timeout_sec": 300,
      "retries": 0
    }
  },

  "routes": {
    "moderate": {
      "steps": [
        {"id": "scan",      "agent": "gemini_scan",  "distill": true},
        {"id": "implement", "agent": "cursor_edit",   "input_from": "scan"},
        {"id": "verify",    "agent": "codex_verify",  "input_from": "implement"}
      ]
    }
  },

  "defaults": {
    "diff_policy": {
      "forbidden_paths": [".env*", "*.secret", "*.lock", "node_modules/**"],
      "forbidden_patterns": ["(?i)api[_-]?key\\s*=\\s*['\"][^'\"]{16,}"],
      "max_files": 10,
      "max_loc": 500,
      "check_added_lines_only": true
    },
    "runtime": {
      "max_total_sec": 1800,
      "max_correct_attempts": 1,
      "on_timeout": "save_and_stop",
      "on_failure": "save_reason_and_escalate"
    },
    "artifacts": {
      "required": ["summary.md"],
      "optional": ["diff.patch", "test.log", "risks.md"]
    }
  }
}
```

### input_mode

| mode | 동작 | 예시 |
|------|------|------|
| `arg` | argv 마지막에 프롬프트 | `gemini -p "..."` |
| `stdin` | 프롬프트를 stdin으로 | `echo "..." \| codex exec` |
| `file` | tmp 파일로 저장 후 경로 전달 | `cursor-agent -p --file /tmp/p.md` |

### output_parser

| parser | 동작 |
|--------|------|
| `json` | stdout 전체를 `json.loads()` |
| `ndjson_last` | stdout 마지막 유효 JSON 라인 |
| `raw` | 파싱 안 함, raw.log로만 |

---

## 4. 핵심 모듈 (skeleton)

### 4.1 models.py — 데이터 구조

```python
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

class State(str, Enum):
    PLANNING = "PLANNING"
    ACTING = "ACTING"
    VERIFYING = "VERIFYING"
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

@dataclass
class StepResult:
    step_id: str
    agent: str
    exit_code: int
    raw_output: str
    parsed_output: Optional[dict]
    parse_error: Optional[str]
    duration_sec: float = 0.0
```

### 4.2 adapter.py — 에이전트 통일 인터페이스

```python
import subprocess, json, time
from pathlib import Path
from models import AgentConfig, StepResult

def run_agent(config, prompt, step_dir, cwd="."):
    """1. input_mode에 따라 프롬프트 전달
       2. timeout 적용
       3. raw.log 항상 저장
       4. output_parser에 따라 파싱 시도
       5. StepResult 반환"""
    cmd = list(config.argv)
    stdin_data = None

    if config.input_mode == "arg":
        cmd.append(prompt)
    elif config.input_mode == "stdin":
        stdin_data = prompt
    elif config.input_mode == "file":
        prompt_file = step_dir / "prompt.md"
        prompt_file.write_text(prompt)
        cmd.extend(["--file", str(prompt_file)])

    (step_dir / "prompt.md").write_text(prompt)

    start = time.time()
    try:
        result = subprocess.run(
            cmd, input=stdin_data,
            capture_output=True, text=True,
            timeout=config.timeout_sec, cwd=cwd
        )
        raw, exit_code = result.stdout, result.returncode
    except subprocess.TimeoutExpired:
        raw, exit_code = "", -1
    duration = time.time() - start

    (step_dir / "raw.log").write_text(raw)

    parsed, parse_error = None, None
    try:
        if config.output_parser == "json":
            parsed = json.loads(raw)
        elif config.output_parser == "ndjson_last":
            parsed = _parse_ndjson_last(raw)
    except (json.JSONDecodeError, ValueError) as e:
        parse_error = str(e)
        (step_dir / "parse_error.md").write_text(
            f"Parser: {config.output_parser}\nError: {e}"
        )

    if parsed is not None:
        (step_dir / "output.json").write_text(
            json.dumps(parsed, ensure_ascii=False, indent=2)
        )

    return StepResult(
        step_id=step_dir.name, agent=config.argv[0],
        exit_code=exit_code, raw_output=raw,
        parsed_output=parsed, parse_error=parse_error,
        duration_sec=duration
    )

def _parse_ndjson_last(raw):
    for line in reversed(raw.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    raise ValueError("No valid JSON line in NDJSON")
```

### 4.3 distiller.py — 시상 필터

```python
import json

MAX_DISTILLED_CHARS = 15000  # ~5K tokens

def distill(raw_output, step_dir):
    """1. 프롬프트 제약으로 이미 작은 출력 기대
       2. 크기 초과 시 핵심 필드만 추출
       3. 실패 시 truncate fallback"""
    text = json.dumps(raw_output, ensure_ascii=False)

    if len(text) > MAX_DISTILLED_CHARS:
        distilled = _extract_essentials(raw_output)
    else:
        distilled = raw_output

    if not _validate_schema(distilled):
        distilled = {"raw_truncated": text[:MAX_DISTILLED_CHARS]}

    (step_dir / "distilled.json").write_text(
        json.dumps(distilled, ensure_ascii=False, indent=2)
    )
    return distilled

def _extract_essentials(data):
    essentials = {}
    for key in ["files", "changes", "risks", "plan", "summary"]:
        if key in data:
            essentials[key] = data[key]
    return essentials or data

def _validate_schema(data):
    return isinstance(data, dict) and len(data) > 0
```

### 4.4 validator.py — post-run 검증

```python
import re, subprocess
from pathlib import Path
from fnmatch import fnmatch

def validate_diff(policy, cwd="."):
    """git diff 기반 검증. 위반 목록 반환 (빈 목록=통과)"""
    errors = []

    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        capture_output=True, text=True, cwd=cwd
    )
    changed_files = result.stdout.strip().splitlines()

    if len(changed_files) > policy.max_files:
        errors.append(f"Too many files: {len(changed_files)} > {policy.max_files}")

    if policy.allowed_paths:
        for f in changed_files:
            if not any(fnmatch(f, p) for p in policy.allowed_paths):
                errors.append(f"Outside allowed: {f}")

    for f in changed_files:
        if any(fnmatch(f, p) for p in policy.forbidden_paths):
            errors.append(f"Forbidden file: {f}")

    stat = subprocess.run(
        ["git", "diff", "--numstat", "HEAD"],
        capture_output=True, text=True, cwd=cwd
    )
    total_loc = sum(
        int(p[0]) + int(p[1])
        for line in stat.stdout.strip().splitlines()
        for p in [line.split("\t")]
        if len(p) >= 2 and p[0].isdigit()
    )
    if total_loc > policy.max_loc:
        errors.append(f"Too many lines: {total_loc} > {policy.max_loc}")

    if policy.forbidden_patterns and policy.check_added_lines_only:
        diff_added = subprocess.run(
            ["git", "diff", "-U0", "HEAD"],
            capture_output=True, text=True, cwd=cwd
        )
        for line in diff_added.stdout.splitlines():
            if line.startswith("+") and not line.startswith("+++"):
                for pattern in policy.forbidden_patterns:
                    if re.search(pattern, line):
                        errors.append(f"Forbidden pattern: {pattern}")
                        break

    return errors
```

---

## 5. 프롬프트 템플릿

### prompts/scan.md
```markdown
You are scanning a codebase to find relevant files for a task.

Task: {{task}}

Output ONLY valid JSON with this structure:
{
  "files": [
    {"path": "src/auth/session.ts", "reason": "세션 갱신 로직", "lines": "42-58"}
  ],
  "risks": ["risk description if any"],
  "plan": ["step 1", "step 2"],
  "summary": "1-2 sentence summary"
}

Constraints:
- Maximum 10 files
- Keep total output under 10K tokens
- JSON only, no explanation text
```

### prompts/implement.md
```markdown
Implement the following task based on the scan results.

Task: {{task}}
Allowed paths: {{allowed_paths}}

Context from scan:
{{previous_output}}

Constraints:
- Only modify files listed in the scan results
- Do not modify test files unless explicitly listed
- Do not refactor unrelated code
- After editing, report changes as JSON:
{
  "changed_files": ["path1", "path2"],
  "summary": "what was done"
}
```

### prompts/verify.md
```markdown
Run tests and verify the recent changes.

Task: {{task}}

Previous step output:
{{previous_output}}

Instructions:
1. Run the project's test suite
2. Report results as JSON:
{
  "tests_passed": true/false,
  "test_command": "npm test",
  "failures": ["description if any"],
  "summary": "1-2 sentence result"
}
```

---

## 6. State Machine (순차 함수, 일반화 없음)

```
runner.py의 run() 함수가 곧 State Machine:

for step in steps:
    if step.id == "scan":     → state = PLANNING
    if step.id == "implement" → state = ACTING
    if step.id == "verify"    → state = VERIFYING
        if fail → CORRECTING (1회) → 재실패 → ESCALATING

마지막 → CONSOLIDATING → DONE

state.json은 각 전이 시 기록만 (디버깅/재현용)
별도 state machine 라이브러리 없음
```

---

## 7. Run Directory (v3 최종)

```
.brain/runs/run-20260428-143022/
├── task.json                    # 작업 계약
├── state.json                   # {"state": "DONE", "updated_at": "..."}
├── steps/
│   ├── 01-scan/
│   │   ├── prompt.md            # 보낸 프롬프트
│   │   ├── raw.log              # 원본 출력 (항상)
│   │   ├── output.json          # 파싱 성공 시
│   │   ├── parse_error.md       # 파싱 실패 시
│   │   └── distilled.json       # 시상 필터 후
│   ├── 02-implement/
│   │   ├── prompt.md
│   │   ├── raw.log
│   │   ├── output.json
│   │   └── diff.patch           # git diff로 생성
│   ├── 03-verify/
│   │   ├── prompt.md
│   │   ├── raw.log
│   │   └── output.json
│   ├── 04-correct/              # 자동수정 시
│   └── 05-reverify/             # 재검증 시
├── artifacts/
│   ├── summary.md               # 필수
│   ├── final.patch              # 선택
│   └── test.log                 # 선택
└── failed_reason.md             # 실패 시
```

---

## 8. 설계 원칙 (v3 최종 10가지)

```
v2 8가지:
1. 뇌처럼 생각하되, 기계처럼 실행하라
2. 오케스트레이터에 LLM을 쓰지 마라
3. 에이전트 사이에 시상 필터를 끼워라
4. 모든 출력은 JSON이다
5. 계약은 prompt + 기계적 검증 이중 구조
6. 실패는 투명하게 (failed_reason + repro_command)
7. Kill-switch는 항상 켜져 있다
8. 에이전트 역할을 고정하지 마라

v3 추가:
9. 원본은 항상 보존하라 (raw.log 필수 저장)
10. diff는 에이전트가 아닌 git이 만든다
```

---

## 9. 구현 우선순위 (Phase 0 = 1주)

```
Day 1: models.py + config.py + cli.py + main.py (뼈대)
Day 2: adapter.py (에이전트 실행 + raw.log + 파싱)
Day 3: distiller.py + prompts/*.md
Day 4: validator.py + killswitch.py
Day 5: runner.py (순차 오케스트레이션) + state.py
Day 6: 통합 테스트 (실제 gemini → cursor → codex)
Day 7: 버그 수정 + README 업데이트
```

→ 자세한 로드맵은 [ROADMAP.md](ROADMAP.md)
