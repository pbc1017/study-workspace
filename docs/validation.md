# Validation notes — 2026-10-03

## Automated

- 19 Python tests passed locally on Python 3.14 / macOS.
- Coverage includes project isolation, atomic/idempotent imports, session snapshots after content edits, answer conflicts from two connections, four question types, essay self-assessment, exact AWS exam counts/scoring, persisted expiry, review intervals, source deduplication, backup restore, synthetic legacy migration, and HTTP authentication/origin checks.
- `node --check web/app.js` passed.
- Concurrent local runtimes use port-specific session cookies, verified with a shared browser cookie jar.
- Portable package validation passed: root and Claude manifests, two marketplaces, five skills, three example packs.
- All five skills passed the skill-creator frontmatter validator.
- Claude Code 2.1.114 `plugin validate` passed for the plugin and marketplace without warnings.
- GitHub Actions is configured for Python 3.10/3.12/3.14 on Linux and macOS, plus JavaScript syntax validation.

## Browser

Verified in Chromium over local CDP with a separate demo-only data home:

- Project library and independent project navigation.
- New-project modal and JSON file import through the browser.
- Concept rendering and linked practice.
- Single-choice, multiple-choice, short-answer, and essay input.
- Autosave, question navigation, review flags, submission and result display.
- Essay remains pending before self-assessment; learner-selected rubric score updates the result.
- Wrong-answer queue, mistake tags and memo persistence.
- History chart rendering; fixed an initial chart overflow found during screenshot inspection.
- 390px mobile concept page: no document-level horizontal overflow.

## Private legacy compatibility

A private local AWS application was migrated into an isolated local data home, not this repository. Verified 289 questions, 37 extracted concept sections (36 previously configured plus one additional source-note section), 37 sessions, 33 saved results and 45 study marks. Every imported question has a concept mapping. Saved scored-question counts and correct counts were checked; saved AWS scaled scores were compared before commit. Legacy result records remain attached to the imported history. The source database was read-only.

No source question bank, personal answer, original PDF, memo, private database, or token is included in the public package. The README screenshot contains only the newly authored demonstration projects.

## Scope of this evidence

Manifest/marketplace validation does not establish that every host version's plugin browser has discovered the package. Interactive discovery in a fresh Codex profile and a full tutoring conversation in both hosts have not been verified. Installation instructions follow the current official Codex packaging format and validated Claude marketplace format. The same standalone runtime and CLI are used by both skills.

This release does not validate AI factual accuracy automatically, predict official exam scores, or provide background agent grading. These limits are also stated in the skills and README.
