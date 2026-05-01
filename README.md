# Brain-Workflow

> 뇌의 작동 원리에서 영감을 받은 Multi-Agent CLI 워크플로우
> **원칙**: "뇌처럼 생각하되, 기계처럼 실행하라"

---

## 한 줄 요약

Codex가 넓게 보고, Claude가 깊게 설계하고, Cursor가 정교하게 실행하고, Codex가 빠르게 검증한다 — 결정 로그(decisions.md)가 이 모든 것을 기록한다.

## 무엇인가

```bash
brain run --route moderate "세션 갱신 로직 단순화"
```

→ 4개 CLI(Codex/Claude/Cursor/Codex)가 협업해서 task 수행. 모든 흐름은 deterministic Python 오케스트레이터가 조율. LLM은 도메인 작업에서만 호출.

## 빠른 시작

### 사전 조건
- Python 3.10+
- `cursor-agent`, `codex`, `claude`, `gemini` CLI 설치 + 인증 완료
- 작업 대상이 git repo여야 함

### 명령

```bash
# 작업 실행
brain run "<task>"                          # default: moderate (worktree 격리)
brain run "<task>" --route simple           # 작은 변경 (Codex 단독)
brain run "<task>" --route moderate         # 일반 task (Codex → Cursor → Codex)
brain run "<task>" --route complex          # 어려운 task (+ Claude design + review)
brain run "<task>" --route auto             # 키워드로 자동 분류

# 결과 확인
brain status [--limit 5]                    # 최근 N개 run 표
brain show latest                           # 최신 run 상세 (steps, files, verify)
brain show run-20260430-093015              # 특정 run 상세

# worktree 결과 가져오기 (moderate/complex)
brain apply latest                          # 최신 DONE run의 final.patch를 cwd에 적용
brain apply <run_id> --check                # 적용 가능한지만 점검
```

### 빠른 예시

```bash
$ brain run "src/auth.py의 SQL injection 수정" --route complex
  ...
  state: DONE

$ brain show latest
  Run: run-20260430-093015
  Task: src/auth.py의 SQL injection 수정
  Route: complex
  State: DONE

  Steps:
    01-scan       (codex_scan, OK, 5.2s)
    02-design     (claude_design, OK, 19.1s)
    03-implement  (cursor_edit, OK, 45.0s)
    04-verify     (codex_verify, OK, 12.3s)
    05-review     (codex_review, OK, 8.7s)

  Changed files (final.patch):
    M src/auth.py

  Verify: task_completed=True, tests_passed=True
  Review: approved=True
  Summary: ...

$ brain apply latest
  Will apply: M src/auth.py
  Applied successfully.
```

결과는 `.brain/runs/<id>/`에 저장. DONE 시 `.brain/decisions.md`에 한 줄 append.

## 현재 상태

**Phase 0 + Phase 1 + Phase 2 핵심 + 운영 명령 완료**. baseline 운영 검증 통과.

```
Phase 0    ✅ MVP 골격 + end-to-end PASS
운영검증    ✅ 12개 이슈 발견/해결 (silent failure, ndjson 파싱, gemini argv,
              untracked 파일, sandbox 권한, N/A placeholder, ...)
Phase 1    ✅ simple/complex route, JSON Schema 검증 (input_from 참조 무결성),
              worktree 자동 생성/정리, decisions.md 자동 append, 엣지케이스 4건
Phase 2    ✅ 메타인지 review step (verify가 놓친 이슈 catch),
              자동 복잡도 분류 (--route auto)
운영명령    ✅ brain status / show / apply
```

남은 항목 (실사용 후 가치 평가 후 진행 권장):
- 신경가소성 (decisions.md 누적 후 학습)
- SQLite 상태 관리
- 병렬 worktree

## 디렉토리 구조

```
brain-workflow/
├── README.md                     # 이 파일
├── config.json                   # 에이전트 실행 설정
├── docs/                         # 설계 문서 (4단계 진화 기록)
│   ├── 01-research.md
│   ├── 02-feedback.md
│   ├── 03-architecture-v2.md
│   ├── 04-implementation-v3.md
│   ├── PRINCIPLES.md
│   └── ROADMAP.md
├── bin/
│   └── brain                     # bash 래퍼
├── lib/                          # Python 구현 (외부 의존성 0)
│   ├── main.py                   # 진입점
│   ├── cli.py                    # argparse
│   ├── config.py                 # JSON Schema 검증
│   ├── models.py                 # dataclass: TaskContract, AgentConfig, ...
│   ├── runner.py                 # State Machine + worktree
│   ├── adapter.py                # 에이전트 통일 인터페이스
│   ├── distiller.py              # 시상 필터 (Context Distillation)
│   ├── validator.py              # post-run diff 검증
│   ├── killswitch.py             # 편도체 (timeout, dirty 차단)
│   └── state.py                  # state.json CRUD
├── prompts/                      # 에이전트별 프롬프트 템플릿
│   ├── scan.md     (codex_scan)
│   ├── design.md   (claude_design)
│   ├── implement.md (cursor_edit)
│   ├── patch.md    (codex_patch)
│   ├── verify.md   (codex_verify)
│   └── review.md   (codex/claude_review)
└── .brain/                       # 프로젝트별 (gitignore 권장)
    ├── decisions.md              # DONE entries 자동 append
    └── runs/                     # 실행 기록 (run-YYYYMMDD-HHMMSS/)
```

