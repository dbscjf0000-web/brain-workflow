You are scanning a codebase to find files relevant to a task.

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
