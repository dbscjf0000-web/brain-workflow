# v1: 뇌과학 기반 조사 및 초기 설계

> 작성일: 2026-04-28
> 조사 참여: Claude (종합/아키텍처), Gemini (뇌과학 원리), Codex (CLI 아키텍처 패턴)
> 기반 레포: [triad-workflow-plugin](https://github.com/dbscjf0000-web/triad-workflow-plugin)
> **상태**: 초기 설계, [02-feedback.md](02-feedback.md)에서 비판 받음

---

## 1. 기존 triad-workflow-plugin 분석

### 현재 구조

```
triad-workflow-plugin/
  .claude-plugin/plugin.json
  commands/
    plan.md        # Claude가 코드베이스 조사 후 PLAN.md 작성
    implement.md   # Plan을 Cursor Agent에 전달하여 구현
    review.md      # git diff를 Codex에 파이프하여 리뷰
    cycle.md       # plan -> implement -> review 자동 사이클
```

### 역할 분담

| 역할 | 도구 | 이유 |
|------|------|------|
| **Plan** | Claude Code | 긴 컨텍스트 추론, 코드베이스 조사 |
| **Implement** | Cursor Agent | 구독 기반, 파일 직접 편집, Claude 토큰 절약 |
| **Review** | Codex CLI | 구독 기반, diff 읽기, Claude 컨텍스트 오염 방지 |

### 한계점 (개선 대상)

- Gemini CLI 미활용 (대용량 컨텍스트, 멀티모달, 검색 grounding)
- 기억/컨텍스트 시스템 부재 (작업 간 학습 없음)
- 복잡도 기반 라우팅 없음 (모든 작업이 동일 파이프라인)
- 메타인지/자기성찰 부재 (결과 품질 자동 평가 없음)
- 병렬 작업 지원 없음

---

## 2. 뇌의 작동 원리

### 2.1 기억의 3단계 전환

```
감각기억 (ms~초)  →  단기/작업기억 (초~분)  →  장기기억 (영구)
  [입력 버퍼]         [컨텍스트 윈도우]         [영구 저장소]
```

- **감각기억**: 0.5~3초, 즉시 소멸. SW: stdin 버퍼, 이벤트 스트림
- **작업기억**: 7±2 청크, 능동적 조작. SW: LLM 컨텍스트 윈도우
- **장기기억**: 거의 무한, 단서(cue) 필요. SW: 파일시스템, DB, 벡터 저장소

### 2.2 해마 (Hippocampus) — 기억의 관문

해마는 **인덱스/포인터**를 관리한다 (직접 저장 X):
- 새로운 경험을 신피질의 여러 영역에 분산 저장
- 수면 중 **기억 통합**: 단기 → 장기 전환
- 맥락 의존적 인출

**SW 매핑**: RAG 엔진, Vector DB 인덱스, 메타데이터 관리자

### 2.3 기억의 종류

| 뇌의 기억 | 설명 | SW 대응 |
|-----------|------|---------|
| **에피소딕** | 과거 사건/경험 | 작업 로그, 대화 이력, PR 기록 |
| **시맨틱** | 일반 지식/사실 | 프로젝트 구조, 코딩 규칙, API 문서 |
| **절차적** | 방법/기술 (자동화) | 함수, 스크립트, 워크플로우 |

### 2.4 System 1 vs System 2 (Kahneman)

| 특성 | System 1 (빠름) | System 2 (느림) |
|------|----------------|-----------------|
| 속도 | 자동적 | 의식적 |
| 노력 | 적은 인지 부하 | 높은 인지 부하 |
| 정확도 | 휴리스틱 | 논리적 |
| **AI 매핑** | 경량 모델/캐시/스크립트 | 고성능 모델 + CoT 추론 |

### 2.5 전전두엽 피질 (PFC) — 실행 기능

뇌의 "CEO":
- **계획**: 목표를 서브태스크로 분해
- **의사결정**: 여러 대안 중 최적 선택
- **작업 전환**: 컨텍스트 유지하며 전환
- **억제 제어**: 부적절한 반응 억제
- **작업기억 관리**: 관련 정보 유지

**SW 매핑**: 오케스트레이터, 작업 스케줄러, 라우터

### 2.6 메타인지 — "생각에 대한 생각"

- **자기 모니터링**: "내 답이 맞는가?" → Self-Reflection
- **자기 조절**: "다른 전략이 필요한가?" → 실패 시 재계획
- **지식 상태 인식**: "이 문제를 풀 수 있는가?" → 불확실성 → 에스컬레이션
- **SOFAI 모델**: System 1 + System 2 + 메타인지 = 더 높은 결정 품질

---

## 3. 뇌 → 에이전트 매핑

### 핵심 매핑 테이블

| 뇌 영역 | 기능 | 에이전트 역할 | CLI 도구 |
|---------|------|-------------|---------|
| **전전두엽 (PFC)** | 계획, 의사결정, 조율 | Orchestrator / Planner | Claude |
| **해마** | 기억 인덱싱, 통합 | Memory Manager | 파일시스템 + SQLite |
| **시각/감각 피질** | 대량 입력, 패턴 인식 | Context Scanner | Gemini |
| **운동 피질** | 실제 행동 실행 | Code Editor | Cursor Agent |
| **소뇌** | 자동화, 반복 보정 | Test Runner / Auto-fixer | Codex |
| **기저핵** | 작업 선택, 우선순위 | Task Router | 오케스트레이터 |
| **편도체** | 위험 감지, 경보 | Risk Detector | Claude (리뷰) |
| **DMN (기본모드)** | 자기성찰, 창의적 연결 | Reflection Agent | Claude (메타인지) |

### 이중 추론 경로 (Dual-Process)

```
입력 (사용자 요청)
    │
    ▼
[복잡도 판별 라우터]
    │
    ├── 단순 (System 1)
    │     → Codex 직접 실행
    │     → 예: 린트, 포맷팅, 단순 버그
    │
    ├── 보통 (Hybrid)
    │     → Gemini 스캔 → Cursor 구현 → Codex 테스트
    │     → 예: 기능 추가, 리팩터링
    │
    └── 복잡 (System 2)
         → Claude 분석 → 설계 → Cursor 구현 → Claude 리뷰 → Codex 검증
         → 예: 아키텍처 변경, 보안 설계
```

---

## 4. CLI 에이전트별 특성

### Claude Code (`claude -p`)
- **뇌 매핑**: PFC + 편도체
- **강점**: 깊은 추론, 아키텍처 설계, 코드 리뷰
- **원칙**: 직접 구현보다 설계/판단에 집중. "생각하는 뇌"

### Gemini CLI (`gemini -p`)
- **뇌 매핑**: 감각 피질 + 연합 피질
- **강점**: 1M 토큰 컨텍스트, 멀티모달, 검색 grounding
- **원칙**: "넓게 보고 압축한다"

### Codex CLI (`codex exec`)
- **뇌 매핑**: 소뇌 + 기저핵
- **강점**: 빠른 실행, 샌드박스, 테스트 반복
- **원칙**: "빠르게 고치고 실행한다"

### Cursor Agent (`cursor-agent -p`)
- **뇌 매핑**: 운동 피질 + 체성감각
- **강점**: 다중 파일 편집, IDE 통합, 실시간 diff
- **원칙**: "계획을 실행하는 손"

---

## 5. 초기 아키텍처 (v1, 비판 받음)

```
                    사용자 / CI / IDE
                          │
                    ┌──────▼──────┐
                    │  전전두엽    │  ← Claude (오케스트레이터)
                    │ Orchestrator │     [v2에서 비판: deterministic으로 전환]
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
       ┌──────▼──────┐  ┌─▼──────┐  ┌──▼─────────┐
       │   해마       │  │ 기저핵  │  │ 편도체      │
       │ Memory Mgr  │  │ Router │  │ Risk Check  │
       └──────┬──────┘  └─┬──────┘  └──┬─────────┘
              │            │            │
    ┌─────────┼────────────┼────────────┼──────────┐
    │         │            │            │          │
┌───▼───┐ ┌──▼────┐ ┌─────▼──┐ ┌──────▼──┐ ┌─────▼────┐
│Gemini │ │Cursor │ │ Codex  │ │ Claude  │ │ Claude   │
│Scanner│ │Editor │ │AutoFix │ │Reflect  │ │Monitor   │
└───────┘ └───────┘ └────────┘ └─────────┘ └──────────┘
```

### 메모리 시스템 (4분류, v2에서 축소됨)

```
.agent/memory/
  ├── semantic/      # 시맨틱 (프로젝트 지식)
  ├── episodic/      # 에피소딕 (작업 이력)
  ├── procedural/    # 절차적 (자동화 패턴)
  └── working/       # 작업기억 (현재 세션)
```

---

## 6. v1의 문제점 (v2에서 지적됨)

1. **Claude가 오케스트레이터** → 비용 폭발, 비결정적
2. **메모리 4분류** → MVP 과대 설계
3. **자동 복잡도 분류** → 사전 판별 불가능
4. **시상 필터 누락** → 에이전트 간 토큰 폭발
5. **Kill-switch 없음** → 무한 루프/보안 사고 위험
6. **YAML config** → 실행 가능한 schema 아님
7. **MVP가 3개 프로젝트 분량** → 시작 못 함

→ 이 지적들이 [02-feedback.md](02-feedback.md)에 정리됨

---

## 7. 참고 자료

### 핵심 논문 및 아키텍처

- [Brain-Inspired AI Agent: The Way Towards AGI](https://arxiv.org/html/2412.08875v1) — 뇌 영역별 AI 에이전트 모듈 매핑 (PPDA 모델)
- [Fast, slow, and metacognitive thinking in AI](https://www.nature.com/articles/s44387-025-00027-5) — System 1/2 + 메타인지 AI 적용
- [SuperLocalMemory V3.3](https://arxiv.org/html/2604.04514v1) — 생물학적 영감 망각, 인지 양자화
- [AI Meets Brain: Memory Systems Survey](https://arxiv.org/html/2512.23343v1) — 인지신경과학 → 자율 에이전트 메모리
- [Cognitive Architectures for Language Agents (CoALA)](https://www.cognee.ai/blog/fundamentals/cognitive-architectures-for-language-agents-explained)

### 실무 구현 참고

- [Architecture and Orchestration of Memory Systems in AI Agents](https://www.analyticsvidhya.com/blog/2026/04/memory-systems-in-ai-agents/)
- [LinkedIn Cognitive Memory Agent](https://www.infoq.com/news/2026/04/linkedin-cognitive-memory-agent/)
- [Agentic AI Architectures & Taxonomies](https://arxiv.org/html/2601.12560v1)

### 기존 레포

- [triad-workflow-plugin](https://github.com/dbscjf0000-web/triad-workflow-plugin)
