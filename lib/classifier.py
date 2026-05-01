from __future__ import annotations

SIMPLE_KEYWORDS = [
    "docstring",
    "type hint",
    "type annotation",
    "rename",
    "한 줄",
    "oneliner",
    "comment 추가",
    "comment 수정",
    "lint",
    "format",
    "whitespace",
    "log 추가",
    "print 추가",
    "import 정리",
    "unused",
    "typo",
]
COMPLEX_KEYWORDS = [
    "리팩터링",
    "refactor",
    "아키텍처",
    "architecture",
    "재설계",
    "redesign",
    "마이그레이션",
    "migration",
    "의존성 주입",
    "dependency injection",
    "클래스 기반",
    "모듈 분리",
    "책임 분리",
    "결합도",
    "디자인 패턴",
    "design pattern",
    "security 검토",
    "취약점",
    "확장성",
    "scalability",
    "concurrency",
]


def classify(task: str) -> str:
    t = task.lower()
    simple_hits = sum(1 for kw in SIMPLE_KEYWORDS if kw.lower() in t)
    complex_hits = sum(1 for kw in COMPLEX_KEYWORDS if kw.lower() in t)

    if complex_hits >= 1:
        return "complex"
    if simple_hits >= 1:
        return "simple"
    return "moderate"
