---
name: material-authoring
description: Turn a learner's local course materials into source-linked concepts, worked examples, and practice activities in an existing Study Workspace project. Supports school, university, and certification content with subject-appropriate evaluation.
---

# Material authoring

Resolve the plugin root two directories above this file. Read [CLI](../../docs/cli.md), [methodology](../../docs/methodology.md), and [pack format](references/pack-format.md) for the current task. All commands use `python3 <plugin-root>/scripts/study.py` and the user's data home.

Inspect the project's existing topics, questions, sources, and goal before creating content. Read the relevant original materials. Avoid turning missing source material into invented textbook claims or instructor requirements.

Prepare a project-scoped JSON pack in the data home (not the public plugin checkout):

- Each topic contains observable learning objectives, an explanation, a worked example or useful contrast, and a prompt to recall without looking.
- Select activities based on the actual learning goal: definitions and contrasts, causal explanation, numerical application, argument, proof, or exam scenario. Do not force everything into multiple-choice questions.
- Use source IDs and page/section references. Clearly distinguish original questions from generated ones. Generated variants should test the same objective without only changing superficial wording.
- For quantitative subjects, include assumptions, units and intermediate reasoning in explanations. Do not declare equivalent mathematical expressions wrong because their strings differ. Use essay + rubric for proof and process-based tasks in this version.
- `short` uses normalized exact accepted strings. Include justified aliases; do not use it for unrestricted reasoning. `essay` uses a rubric and explicit self-assessment. Code execution, OCR, symbolic math, and automatic agent grading are not implemented by this runtime.
- Keep uncertain questions as `status: draft`; they are excluded from practice. Mark uncertainty in the explanation and resolve against the source before activating. A schema-valid pack is not proof of factual correctness.

Use stable topic and question IDs. Reimporting the same IDs updates content with retained question revisions. Do not renumber IDs because the teaching order changes. Omitted questions are retained; set `status: draft` to remove a question from new practice without deleting attempts.

Run `import <project-id> <pack> --dry-run`, address errors, then import within the user's requested authoring scope. Structural validation is followed by a content review of answer keys, distractors, assumptions and source alignment. Report the actual topic/question/draft counts and open the project's concept page.
