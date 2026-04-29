You are designing the implementation approach for a complex task.

Task: {{task}}

Context from scan:
{{previous_output}}

Produce a design that breaks the task into atomic steps. Output JSON:
{
  "approach": "1-2 sentence high-level approach",
  "steps": [
    {"order": 1, "what": "...", "why": "...", "files": ["path1"]},
    {"order": 2, "what": "...", "why": "...", "files": ["path2"]}
  ],
  "risks": [
    {"risk": "...", "mitigation": "..."}
  ],
  "rollback_plan": "how to undo if things go wrong"
}

Constraints:
- 3-7 steps total
- Each step must be independently verifiable
- Output under 8K tokens
- JSON only, no markdown fences
