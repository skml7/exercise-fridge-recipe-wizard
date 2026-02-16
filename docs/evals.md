# Evals and Feedback Guide

This guide defines how to evaluate the end-to-end chat flow (input → options → selection),
how to collect internal human feedback, and how to run deterministic and judge-based evals.

## Evaluation Rubric (End-to-End)

Score each dimension on a 1–5 scale.

- **Input Understanding**
  - 1: Misses or mis-parses key ingredients/constraints.
  - 3: Captures most key items with minor omissions.
  - 5: Correctly captures ingredients, time, servings, and constraints.
- **Option Quality**
  - 1: Options ignore inputs or are infeasible.
  - 3: Mixed quality; some options align to inputs.
  - 5: All options align to inputs and are feasible.
- **Selection Quality**
  - 1: Selected recipe contradicts options or inputs.
  - 3: Generally consistent but with small issues.
  - 5: Fully consistent with options and user constraints.
- **Reliability**
  - 1: Errors or empty output.
  - 3: Works but with noticeable issues.
  - 5: Smooth responses with no errors.
- **Clarity**
  - 1: Confusing steps or unclear output.
  - 3: Understandable but needs polish.
  - 5: Clear, concise, easy to follow.

Overall score: average of the five dimensions.

## Internal Human Feedback Workflow

Goal: lightweight internal review without user-facing UI.

1. **Capture runs** as JSONL records (one line per run).
2. **Reviewers** score the rubric and leave a short rationale.
3. **Aggregate** scores weekly to spot regressions.

Suggested storage:
- Local JSONL file: `docs/evals_runs.jsonl` (or move to internal datastore later).
- Match to Arize trace IDs when available for debugging.

## Evaluation Record Schema

See `docs/eval_record.schema.json` for a JSON Schema you can validate against.

Minimum fields to capture:
- `eval_id`, `timestamp`, `trace_id`
- `request.messages`, `request.fridge_input`
- `response.options`, `response.selected`
- `scores.*` and `notes`

## Deterministic (Code-Based) Evals

These are offline checks that should never require an LLM:

- **Ingredient overlap**: At least N input ingredients appear in the option ingredients.
- **Time budget**: `time_minutes <= time_budget_minutes`.
- **Steps present**: At least 2 steps.
- **Dietary constraints**: Check forbidden ingredients (if provided).
- **Consistency**: `selected` is one of `options`.

Suggested harness flow:
1. Prepare fixed test inputs (JSON).
2. Call `POST /api/chat/turn` until `next_action == "options"`.
3. Validate deterministic rules on returned options.
4. Optionally call `POST /api/recipes/choose` and verify consistency.

Example test case (input):
```json
{
  "messages": [
    { "role": "assistant", "content": "What's in your fridge?" },
    { "role": "user", "content": "chicken, rice, garlic. 20 min. gluten-free." }
  ],
  "fridge_input": null
}
```

Example deterministic checks (pseudocode):
```python
assert options, "Options should not be empty"
assert all(o["time_minutes"] <= 20 for o in options)
assert any("chicken" in o["ingredients"] for o in options)
```

## Judge-Based Evals (LLM or Human)

Use the same rubric as above and produce a JSON verdict.

### Judge Prompt (LLM)
```
You are a strict evaluator for a recipe assistant.
Score the run on:
Input Understanding, Option Quality, Selection Quality, Reliability, Clarity (1-5).
Provide a brief rationale per score and an overall average.
Return JSON only.

Input:
<messages>
<fridge_input>
<options>
<selected>
```

### Expected Judge Output (Example)
```json
{
  "scores": {
    "input_understanding": 4,
    "option_quality": 3,
    "selection_quality": 4,
    "reliability": 5,
    "clarity": 4
  },
  "overall": 4.0,
  "rationale": {
    "input_understanding": "Captured all ingredients and time.",
    "option_quality": "One option lacked garlic.",
    "selection_quality": "Selected recipe matches the best option.",
    "reliability": "No errors.",
    "clarity": "Steps are mostly concise."
  }
}
```

## Human-as-Judge Checklist

- Ingredients included?
- Time budget respected?
- Steps feasible with listed ingredients/equipment?
- Output concise and easy to follow?

Record the rubric scores and a 1–2 sentence summary of key issues.
