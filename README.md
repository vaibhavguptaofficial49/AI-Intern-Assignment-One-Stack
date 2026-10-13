# AI Intern Assignment 2: The Policy That Changed

An offline, deterministic assistant for the merchant-services policy documents in `ai-2-data/`.

## Run the evaluation

Use Python 3.10 or later; no third-party packages or API keys are required.

```powershell
python run_eval.py
```

`app.ask(question, as_of_date)` returns an object with `answer`, `citations` (document and clause/FAQ entry), and `status` (`ANSWERED`, `CONFLICT_RESOLVED`, or `CANNOT_ANSWER`). The date may be an ISO `YYYY-MM-DD` string or a Python `date`; if omitted, the assignment default `2026-08-15` is used.

## What works

- Answers the assignment's settlement, MDR/GST, refund, daily/per-transaction limit, card settlement, and account closure questions.
- Selects the applicable rule by `as_of_date`; the August circular is effective 1 August 2026, except deletion of Clause 3.3 effective 1 September.
- Treats the dated FAQ as stale when contradicted by the master policy or circular and cites the controlling sources.
- Calculates MDR, caps and 18% GST using `Decimal`.
- Abstains when the policy or question does not support an exact answer.
- `eval.json` includes all eight required questions and additional adversarial/edge cases. The evaluator checks exact answer text and citation lists.

## What does not work

This is a small rule-based prototype, not a general natural-language system. It supports common question phrasings, but can miss unusual wording, cannot infer absent merchant/account details, and has no bank-holiday calendar for exact dates. See [DECISIONS.md](./DECISIONS.md) and [WHERE_IT_BREAKS.md](./WHERE_IT_BREAKS.md) for the chosen interpretations and limitations.

AI assistance used to build this assignment is disclosed in [AI_USAGE.md](./AI_USAGE.md).
