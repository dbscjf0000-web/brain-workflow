You are running inside the working directory. Inspect files directly via ls/find/cat before making changes.

Task: {{task}}

Allowed paths: {{allowed_paths}}

Instructions:
- Explore the working directory yourself.
- Make the minimal change needed for the task.
- Do not refactor unrelated code.
- Do not introduce new dependencies.
- Do not modify .env*, *.secret, *.lock files.

After editing, append a JSON object describing what you changed:
{
  "changed_files": ["path1"],
  "summary": "what was done in 1-2 sentences"
}
The JSON must be the LAST item. No markdown fences.
