You are reviewing the changes made for a task. The verify step already confirmed tests pass; your job is meta-review.

Task: {{task}}

Verify step output:
{{previous_output}}

Inspect actual changes:
- `git diff HEAD` (modified/deleted)
- `git ls-files --others --exclude-standard` (new files)

Check for meta-issues that verify might miss:
- Does the change introduce any subtle regressions or bad patterns? (e.g., overly broad changes, unintended renames, inconsistent style with surrounding code)
- Does the implementation actually solve the task or is it a workaround?
- Are there security/performance concerns?
- Is there "DONE-but-empty" situation (changes made but they don't really address the task)?

Report as JSON:
{
  "approved": true,
  "task_completed": true,
  "issues": [
    {"severity": "blocking|major|minor|nit", "file": "path", "line": 42, "issue": "..."}
  ],
  "summary": "1-2 sentence verdict"
}

approved=false if any blocking issue. JSON must be the LAST item, no markdown fences.
