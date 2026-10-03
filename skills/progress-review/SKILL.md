---
name: progress-review
description: Summarize a Study Workspace project's learning evidence and adjust study priorities using attempts, topic coverage, hint use, pending evaluations, and the learner's goals.
---

# Progress review

Resolve the plugin root two directories above this file. Read [CLI](../../docs/cli.md). Load `progress`, `history`, and `review` for the requested project. Compare the evidence to the project's stated goal or exam scope.

Report what was practiced, accuracy on confirmed answers, distinct questions attempted, hint use, and pending self-assessment. Separate unfamiliar topics from practiced-but-difficult topics. High accuracy on repeated identical questions is weaker evidence of transfer than success on varied tasks.

Do not equate page views, time open, or one correct answer with mastery. Do not claim trends when the history is too short or compare scores with incompatible rubrics as if they were identical. AWS scaled scores are this application's simulation only, not a prediction of the official exam.

Propose the smallest useful plan: which objective to revisit, which source to reread, and what independent activity would provide better evidence. Base time estimates on the learner's stated availability rather than fabricated study durations. Preserve prior goals unless the user asks to change them.

Return project-specific concept, review or history links using the URL from `open --no-browser`. Keep personal materials and records local. For export or migration, distinguish the content JSON export from a full restorable `backup`.
