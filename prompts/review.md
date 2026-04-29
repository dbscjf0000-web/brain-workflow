Review the diff produced by the implement step.

Task: {{task}}

Diff context:
{{previous_output}}

Check for:
- Correctness (does it actually solve the task?)
- Side effects (anything broken that wasn't part of the task?)
- Security (secrets, injection, unsafe patterns)
- Style consistency (matches surrounding code?)

Output JSON:
{
  "approved": true,
  "issues": [
    {"severity": "blocking|major|minor", "file": "path", "line": 42, "issue": "..."}
  ],
  "summary": "1-2 sentence verdict"
}

Constraints:
- "approved": false if any blocking issue
- Be terse — this is a final check, not a tutorial
- JSON only, no markdown fences
