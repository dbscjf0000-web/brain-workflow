Run tests and verify the recent changes.

Task: {{task}}

Previous step output:
{{previous_output}}

Instructions:
1. Detect the project's test command (package.json, pyproject.toml, Cargo.toml, etc.)
2. Run the test suite
3. Capture pass/fail status and any failure messages
4. Report results as JSON:
{
  "tests_passed": true,
  "test_command": "npm test",
  "failures": [],
  "summary": "1-2 sentence result"
}

If tests fail:
- Set "tests_passed": false
- List failures briefly in the "failures" array
- Do NOT attempt to fix here — that is the next step's job

Output the JSON at the end. No markdown fences.
