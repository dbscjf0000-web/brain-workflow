# 구현 로드맵

> 현재 위치: **Phase 0 설계 완료, 구현 대기**

---

## Phase 0 — MVP (1주)

**목표**: `brain run --route moderate "<task>"` 한 줄로 동작

### Day 1: 뼈대
- [ ] `lib/models.py` — dataclass 정의
- [ ] `lib/config.py` — config.json 로드/검증
- [ ] `lib/cli.py` — argparse
- [ ] `lib/main.py` — 진입점
- [ ] `bin/brain` — bash 래퍼
- [ ] `config.json` — 초기 설정

### Day 2: 에이전트 어댑터
- [ ] `lib/adapter.py` — `run_agent()` 핵심 함수
- [ ] input_mode 지원: `arg`, `stdin`, `file`
- [ ] output_parser: `json`, `ndjson_last`, `raw`
- [ ] raw.log 항상 저장
- [ ] 단위 테스트: echo 명령으로 시뮬레이션

### Day 3: 시상 필터 + 프롬프트
- [ ] `lib/distiller.py` — `distill()` 함수
- [ ] 크기 초과 시 essentials 추출
- [ ] schema 검증 fallback
- [ ] `prompts/scan.md`
- [ ] `prompts/implement.md`
- [ ] `prompts/verify.md`

### Day 4: 검증 + Kill-switch
- [ ] `lib/validator.py` — `validate_diff()`
- [ ] allowed_paths, forbidden_paths (fnmatch)
- [ ] forbidden_patterns (re, 추가 라인만)
- [ ] max_files, max_loc 체크
- [ ] `lib/killswitch.py` — pre/post check
- [ ] git clean 강제 (--allow-dirty 옵션)

### Day 5: 오케스트레이션
- [ ] `lib/runner.py` — `run()` 메인 루프
- [ ] State 전이 (PLANNING → ACTING → VERIFYING)
- [ ] CORRECTING 1회 (실패 시 ESCALATE)
- [ ] CONSOLIDATING (artifacts + summary.md)
- [ ] `lib/state.py` — state.json CRUD
- [ ] `_save_git_diff()` — diff.patch 생성

### Day 6: 통합 테스트
- [ ] 실제 CLI 사용 시도: gemini → cursor → codex
- [ ] 더미 프로젝트로 end-to-end 검증
- [ ] 실패 케이스 확인 (timeout, 잘못된 JSON, allowed_paths 위반)
- [ ] 재현성 확인 (base_sha + 같은 task → 동일 결과)

### Day 7: 마무리
- [ ] 버그 수정
- [ ] README.md 사용법 업데이트
- [ ] `.brain/` gitignore 추가
- [ ] 첫 사용 노트 (실전 후기)

---

## Phase 1 — 안정화 (2주)

### 새 라우트
- [ ] `--route simple`: scan/review 생략, codex_patch만
- [ ] `--route complex`: claude_design 추가, claude_review 추가

### Robustness
- [ ] config.json JSON Schema 검증
- [ ] 상위 10개 엣지케이스 처리
  - CLI 미설치 (PATH 체크)
  - quota/rate limit
  - 깨진 JSON
  - flaky test (n회 재시도 옵션)
  - 부분 patch (apply 실패)
  - 권한 없는 파일
  - 큰 stdout (truncate)
  - 비ASCII 처리
  - 동시 실행 잠금
  - .git이 없는 디렉토리
- [ ] worktree 자동 생성/정리
- [ ] decisions.md 정책 변경 시 자동 기록
- [ ] post-run validator 고도화 (시그니처 검증, line ending 등)

### UX
- [ ] `--allow-dirty` 옵션
- [ ] `brain status` (현재 run 상태)
- [ ] `brain replay <run-id>` (재현)
- [ ] 컬러 출력 (ANSI)

---

## Phase 2 — 고급 기능 (4주)

### 자동화
- [ ] 자동 복잡도 분류 (키워드 + 사용자 힌트)
- [ ] SQLite 상태 관리 (WAL, FTS)
- [ ] 메타인지 에이전트 (결과 자동 품질 평가)
- [ ] 신경가소성: 성공/실패 통계 → 라우팅 가중치

### 병렬화
- [ ] 병렬 worktree (독립 작업 동시 실행)
- [ ] atomic mkdir 기반 task lock
- [ ] 작업 큐 (`brain queue add`)

### 협업 패턴
- [ ] Debate/Critic (설계 시 에이전트 토론)
- [ ] 다단계 review (Codex → Claude 순차)

---

## Phase 3 — 자율 진화 (8주+)

### 기억 시스템
- [ ] 에피소딕 → 시맨틱 자동 통합 (망각 곡선)
- [ ] Vector DB 기억 검색
- [ ] Gemini Long-context RAG 캐시

### 동적 적응
- [ ] 동적 에이전트 역할 재배정
- [ ] 작업 패턴 학습 → 라우팅 자동 최적화
- [ ] 비용/지연 프로파일링

### 시각화
- [ ] 대시보드 (작업 상태)
- [ ] 통계 페이지 (성공률, 비용)
- [ ] 실시간 로그 스트리밍

---

## 마일스톤

| 시점 | 상태 |
|------|------|
| Day 7 | `brain run --route moderate` 동작 |
| Week 3 | simple/complex 추가, 엣지케이스 안정화 |
| Week 7 | 자동 라우팅 + 병렬 실행 |
| Week 15 | 자율 학습 + 대시보드 |

---

## 다음 단계

1. **Phase 0 Day 1 시작**: `lib/models.py`부터 작성
2. 통합 테스트 환경 준비:
   - 더미 프로젝트 1개 (Node.js or Python)
   - 4개 CLI 동작 확인 (gemini, claude, cursor-agent, codex)
3. 첫 실행 목표: "README.md 한 줄 추가" 같은 trivial task로 파이프라인 검증
