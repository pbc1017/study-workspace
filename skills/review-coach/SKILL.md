---
name: review-coach
description: Review mistakes and uncertain concepts from a Study Workspace project, diagnose the cause from the learner's answers, and guide spaced retrieval or a targeted retry.
---

# Review coach

Resolve the plugin root two directories above this file. Read [CLI](../../docs/cli.md) and [methodology](../../docs/methodology.md). Load `review <project>` and `progress <project>` before recommending work.

Prioritize unresolved due items and objectives with repeated errors. Inspect prior answers, explanations and hint use. Distinguish a missing concept, wrong assumption, misread condition, calculation/procedure slip, or low confidence only when the evidence supports it. Ask for the learner's reasoning when necessary; do not infer a misconception from one wrong letter alone.

Try unaided recall first. Give a targeted explanation or smaller subproblem if needed, then ask for another independent attempt. For variants, preserve the objective and source grounding; create them through a validated content pack rather than mutating a historical attempt.

The current runtime schedules unresolved questions using a transparent 1/3/7/14/30-day heuristic. Wrong or assisted answers reset the streak. Correct independent retries lengthen the interval. This is a review aid, not a calibrated mastery model. Automatic scheduling is per question; use topic evidence for broader concept recommendations.

Update notes with `mark <project> <question> <json-file>`, preserving existing tags and memo content. Include the mistake cause and one actionable cue when known. Mark resolved when the user chooses to, not just because the solution was displayed. Never delete past mistakes to make progress appear better.

Finish with the actual GUI review link and a bounded next session. Do not create reminders or scheduled automations unless requested.
