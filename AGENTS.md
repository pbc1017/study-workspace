# Study Workspace

Keep the runtime portable: Python 3.10+ standard library, static browser assets, no required package installation. Both host plugins share the same skills and runtime.

- User data lives outside this repository. Never commit personal sources, question banks, SQLite databases, runtime tokens, or learning records.
- New course content must work through project-scoped learning packs, not subject-specific application forks.
- Preserve session snapshots, idempotent submission, answer version conflicts, and pending essay assessment.
- User-facing documentation must distinguish implemented behavior from planned features.
- Run `python3 -m unittest discover -s tests -v` and `python3 scripts/validate_plugin.py` for functional changes. Use browser checks for changed user flows.
- Keep public examples original and small. Do not redistribute proprietary course or certification materials.
