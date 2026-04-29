# 설계 원칙 10가지

> "뇌처럼 생각하되, 기계처럼 실행하라"

이 10가지 원칙은 v1 → v2 → v3 진화 과정에서 3개 에이전트(Gemini, Codex, Claude)의 합의로 도출되었다. 모든 구현 결정은 이 원칙을 따른다.

---

## 1. 뇌처럼 생각하되, 기계처럼 실행하라

뇌의 구조에서 영감은 받되, 실행은 deterministic해야 한다.
- "PFC는 Claude니까 Claude가 라우팅 결정" ❌
- "라우팅은 셸 스크립트, Claude는 설계 시에만" ✅

비유는 **설명용**, 구현은 **capability 기반**.

---

## 2. 오케스트레이터에 LLM을 쓰지 마라

상태전이/검증/라우팅은 셸 또는 Python 스크립트가 담당.
- 비용 0
- 100% 재현 가능
- 비결정성 차단

LLM은 도메인 작업(설계, 구현, 리뷰)에서만 호출.

---

## 3. 에이전트 사이에 시상 필터를 끼워라

뇌의 시상(Thalamus)은 감각 정보를 PFC로 전달하기 전에 필터링한다.

```
Gemini (50K tokens) → 시상 필터 → Claude (5K tokens)
```

- 토큰 비용 90% 절감
- MVP: "10K 이내 핵심만" 프롬프트 제약
- Phase 2: jq/rg 기반 기계적 필터링

---

## 4. 모든 출력은 JSON이다

text 출력 금지. 파싱 가능한 구조만.

| 도구 | 옵션 |
|------|------|
| Gemini | `--output-format json` |
| Claude | `--output-format json` |
| Cursor | `--output-format json` |
| Codex | `--json` (NDJSON) |

파싱 실패 시 raw.log + parse_error.md로 fallback.

---

## 5. 계약은 prompt + 기계적 검증 이중 구조

prompt 제약 (소프트) + post-run validator (하드).

```
"src/auth/만 수정해" (prompt)
       +
git diff --name-only | grep -v '^src/auth/' && FAIL (validator)
```

LLM이 약속을 어길 가능성에 대비.

---

## 6. 실패는 투명하게

실패 시 반드시 저장:
- `failed_reason.md` — 원인
- `last_event` — 어디서 멈췄나
- `repro_command` — 어떻게 재현하나
- artifacts/ — 부분 결과물

침묵 실패 금지.

---

## 7. Kill-switch는 항상 켜져 있다

뇌의 편도체(Amygdala)처럼 위험을 즉시 감지:

| 한도 | 기준 | 동작 |
|------|------|------|
| 시간 | timeout_sec | SIGTERM + 저장 |
| 비용 | cost_budget | 즉시 중단 |
| diff | max_loc | ESCALATE |
| 보안 | .env, *.secret 접근 | 즉시 중단 |
| 패턴 | password, api_key | ESCALATE |
| 반복 | CORRECT 2회 초과 | ESCALATE |

---

## 8. 에이전트 역할을 고정하지 마라

"Codex = 소뇌" ❌
"이 step에서는 Codex를 verifier로 쓴다" ✅

config의 step 단위로 정의. 도구는 교체 가능 (cursor → aider 등).

```yaml
agents:
  codex_verify:    # 검증용
  codex_review:    # 리뷰용
  codex_patch:     # 소규모 수정용
  codex_fix_loop:  # 자동 수정용
```

---

## 9. 원본은 항상 보존하라 (v3 추가)

`raw.log`는 무조건 저장. 파싱 성공/실패와 무관.
- 파싱 성공: raw.log + output.json
- 파싱 실패: raw.log + parse_error.md

디버깅 가능성 보장.

---

## 10. diff는 에이전트가 아닌 git이 만든다 (v3 추가)

에이전트가 보고하는 "변경 파일"을 신뢰하지 말 것.

```python
# ❌ 에이전트 출력에서 diff 추출
diff = response["diff"]

# ✅ git diff로 생성
diff = subprocess.run(["git", "diff", "HEAD"], ...).stdout
```

진실의 출처는 작업 디렉토리.

---

## 원칙 적용 체크리스트

새 기능 추가 시:
- [ ] LLM이 결정해야 하나? (#2 위반 여부)
- [ ] 에이전트 출력이 다음 단계로 그대로 흐르나? (#3 위반 여부)
- [ ] 출력이 text인가? (#4 위반 여부)
- [ ] prompt만으로 제약하나? (#5 위반 여부)
- [ ] 실패 시 무엇이 저장되나? (#6 확인)
- [ ] 무한 루프 가능성? (#7 확인)
- [ ] 도구 교체 가능한가? (#8 확인)
- [ ] raw 출력 보존되나? (#9 확인)
- [ ] git이 진실의 출처인가? (#10 확인)
