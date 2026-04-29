# v2: 아키텍처 (피드백 반영)

> 작성일: 2026-04-28
> 기반: [02-feedback.md](02-feedback.md)
> 상태: 설계 완료, [04-implementation-v3.md](04-implementation-v3.md)에서 Python으로 구체화

---

## 1. 전체 아키텍처

```
 +-----------------------------------------------------------------+
 |                        brain CLI (bash → Python)                 |
 |  deterministic orchestrator: 라우팅, 상태전이, 검증, artifact     |
 +---------+-------------------+-------------------+---------------+
           |                   |                   |
   +-------v-------+  +-------v-------+  +--------v--------+
   |  Kill-switch   |  | State Machine |  |  Run Manager    |
   |  (편도체)       |  | PLAN→ACT→     |  |  runs/<id>/     |
   |  비용/시간/보안  |  | VERIFY→DONE   |  |  artifacts/     |
   +---------------+  +---------------+  +-----------------+
           |                   |                   |
 +---------v-------------------v-------------------v---------------+
 |                     Agent Adapter Layer                          |
 |  모든 에이전트를 동일 인터페이스로 래핑 (argv + JSON in/out)       |
 +------+----------+----------+----------+----------+--------------+
        |          |          |          |          |
   +----v---+ +---v----+ +---v----+ +---v----+ +---v----+
   |gemini  | |claude  | |cursor  | |codex   | |codex   |
   |_scan   | |_design | |_edit   | |_verify | |_review |
   |감각피질 | |전전두엽 | |운동피질 | |소뇌    | |리뷰어  |
   +--------+ +--------+ +--------+ +--------+ +--------+
```

---

## 2. 3가지 라우팅 경로

### Simple (System 1) — 자동 반사

```
사용자: brain run --route simple "린트 수정"

  +--------+     +----------+     +--------+
  | codex  |---->| validator |---->|  DONE  |
  | _patch |     | (diff)    |     |  runs/ |
  +--------+     +----------+     +--------+

  Claude 호출 없음. 비용 최소.
```

### Moderate (Hybrid) — 의식적 행동

```
사용자: brain run --route moderate "세션 갱신 리팩터링"

+--------+   +-------+   +--------+   +----------+   +--------+
|gemini  |-->| 시상  |-->| cursor |-->| codex    |-->|  DONE  |
|_scan   |   | 필터  |   | _edit  |   | _verify  |   |  runs/ |
+--------+   +-------+   +--------+   +----+-----+   +--------+
 50K→JSON     →5K        diff.patch    테스트+1회fix
                                            |
                                       실패시 ESCALATE
```

### Complex (System 2) — 심층 사고

```
사용자: brain run --route complex "인증 아키텍처 재설계"

+------+   +-----+   +------+   +------+   +------+   +------+
|gemini|-->|시상 |-->|claude|-->|cursor|-->|codex |-->|claude|
|_scan |   |필터 |   |_design|  |_edit |   |_verify|  |_review|
+------+   +-----+   +------+   +------+   +--+---+   +------+
 전체스캔   증류5K    설계분해   구현       테스트     최종리뷰
                                              |
                                         실패→CORRECT
                                         재실패→ESCALATE
```

---

## 3. State Machine

```
                       brain run "<task>"
                             |
                             v
                   +-------------------+
                   |     PLANNING      |  gemini_scan → 시상필터
                   |  (컨텍스트 수집)   |  complex면 claude_design 추가
                   +---------+---------+
                             |
                             v
                   +-------------------+
                   |     ACTING        |  cursor_edit 또는 codex_patch
                   |  (구현/편집)      |
                   +---------+---------+
                             |
                             v
                   +-------------------+
                   |    VERIFYING      |  codex_verify (테스트)
                   |  (검증)           |  + diff validator (기계적)
                   +---------+---------+
                       /     |     \
                      /      |      \
                     v       v       v
                  PASS    MINOR    FAIL
                   |     ISSUE      |
                   |       v        v
                   |  +---------+ +------------+
                   |  |CORRECTING| | ESCALATING |
                   |  |자동수정   | | 사람에게    |
                   |  |1회 허용   | | 보고       |
                   |  +----+----+ +------------+
                   |       |
                   |       v
                   |   VERIFYING (재검증)
                   v       v
                +------------------+
                |  CONSOLIDATING   |  artifacts 저장
                |  (결과 정리)      |  decisions.md 업데이트
                +--------+---------+  failed_reason (실패시)
                         |
                         v
                      DONE / FAILED
```

