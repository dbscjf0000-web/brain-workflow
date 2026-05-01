Verify the recent changes in this working directory.

Task: {{task}}

Context from previous step:
{{previous_output}}

Steps:
1. Inspect actual changes (the source of truth — do not trust the previous step's self-report):
   - Modified/deleted tracked files: `git diff HEAD`
   - **New untracked files: `git ls-files --others --exclude-standard`**
   - Both count as changes for task completion.
2. Decide if the diff actually accomplishes the Task above (task_completed).
3. Run the project test suite (detect command via package.json/pyproject.toml/Makefile/README).
If no test infrastructure exists (no test framework, no test files, no documented test command), set:
  - test_command to empty string `""` (NOT "N/A" or any explanation text)
  - tests_passed to true (vacuously true since there is nothing to fail)
  - failures to `[]`
4. Report results as JSON:
{
  "task_completed": true,
  "task_completed_reason": "diff adds farewell function and corresponding test as requested",
  "tests_passed": true,
  "test_command": "python3 tests/test_hello.py",
  "failures": [],
  "summary": "1-2 sentence overall verdict"
}

If task_completed is false OR tests_passed is false → set summary accordingly.
The JSON must be the LAST item in your response. No markdown fences.