## 라우트 비교

| route | steps | 흐름 | 용도 | worktree |
|-------|-------|------|------|----------|
| **simple** | patch → verify | Codex → Codex | 작은 변경 (docstring, 1줄 수정) | ❌ |
| **moderate** | scan → implement → verify | Codex → Cursor → Codex | 일반 task (기능 추가, 리팩터링) | ✅ |
| **complex** | scan → design → implement → verify | Codex → Claude → Cursor → Codex | 어려운 task (아키텍처 변경) | ✅ |

## Run Directory 구조

```
.brain/runs/run-20260429-145606/
├── task.json                  # 작업 계약 (base_sha, diff_policy)
├── state.json                 # 현재 상태 (DONE/FAILED/...)
├── steps/
│   ├── 01-scan/
│   │   ├── prompt.md          # 보낸 프롬프트
│   │   ├── raw.log            # 원본 출력 (항상 보존)
│   │   ├── output.json        # 파싱 성공 시
│   │   ├── stderr.log         # stderr가 있을 때
│   │   └── distilled.json     # 시상 필터 후
│   ├── 02-implement/
│   │   ├── ...
│   │   └── diff.patch         # git diff로 생성 (에이전트 출력 X)
│   └── 03-verify/
├── artifacts/
│   ├── final.patch            # 최종 변경
│   ├── summary.md
│   └── test.log
├── worktree/                  # moderate/complex의 격리 영역 (DONE 후 자동 정리)
└── failed_reason.md           # 실패 시
```

## 핵심 원칙 (자세히는 [PRINCIPLES.md](docs/PRINCIPLES.md))

1. 뇌처럼 생각하되, 기계처럼 실행하라
2. 오케스트레이터에 LLM을 쓰지 마라 (셸/Python만)
3. 에이전트 사이에 시상 필터를 끼워라 (50K → 5K)
4. 모든 출력은 JSON이다 (text 금지)
5. 계약은 prompt + 기계적 검증 이중 구조
6. 실패는 투명하게 (failed_reason + repro_command + raw.log)
7. Kill-switch는 항상 켜져 있다 (timeout, forbidden paths)
8. 에이전트 역할을 고정하지 마라 (config로 교체 가능)
9. 원본은 항상 보존하라 (raw.log + stderr.log 필수)
10. diff는 에이전트가 아닌 git이 만든다

## config.json 한눈에

```json
{
  "agents": {
    "codex_scan":   { "argv": ["codex", "exec", "..."], "output_parser": "ndjson_last" },
    "claude_design":{ "argv": ["claude", "-p", "..."], "output_parser": "json" },
    "cursor_edit":  { "argv": ["cursor-agent", "-p", "--force", "--trust", "..."],
                      "requires_worktree": true },
    "codex_verify": { "argv": ["codex", "exec", "..."], "output_parser": "ndjson_last" },
    "codex_patch":  { "argv": ["codex", "exec", "...", "--full-auto"] }
  },
  "routes": { "simple": ..., "moderate": ..., "complex": ... }
}
```

agent별 `env` 필드도 지정 가능 (예: `GEMINI_CLI_TRUST_WORKSPACE`).

## 알려진 환경 의존성 (KISTI Neuron)

- **Gemini keychain ENOENT**: `uv_os_get_passwd` 시스템 정보 누락이지만 OAuth fallback으로 동작 OK (stderr 경고 무시)
- **Workspace trust**: `GEMINI_CLI_TRUST_WORKSPACE=true` env로 우회 (config의 agent.env에 설정)
- **Codex sandbox**: `--full-auto` 플래그 필수 (workspace-write 권한)
- **Cursor 새 디렉토리**: `--force --trust` 플래그 필수

## 다음 단계

- Phase 1 #6: 더 많은 엣지케이스 (CLI 미설치, quota, 네트워크 실패)
- Phase 2: 자동 복잡도 분류, 메타인지(품질 자동 평가), 신경가소성(라우팅 학습)
- Phase 3: 자율 진화 (에피소딕→시맨틱 통합, 대시보드)

상세는 [ROADMAP.md](docs/ROADMAP.md).

## 라이선스

(미정)
