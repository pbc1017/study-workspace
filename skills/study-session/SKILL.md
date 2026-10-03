---
name: study-session
description: Run a focused study session in an existing Study Workspace project through the local GUI or agent conversation, using retrieval, application, and evidence-based feedback rather than passive rereading.
---

# Study session

Resolve the plugin root two directories above this file and read [CLI](../../docs/cli.md) and the relevant [methodology](../../docs/methodology.md). Use the same project ID and data home throughout.

Read project progress and topics. Choose a small objective aligned with the user's available time. Start with unaided recall or an attempt before offering a full explanation. When useful, explain a worked example, reduce scaffolding, then give an independent application.

For GUI practice, use `start <project> --count N [--topic ID]` or open `/projects/<project>/practice`. Check the available question count rather than silently lowering an exam's required count. The AWS preset is an optional 65-question/90-minute simulation, not a requirement for other subjects.

For a conversational session, `session`, `answer`, and `submit` operate on the same persisted session. Read the current item version before saving; pass it with the answer. A conflict means another interface changed the item: reload instead of overwriting. In exam mode, do not fetch the answer bank or reveal solutions before submission unless the user explicitly changes the activity to guided study.

Let the learner respond before showing the answer. Record hints or source consultation as assisted work and confidence only when provided by the learner. Do not fill in confidence, time spent, or independent-success evidence by guessing. Explain mistakes in terms of the objective and reasoning, not only the correct option.

After submission, show objective-level evidence and choose one useful next step. Essay answers require the learner's self-assessment using the rubric. You may offer qualitative rubric feedback, but the `assess` command records a self-assessment: only use it for a score explicitly selected or accepted by the learner. This version does not store provisional AI grades.

If the agent is disconnected, the GUI still supports study, deterministic grading, and self-assessment. Do not promise background AI feedback or claim a pending worker will run automatically.
