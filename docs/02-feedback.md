# v1 → v2: 3-Agent 피드백 종합

> 작성일: 2026-04-28
> 원본: [01-research.md](01-research.md)
> 피드백 참여: Gemini, Codex, Claude (자체 피드백)

---

## 1. 피드백 요약 매트릭스

| 주제 | Gemini | Codex | Claude | 합의 |
|------|--------|-------|--------|------|
| 뇌 비유의 유용성 | 영리한 매핑 | 비유는 OK, 구현은 제약 | 설명용으로만, 하드코딩 금지 | **비유 유지, 구현은 capability 기반** |
| PFC/Claude 과부하 | 의지력 고갈, 분산 필요 | 오케스트레이터는 deterministic | 비용/속도 병목 | **전원 일치: Claude 역할 분리** |
| 기억 시스템 | Context Distillation 필수 | run log + artifact 재현성 우선 | 4분류는 MVP 과함 | **MVP: decisions.md + runs/** |
| 복잡도 판별 | `brain think` 명령으로 시작 | 수동 플래그로 시작 | 사전 판별 어려움 | **MVP: 수동 --route 플래그** |
| config.yaml | - | schema 기반, argv 배열, timeout | - | **JSON Schema로 재설계** |
| Task Contract | - | 느슨함, validator 필요 | - | **prompt + 기계적 검증 이중** |
| CLI 출력 형식 | - | 전부 JSON/stream-json | - | **text 금지, JSON 강제** |
| cursor-agent | 비결정적, 에러핸들링 두꺼워야 | --force 위험, json 필수 | CLI 불안정, 대체 가능 구조 | **최소 의존, 격리 환경** |
| Codex 역할 | - | 소뇌는 fix_loop만, 나머지 과소평가 | - | **verifier/reviewer/fix_loop 분리** |
| 누락: 시상 | 정보 필터링 레이어 필요 | - | - | **Gemini→Claude 증류 레이어** |
| 누락: 신경가소성 | 라우팅 자동 학습 | - | - | **Phase 2** |
| 누락: 상태 머신 | Pipeline → State Machine | - | - | **PLAN→ACT→VERIFY→DONE** |
| 에러/엣지케이스 | 편도체 = Kill-switch | 25+ 엣지케이스 목록 | - | **failed_reason + repro_command** |
| MVP 범위 | Context Bridge + Linear Route | `brain run` 하나 | 3개 프로젝트 분량 | **전원 일치: MVP 대폭 축소** |

---

## 2. 핵심 합의 (3개 에이전트 공통)

### 2.1 MVP를 대폭 축소해야 한다

**v1 MVP**: Gemini 추가 + 기억 시스템 + 복잡도 라우팅 = 3개 프로젝트

**v2 MVP**:
```bash
brain run --route moderate "세션 갱신 로직 단순화"
```

내부 6단계:
1. Git clean 확인 + run directory 생성
2. **Gemini scan** → JSON
3. **시상 필터**: 10K 이하로 증류
4. **Cursor/Codex** 구현 → diff.patch
5. **Validator** (기계적): allowed paths 내 확인
6. **Codex test** + 1회 자동 수정 → test.log
7. artifacts 저장: `runs/<id>/`

**MVP에서 제외**:
- Debate/Critic, DMN/Reflection
- 망각 곡선, Vector DB
- 병렬 worktree, 대시보드
- 에피소딕→시맨틱 자동 통합
- 성능 학습 라우팅
- 자동 복잡도 분류

### 2.2 Claude 오케스트레이터 과부하 해결

**문제**: Claude가 계획+라우팅+리뷰+메타인지 모두 = 비용 폭발

**해결책**:
```
오케스트레이터 = deterministic 셸 스크립트 (뇌 비유 없음)
Claude = 설계/리뷰 시에만 호출 (System 2 경로)
```

| 기능 | 담당 | 이유 |
|------|------|------|
| 라우팅/상태전이 | 셸 + config | deterministic, 비용 0 |
| 작업 분해/설계 | Claude | System 2 필요 시만 |
| 컨텍스트 스캔 | Gemini | 대용량 처리 |
| 구현 | Cursor 또는 Codex | 능력 기반 |
| 테스트/검증 | Codex | sandbox + 자동 반복 |
| 리뷰 | Claude or Codex | 고위험=Claude, 저위험=Codex |
| diff 검증 | 셸 스크립트 | 기계적, LLM 불필요 |

### 2.3 "시상 (Thalamus)" 레이어 추가

Gemini만 지적:
> "감각 피질에서 들어오는 방대한 데이터 중 무엇을 전전두엽에게 보고할지 결정하는 필터링 레이어가 없으면 Claude 토큰 비용 폭발"

**구현**: 에이전트 핸드오프 사이에 **Context Distillation** 삽입

```
Gemini (1M 컨텍스트 스캔)
    ↓ [raw: ~50K tokens]
시상 필터 (경량 프롬프트 or jq/rg)
    ↓ [distilled: ~5K tokens]
Claude (설계/리뷰)
```

MVP: Gemini 프롬프트에 "10K 토큰 이내 핵심만 출력" 제약.

### 2.4 config.yaml → 실행 가능한 schema

**Before** (읽기용):
```yaml
agents:
  claude:
    command: "claude -p"
    roles: [architect, reviewer]
```

**After** (실행용):
```yaml
agents:
  claude_design:
    argv: ["claude", "-p", "--output-format", "json", "--max-turns", "3"]
    timeout_sec: 300
    retries: 1
    output_format: json

  codex_verify:
    argv: ["codex", "exec", "--json", "--sandbox", "workspace-write"]
    timeout_sec: 1800
    retries: 1
    output_format: ndjson

routes:
  moderate:
    steps:
      - id: scan
        agent: gemini_scan
      - id: implement
        agent: cursor_edit
      - id: verify
        agent: codex_verify
```

### 2.5 Task Contract 강화 (이중 구조)

**prompt 제약 (소프트)** + **post-run validator (하드)**:

```json
{
  "schema_version": "1.0",
  "id": "run-2026-04-28-001",
  "base_sha": "abc1234",
  "diff_policy": {
    "allowed_paths": ["src/auth/**"],
    "forbidden_paths": [".env*", "*.lock", "*.secret"],
    "max_files": 10,
    "max_loc": 500,
    "forbidden_patterns": ["password", "api_key"]
  },
  "runtime": {
    "max_runtime_sec": 1800,
    "on_timeout": "kill_and_save_artifacts",
    "on_failure": "save_failed_reason_and_stop"
  },
  "artifacts": {
    "required": ["summary.md", "test.log"],
    "optional": ["diff.patch", "risks.md"]
  }
}
```

**validator** (셸):
```bash
# 1. allowed_paths 매칭
# 2. forbidden_patterns grep
# 3. required artifacts 존재 확인
```

---

## 3. 에이전트별 고유 피드백

### 3.1 Gemini만 지적

| 포인트 | 내용 | 반영 |
|--------|------|------|
| **신경가소성** | 라우팅이 경험에서 자동 학습 | Phase 2 |
| **편도체 = Kill-switch** | 보안+예산+무한루프+파괴적 명령 | MVP: cost_budget + max_runtime |
| **State Machine** | Pipeline → State Machine | `PLAN → ACT → CORRECT → CONSOLIDATE` |
| **Long-context RAG** | Vector DB 대신 Gemini 캐싱 | Phase 2 검토 |
| **Memory Consolidation** | 유휴 시간 백그라운드 작업 | Phase 3 |

### 3.2 Codex만 지적

| 포인트 | 내용 | 반영 |
|--------|------|------|
| **25+ 엣지케이스** | CLI 미설치, quota, flaky test | MVP: 상위 10개 |
| **argv 배열** | 문자열 → argv (injection 방지) | 즉시 |
| **Codex 과소평가** | reviewer/implementer로도 강함 | 4분할: verifier, small_patch, reviewer, fix_loop |
| **SQLite WAL** | 파일 큐 → SQLite 테이블 | Phase 2 |
| **base_sha 필수** | 재현성을 위해 기준 커밋 기록 | 즉시 |
| **lease/lock** | atomic mkdir 기반 task claim | 병렬화 시 |

### 3.3 Claude만 지적

| 포인트 | 내용 | 반영 |
|--------|------|------|
| **비유가 설계 제약** | "소뇌니까 Codex" 논리가 능력 변화 못 따라감 | capability 기반 동적 |
| **단순 작업 바이패스** | 오케스트레이터 없이 직접 실행 | `--route simple`은 scan/review 생략 |
| **복잡도 사전 판별 불가** | files_touched를 실행 전에 모름 | 키워드 + 사용자 힌트 |
| **cursor-agent 대체 가능** | 인터페이스 분리로 교체 가능 | adapter 패턴 |

---

## 4. 한 줄 총평

### Gemini
> "Gemini를 눈으로, Claude를 뇌로 쓴다는 발상은 훌륭하나, 에이전트 사이의 '정보 요약'과 '상태 관리'가 빠지면 토큰만 먹는 괴물이 될 위험이 있다."

### Codex
> "비유와 큰 그림은 강하지만, 실행 시스템 설계로는 아직 'LLM에게 잘 부탁하는 워크플로우'에 가깝다. 핵심은 뇌 비유를 줄이고 deterministic한 오케스트레이터를 키우는 것이다."

### Claude
> "3개 에이전트 모두 같은 결론: '뇌처럼 생각하되, 기계처럼 실행하라.' MVP는 brain run 하나로 시작하고, config와 validator를 먼저 탄탄히 만들어야 한다."

---

## 5. v1 → v2 변경점 (요약)

```
v1 (조사 단계)              v2 (피드백 반영)
──────────────             ──────────────────
Claude 오케스트레이터       deterministic 셸
뇌 비유 하드코딩            설명용만, capability 기반
text 출력 혼재              JSON 강제
직접 핸드오프               시상 필터 (Distillation)
안전장치 없음               편도체 Kill-switch
config 읽기용 YAML          argv 배열 + schema + timeout
prompt 제약만               prompt + post-run validator
선형 Pipeline               State Machine
자동 복잡도 분류            수동 --route (MVP)
4분류 메모리                decisions.md + runs/
Codex = 소뇌 고정           verifier/reviewer/fix_loop/patch
3개 프로젝트 분량           `brain run` 하나
```

→ 이 변경점이 [03-architecture-v2.md](03-architecture-v2.md)에 반영됨
