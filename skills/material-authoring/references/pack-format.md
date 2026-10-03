# Learning pack v1

This is a content exchange format, not a complete progress backup. Use `backup` for a restorable database + source snapshot. Arrays omitted from a content import are not deleted.

```json
{
  "schemaVersion": 1,
  "topics": [{
    "id": "linear-independence",
    "title": "Linear independence",
    "objectives": ["Use the definition to find a nontrivial linear relation"],
    "body": "## Definition\nExplain the condition, then give an example and counterexample.",
    "sourceRefs": ["source-id, lecture 2, page 4"]
  }],
  "questions": [{
    "id": "independence-001",
    "number": "1",
    "type": "essay",
    "prompt": "Why is a set containing the zero vector linearly dependent?",
    "rubric": "1 point: construct coefficients with the zero vector coefficient nonzero. 1 point: connect this to the definition.",
    "points": 2,
    "explanation": "Set the zero vector's coefficient to 1 and all others to 0.",
    "topics": ["linear-independence"],
    "sourceRefs": ["source-id, lecture 2, page 4"],
    "origin": "generated",
    "status": "active"
  }]
}
```

Question types:

| type | Additional fields | Evaluation |
|---|---|---|
| `single` | `options: [{label: "A", text: "…"}, …]`, `answer: ["A"]` | Exact label match |
| `multiple` | Same options, `answer: ["A", "C"]` | Set equality, no partial credit |
| `short` | `answer: ["accepted answer", "alias"]` | Unicode NFKC, case and whitespace normalization |
| `essay` | `rubric: "criteria"`, optional `points` | Pending until user self-assesses |

`points` defaults to 1. IDs are stable strings, maximum 150 characters. Topic links must resolve within this project. `origin` is `original` or `generated`; it does not indicate an independent correctness review. Active content is eligible for practice; draft content is not. Options require 2–20 unique labels, at least one valid answer, and exactly one answer for `single`.

Examples are in the plugin's `examples/biology.json`, `examples/linear-algebra.json`, and `examples/aws.json`. They contain only newly authored teaching samples, not redistributed course materials.
