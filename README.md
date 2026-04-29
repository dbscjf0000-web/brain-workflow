# Brain-Workflow

> 뇌의 작동 원리에서 영감을 받은 Multi-Agent CLI 워크플로우
> **원칙**: "뇌처럼 생각하되, 기계처럼 실행하라"

---

## 한 줄 요약

Gemini가 넓게 보고, Claude가 깊게 생각하고, Cursor가 정교하게 실행하고, Codex가 빠르게 검증한다 — 해마(메모리)가 이 모든 것을 기억하고 연결한다.

## 무엇을 만드는가

기존 [triad-workflow-plugin](https://github.com/dbscjf0000-web/triad-workflow-plugin)을 확장하여:

- **4개 CLI 협업**: Claude (PFC) + Gemini (감각피질) + Cursor (운동피질) + Codex (소뇌)
- **시상 필터 (Context Distillation)**: 에이전트 간 출력 증류 → 토큰 비용 90% 절감
- **State Machine**: PLANNING → ACTING → VERIFYING → CONSOLIDATING
- **Deterministic Orchestrator**: Python 셸 (LLM 아님) — 비용 0, 재현 가능
- **Kill-switch (편도체)**: 비용/시간/보안 한도 자동 감시
- **기계적 검증**: prompt 제약 + post-run validator 이중 구조

## 빠른 사용 (Phase 0 MVP 목표)

```bash
brain run --route moderate "세션 갱신 로직 단순화"
```

내부 동작:
1. Git clean 확인 + run directory 생성
2. **Gemini scan**: 관련 파일/위험/계획 요약 → JSON
3. **시상 필터**: 50K → 5K로 증류
4. **Cursor edit**: 계획 기반 구현 → diff.patch
5. **Validator**: diff가 allowed paths 내인지 기계적 검증
6. **Codex verify**: 테스트 + 1회 자동 수정
7. artifacts 저장: `.brain/runs/<id>/`

## 문서 구조

| 문서 | 내용 |
|------|------|
| [docs/01-research.md](docs/01-research.md) | v1: 뇌과학 원리 + CLI 매핑 + 초기 아키텍처 |
| [docs/02-feedback.md](docs/02-feedback.md) | 3-agent (Gemini/Codex/Claude) 피드백 종합 |
| [docs/03-architecture-v2.md](docs/03-architecture-v2.md) | v2: 피드백 반영 후 재설계 |
| [docs/04-implementation-v3.md](docs/04-implementation-v3.md) | v3: Python 구현 명세 (현재 작업본) |
| [docs/PRINCIPLES.md](docs/PRINCIPLES.md) | 설계 원칙 10가지 |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Phase 0 → Phase 3 로드맵 |

## 디렉토리 구조

```
brain-workflow/
├── README.md                     # 이 파일
├── docs/                         # 설계 문서 (4단계 진화 기록)
│   ├── 01-research.md
│   ├── 02-feedback.md
│   ├── 03-architecture-v2.md
│   ├── 04-implementation-v3.md
│   ├── PRINCIPLES.md
│   └── ROADMAP.md
├── bin/
│   └── brain                     # bash 래퍼 (Phase 0)
├── lib/                          # Python 구현 (Phase 0)
│   ├── main.py
│   ├── cli.py
│   ├── config.py
│   ├── models.py
│   ├── runner.py
│   ├── adapter.py
│   ├── distiller.py
│   ├── validator.py
│   ├── killswitch.py
│   └── state.py
├── prompts/                      # 에이전트별 프롬프트 템플릿
│   ├── scan.md
│   ├── implement.md
│   ├── verify.md
│   ├── design.md                 # Phase 1+
│   └── review.md                 # Phase 1+
├── config.json                   # 에이전트 실행 설정
└── .brain/                       # 프로젝트별 (gitignore)
    ├── decisions.md
    └── runs/
```

## 설계 진화 요약

```
v1 (조사)        →  v2 (피드백 반영)    →  v3 (Python 명세)
───────────         ─────────────────     ──────────────────
LLM 오케스트레이터    deterministic 셸      Python 3 (의존성 0)
YAML config         JSON schema           dataclass + JSON
text 출력 혼재       JSON 강제             raw.log + parsed
4분류 메모리         decisions.md만        동일
자동 복잡도 분류     수동 --route          --route moderate만
3개 프로젝트 분량    `brain run` 하나      Phase 0 = 1주
```

## 핵심 원칙 (자세히는 [PRINCIPLES.md](docs/PRINCIPLES.md))

1. 뇌처럼 생각하되, 기계처럼 실행하라
2. 오케스트레이터에 LLM을 쓰지 마라
3. 에이전트 사이에 시상 필터를 끼워라
4. 모든 출력은 JSON이다
5. 계약은 prompt + 기계적 검증 이중 구조
6. 실패는 투명하게 (failed_reason + repro_command)
7. Kill-switch는 항상 켜져 있다
8. 에이전트 역할을 고정하지 마라
9. 원본은 항상 보존하라 (raw.log 필수)
10. diff는 에이전트가 아닌 git이 만든다

## 현재 상태

**Phase 0 (MVP) 설계 완료**, 구현 시작 전.
- 다음 단계: `lib/main.py` + `lib/adapter.py` 부터 구현
- 로드맵: [ROADMAP.md](docs/ROADMAP.md)
