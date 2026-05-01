You are running inside the working directory. Use ls/find/cat to inspect files directly before answering.

당신은 cwd의 코드베이스를 직접 탐색해 `ls`, `find`, `cat` 등으로 파일을 읽고 분석하라. `find . -type f`로 목록을 잡고 필요한 파일만 열어보면 된다.

You are scanning a codebase in your current working directory: use shell tools to list and read files, then identify files relevant to the task.

Task: {{task}}

Output ONLY valid JSON with this exact structure:
{
  "files": [
    {"path": "src/auth/session.ts", "reason": "session refresh logic", "lines": "42-58"}
  ],
  "risks": ["risk description if any"],
  "plan": ["step 1 description", "step 2 description"],
  "summary": "1-2 sentence summary"
}

Constraints:
- Maximum 10 files in `files` array
- Keep total output under 10K tokens
- JSON only — no explanation text, no markdown fences
- Each `lines` field should be a narrow range (under 50 lines)
- `risks` may be empty array if none
