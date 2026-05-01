# 구현 로드맵

> 현재 위치: **Phase 0 + Phase 1 + Phase 2 핵심 + 운영 명령 완료. 실사용 단계.**

---

## Phase 0 — MVP ✅ 완료

`brain run --route moderate "<task>"` 한 줄로 동작.

- [x] lib/ 10개 모듈 (models/config/cli/main/runner/adapter/distiller/validator/killswitch/state)
- [x] bin/brain bash 래퍼
- [x] config.json + prompts/ 5개 템플릿
- [x] 통합 테스트: end-to-end PASS 확인 (testbed에서 farewell 함수 추가 → DONE)

### 운영 검증 (Phase 0 사이클 중) ✅ 완료

12개 운영 이슈 발견/해결:

- [x] #1 silent failure 차단 (빈 diff = FAILED, untracked 포함)
- [x] #2 ndjson_last 파서 (codex output에서 agent_message 우선 추출)
- [x] #3 verify가 task_completed 검증 (회귀+task 완수)
- [x] #4 cursor raw 파서 전환 (parse_error 노이즈 제거)
- [x] #5 gemini argv 수정 (`--output-format json` 옵션 없음)
- [x] #5b agent별 env 지원 (GEMINI_CLI_TRUST_WORKSPACE)
- [x] #6 implement fallback (scan 비어도 직접 탐색)
- [x] #7 gemini timeout → codex_scan으로 교체
- [x] #8 verify가 untracked 새 파일 인식
- [x] #9 cursor `--force --trust` 추가 (새 디렉토리)
- [x] #10 verify test_command N/A placeholder 처리
- [x] #11 codex_patch sandbox (`--full-auto`)

---

## Phase 1 — 안정화 ✅ 완료

### 새 라우트
- [x] `--route simple`: codex_patch + verify (2 step)
- [x] `--route complex`: scan + design + implement + verify + review (5 step, review는 Phase 2)

### Robustness
- [x] config.json JSON Schema 검증 (input_from 참조 무결성 포함)
- [x] 엣지케이스 4건 (CLI 미설치, retries, 5MB+ output, 빈 task)
- [x] worktree 자동 생성/정리 (moderate/complex)
- [x] decisions.md 자동 append (DONE 시에만)
- [x] post-run validator (changed_files, allowed/forbidden paths, max_loc)

### UX
- [x] `--allow-dirty` 옵션
- [x] `brain status` — 최근 N개 run 표
- [x] `brain show <id|latest>` — 상세 보기 (steps, files, verify, FAILED 원인)
- [x] `brain apply <id|latest>` — worktree 결과를 cwd에 적용
- [ ] 컬러 출력 (ANSI) — 보류, 가치 낮음

---

## Phase 2 — 고급 기능 (진행 중)

### 자동화
- [x] **메타인지 review step** (complex route 5번째) — verify가 놓친 이슈 catch
- [x] **자동 복잡도 분류** (`--route auto`, 키워드 기반)
- [ ] **신경가소성**: 성공/실패 통계 → 라우팅 가중치
  - **차단 조건**: decisions.md에 50-100개 entry 누적 후 시작 권장
  - 너무 일찍 만들면 학습할 데이터 부족
- [ ] **SQLite 상태 관리** (WAL, FTS)
  - **현재 평가**: 파일 기반으로 충분. 검색/통계 필요해질 때 도입.

### 병렬화
- [ ] **병렬 worktree** (독립 작업 동시 실행)
  - **시나리오 불명확**: 한 사람이 brain run을 1개씩 돌리는 패턴이라 가치 낮음
  - 팀/CI 도입 시 재평가
- [ ] atomic mkdir 기반 task lock
- [ ] 작업 큐 (`brain queue add`)

### 협업 패턴
- [ ] Debate/Critic (설계 시 에이전트 토론) — 비용 큼, 가치 미검증
- [ ] 다단계 review (Codex → Claude 순차) — 고비용, 보류

### 추가 도구 (운영 후 가치 확인되면)
- [ ] `brain history "keyword"` — decisions.md 검색
- [ ] `brain logs <id>` — raw.log 빠른 접근
- [ ] `brain dashboard` — 통계 텍스트 (성공률, 평균 duration)

---

## Phase 3 — 자율 진화 (장기)

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
| Phase 0 완료 | ✅ MVP + 운영 검증 |
| Phase 1 완료 | ✅ 3개 route + 운영 명령 |
| Phase 2 핵심 | ✅ 메타인지 + 자동 분류 |
| Phase 2 잔여 | ⏳ 실사용 데이터 누적 후 |
| Phase 3 | ⏳ 장기 |

---

## 우선순위 결정 기준 (실사용 시)

남은 항목들을 언제 시작할지:

| 항목 | 시작 신호 |
|------|----------|
| 신경가소성 | decisions.md 50+ entry 누적 시 |
| SQLite | run history 검색이 grep으로 답답해질 때 |
| 병렬 worktree | 동시 작업 시나리오 발생 시 |
| Debate/Critic | 설계 결정에서 review가 자주 부족하다고 느낄 때 |
| Vector DB 검색 | text grep으로 비슷한 task 찾기 어려울 때 |
| Dashboard | 통계가 의사결정에 필요해질 때 |

---

## 다음 단계 (실사용)

1. 본인 프로젝트에서 brain run을 일주일 사용
2. 매일 `brain status`로 운영 상태 점검
3. `.brain/decisions.md` 누적되는 동안 패턴 관찰
4. 발견되는 부족한 점이 있으면 그때 Phase 2 잔여 항목 또는 Phase 3 시작