---

## 4. 에이전트 어댑터 (통일 인터페이스)

```
+---------------------------------------------------------+
|                  Agent Adapter 규격                       |
+---------------------------------------------------------+
|  입력:   runs/<id>/input.json   (task contract)          |
|  출력:   runs/<id>/output.json  (structured result)      |
|  부산물: runs/<id>/artifacts/   (diff, log, summary)     |
|  종료:   exit 0=성공, 1=실패, 2=에스컬레이션             |
+---------------------------------------------------------+
```

config.yaml (v2 → v3에서 JSON으로 전환):

```yaml
agents:
  gemini_scan:
    argv: ["gemini", "-p", "--output-format", "json"]
    timeout_sec: 120
    retries: 0
    output_format: json

  claude_design:
    argv: ["claude", "-p", "--output-format", "json", "--max-turns", "3"]
    timeout_sec: 300
    retries: 1
    output_format: json

  cursor_edit:
    argv: ["cursor-agent", "-p", "--output-format", "json"]
    timeout_sec: 600
    retries: 0
    output_format: json
    requires_worktree: true

  codex_verify:
    argv: ["codex", "exec", "--json", "--sandbox", "workspace-write"]
    timeout_sec: 300
    retries: 1
    output_format: ndjson

  codex_review:
    argv: ["codex", "exec", "--json"]
    timeout_sec: 180
    retries: 0
    output_format: ndjson
```

---

## 5. 시상 필터 (Context Distillation)

```
+-------------------+                   +------------------+
|  에이전트 A 출력   | --- 시상 필터 ---> |  에이전트 B 입력  |
|  (50K tokens)    |                   |  (5K tokens)     |
+-------------------+                   +------------------+

MVP 구현: 프롬프트 제약
┌──────────────────────────────────────────────────┐
│ "10K 토큰 이내로 다음만 출력:                       │
│  1. 관련 파일 경로 (최대 10개)                      │
│  2. 각 파일의 변경 필요 사항 (1-2줄)                │
│  3. 위험 요소 (있으면)                             │
│  4. 추천 구현 순서                                 │
│  JSON 형식으로."                                   │
└──────────────────────────────────────────────────┘

Phase 2: jq/rg 기반 기계적 필터링 추가
```

---

## 6. 편도체 Kill-switch

| 감시 항목 | 기준 | 동작 |
|-----------|------|------|
| 실행 시간 | > timeout_sec | SIGTERM 후 artifact 저장 |
| 비용 (토큰 추정) | > cost_budget | 즉시 중단 |
| diff 크기 | > max_loc (500) | ESCALATE |
| 금지 파일 접근 | .env, *.secret | 즉시 중단 |
| 금지 패턴 | password, api_key | ESCALATE |
| 반복 실패 | CORRECT 2회 초과 | ESCALATE |

---

## 7. Run Directory 구조

```
.brain/
  config.yaml                    # 에이전트 설정
  decisions.md                   # 장기 기억
  runs/
    run-20260428-143022/
      ├── task.json              # 작업 계약
      ├── state.json             # 현재 상태
      ├── events.ndjson          # 이벤트 로그 (v3에서 제거)
      ├── steps/
      │   ├── 01-scan/
      │   │   ├── prompt.md
      │   │   ├── output.json
      │   │   └── distilled.json
      │   ├── 02-implement/
      │   │   ├── prompt.md
      │   │   ├── output.json
      │   │   └── diff.patch
      │   └── 03-verify/
      │       ├── prompt.md
      │       ├── output.json
      │       └── test.log
      ├── artifacts/
      │   ├── final.patch
      │   ├── summary.md
      │   └── test.log
      └── failed_reason.md       # 실패 시
```

---

## 8. Task Contract (강화)

