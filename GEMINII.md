# Market Data Project

## Core Philosophy
- **Correctness over Completion**: Optimize for correctness. A finished task that solves the wrong problem or introduces hidden complexity is worse than no output at all.
- **Think first. Code second.**
  1. Restate the goal in your own words.
  2. Identify what success looks like — concretely.
  3. Identify what you *don’t* know. Ask before assuming.
  4. Choose the simplest approach that satisfies the success criteria.
  5. Only then write code.

## Tech Stack
- Frontend: Python with Dash (Plotly), Tailwind CSS via components
- Backend/Data: SQLite, Pandas, NumPy

## Architecture & Conventions
- Data Layer: Always isolate SQLite query logic into dedicated modules (e.g., `database/sqlite_connection.py` and `database/database_utils.py`).
- State Management: Use Dash's dcc.Store for client-side state handling; avoid global Python variables.
- Type Hinting: Use explicit Python type hints (`from typing import ...`) for all new function definitions.

## Constraints & Development Rules
- **Simplicity First**: Prefer the boring, obvious solution. Do not add abstractions, generalizations, or “future-proofing” unless explicitly asked.
- **Surgical Edits Only**: Only modify code that is directly relevant to the task. Do not refactor or reformat unrelated code.
- **No Assumptions**: If a requirement is ambiguous, ask a clarifying question before proceeding. Do not invent requirements.
- **No Overengineering**: A working 20-line solution beats an elegant 200-line framework.
- Never hardcode database connection paths; always pull from `os.environ.get('SQLITE_DB_PATH')`.
- Do not use deprecated Dash components (e.g., use `dash.html` instead of `dash_html_components`).
- Never generate massive, multi-thousand-line single files; break components into a `/components` directory.

## Success Criteria
Before considering a task done, verify:
- [ ] Does this solve the stated goal, not a related-but-different goal?
- [ ] Have I run (or can I reason through) the relevant tests?
- [ ] Are my changes scoped to what was asked?
- [ ] Is there anything I assumed that I should have asked about?
- [ ] Would a careful human reviewer be surprised by anything I changed?

## Red Flags (Stop and Reassess)
Stop and ask for clarification if you notice yourself:
- Rewriting something that “seemed messy” but wasn’t part of the task.
- Making a decision because it felt right rather than because it was specified.
- Adding a layer of abstraction to handle cases not mentioned.
- Feeling uncertain but proceeding anyway to avoid “bothering” the user.