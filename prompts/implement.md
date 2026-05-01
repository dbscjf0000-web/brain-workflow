Implement the following task in the current working directory.

Task: {{task}}

Allowed paths: {{allowed_paths}}

Context from scan step (may be empty or unstructured):
{{previous_output}}

Instructions:
- If the scan context above includes a `files` array, prefer those paths.
- ★ If the scan context is empty, raw text, or doesn't list specific files,
  explore the working directory yourself (ls/find/cat) and identify the relevant files.
- Make the minimal change needed to satisfy the task.
- Do not refactor unrelated code or modify files outside the task scope.
- Do not introduce new dependencies.

After editing, append a JSON object describing what you changed:
{
  "changed_files": ["path1", "path2"],
  "summary": "what was done in 1-2 sentences"
}
The JSON object must be the LAST item in your response. No markdown fences around the JSON.
