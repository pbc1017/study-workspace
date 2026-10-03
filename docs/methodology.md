# Learning methodology

The unit of organization is a **learning project**: one course, semester, exam scope, or personal inquiry. It has its own sources, objectives, concepts, questions, attempts, and review queue. A topic is a teaching unit inside a project. An objective states what a learner should be able to explain or do.

## A small complete learning loop

1. Establish an observable objective and the relevant source. Identify prerequisites when the material depends on them.
2. Elicit prior knowledge with unaided recall or a short problem. Preserve uncertainty; this is diagnosis, not a high-stakes grade.
3. Explain the missing concept using an example, comparison, derivation, or counterexample appropriate to the subject.
4. Ask the learner to retrieve or apply it without the source. Offer progressively smaller hints when needed, and record assistance.
5. Compare the answer with explicit criteria. Explain the reasoning and cause of mistakes; let the learner correct their model.
6. Revisit after a delay, preferably with a meaningful variation. Use the accumulated evidence to decide what comes next.

Do not require every step for every request. A user asking for a direct explanation should receive one; a learner explicitly practicing an exam should not be interrupted by unnecessary tutoring.

## Subject-specific choices

| Goal | Activity | Suitable evaluation |
|---|---|---|
| Vocabulary, taxonomy, factual distinctions | Recall, comparison, classification | Explicit answer key with justified aliases |
| Causal or conceptual understanding | Explain, predict, compare cases | Criterion-based rubric and self-correction |
| Mathematics and engineering | Worked example, independent solution, changed assumptions | Reasoning, units, assumptions, final answer |
| Proof and theory | Reconstruct argument, find counterexample | Valid premises and logical steps |
| Humanities | Read, cite evidence, build argument | Evidence and reasoning rubric |
| Certification | Scenario decision, timed simulation | Published app preset and exact option matching |

Preserve the course's definitions and instructor criteria. Explain disagreements with other references instead of silently overwriting them. Neither multiple-choice correctness nor a keyword match establishes complete conceptual understanding.

## Evidence and review

Keep attempts separate from the current content. Question revisions and per-session snapshots make past results interpretable when material changes. Record unaided success, assistance, learner confidence, and unresolved evaluation separately. The current app shows topic-level attempts, distinct questions, confirmed accuracy and assistance; it does not claim calibrated mastery.

The initial scheduler is per question: incorrect/assisted attempts reset the interval to one day; subsequent independent correct retries use 3, 7, 14 and 30 days. Users can resolve items explicitly. This deliberately simple heuristic can later be replaced without changing the content format.

## Agent and platform boundaries

The agent reads sources, proposes learning content, gives explanations and interprets evidence. The platform validates structure, persists project-scoped state, selects questions, deterministically grades supported answers, and exposes a local GUI. Generated content is not automatically factual because validation passes. Essay self-assessment belongs to the learner; qualitative AI feedback should remain distinguishable.

Local storage does not imply offline model inference. Using Codex or Claude Code to interpret material follows that host's model and data settings. The GUI itself has no external network dependencies, analytics, or model API calls.
