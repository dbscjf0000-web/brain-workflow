Implement the following task based on the scan results.

Task: {{task}}

Allowed paths: {{allowed_paths}}

Context from scan step:
{{previous_output}}

Constraints:
- Only modify files listed in the scan `files` array
- Do not modify test files unless explicitly listed
- Do not refactor unrelated code
- Keep changes minimal and focused
- Do not introduce new dependencies

After editing, report what you changed as JSON:
{
  "changed_files": ["path1", "path2"],
  "summary": "what was done in 1-2 sentences"
}

Output the JSON at the end of your response. No markdown fences.