```json
{
  "schema_version": "1.0",
  "id": "run-20260428-143022",
  "task": "세션 갱신 로직 단순화",
  "route": "moderate",
  "base_sha": "abc1234def5678",

  "steps": [
    {"id": "scan",      "agent": "gemini_scan",  "distill": true},
    {"id": "implement", "agent": "cursor_edit",   "input_from": "scan"},
    {"id": "verify",    "agent": "codex_verify",  "input_from": "implement"}
  ],

  "diff_policy": {
    "allowed_paths":    ["src/auth/**", "tests/auth/**"],
    "forbidden_paths":  [".env*", "*.lock", "*.secret", "node_modules/**"],
    "forbidden_patterns": ["password", "api_key", "secret", "token"],
    "max_files": 10,
    "max_loc": 500
  },

  "runtime": {
    "max_total_sec": 1800,
    "cost_budget_usd": 2.0,
    "max_correct_attempts": 1,
    "on_timeout": "save_and_stop",
    "on_failure": "save_reason_and_escalate"
  },

  "artifacts": {
    "required": ["summary.md", "test.log"],
    "optional": ["diff.patch", "risks.md"]
  },

  "post_run_checks": [
    "diff_within_allowed_paths",
    "no_forbidden_patterns_in_diff",
    "required_artifacts_exist",
    "tests_passed"
  ]
}
```

---

## 9. 전체 프로세스 한 눈에

```
사용자
  |
  | brain run --route moderate "세션 갱신 리팩터링"
  v
+====================================================================+
||                        brain CLI                                  ||
||                                                                   ||
||  1. Git clean? --NO-> "커밋 먼저" (중단)                          ||
||      |                                                            ||
||     YES                                                           ||
||      |                                                            ||
||  2. Run dir 생성: .brain/runs/run-20260428-143022/                ||
||      |                                                            ||
||  3. Task Contract 생성 (base_sha 기록)                            ||
||      |                                                            ||
||  +-----------+  state: PLANNING                                   ||
||  |  Gemini   |---> output.json (50K)                              ||
||  |  _scan    |          |                                         ||
||  +-----------+     시상 필터                                       ||
||                         |                                          ||
||                  distilled.json (5K)                               ||
||                         |                                          ||
||  +-----------+  state: ACTING                                     ||
||  |  Cursor   |<--- distilled.json                                 ||
||  |  _edit    |---> diff.patch                                     ||
||  +-----------+                                                    ||
||      |                                                            ||
||  [diff validator] -- FAIL --> ESCALATE                            ||
||      |                                                            ||
||     PASS                                                          ||
||      |                                                            ||
||  +-----------+  state: VERIFYING                                  ||
||  |  Codex    |---> test.log                                       ||
||  |  _verify  |                                                    ||
||  +-----------+                                                    ||
||      |                                                            ||
||   PASS? --NO--> CORRECTING (1회) --재실패--> ESCALATE             ||
||      |                                                            ||
||     YES                                                           ||
||      |                                                            ||
||  state: CONSOLIDATING                                             ||
||      |                                                            ||
||  artifacts/ 저장 + decisions.md 업데이트                          ||
||      |                                                            ||
||     DONE                                                          ||
+====================================================================+
```

---

## 10. v2 → v3 전환 사유

v2는 bash + jq 기반으로 설계되었으나 다음 이유로 Python으로 전환:

| 문제 | bash | Python (v3) |
|------|------|-------------|
| JSON 파싱 | `jq` 외부 의존 | `json` 내장 |
| 에러 처리 | 빈약 | try/except + dataclass |
| timeout | `timeout` 명령 + 신호 | `subprocess.run(timeout=)` |
| 타입 안전성 | 없음 | dataclass + type hints |
| glob 매칭 | bash glob | `fnmatch` 내장 |
| 정규식 | `grep -E` | `re` 내장 |
| 가독성 | 셸 스크립트 한계 | 모듈화 가능 |

→ [04-implementation-v3.md](04-implementation-v3.md)에서 구체화

---

## 11. 설계 원칙 8가지 (v2 단계)

```
1. 뇌처럼 생각하되, 기계처럼 실행하라
2. 오케스트레이터에 LLM을 쓰지 마라
3. 에이전트 사이에 시상 필터를 끼워라
4. 모든 출력은 JSON이다
5. 계약은 prompt + 기계적 검증 이중 구조
6. 실패는 투명하게 (failed_reason + repro_command)
7. Kill-switch는 항상 켜져 있다
8. 에이전트 역할을 고정하지 마라
```

v3에서 9, 10이 추가됨 → [PRINCIPLES.md](PRINCIPLES.md)
