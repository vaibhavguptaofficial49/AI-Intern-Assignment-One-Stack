"""Run the offline evaluation cases and print a compact pass/fail report."""

from __future__ import annotations

import json
from pathlib import Path

from app import ask


def main() -> int:
    cases = json.loads(Path(__file__).with_name("eval.json").read_text(encoding="utf-8"))
    failures = 0
    print(f"{'#':>2}  {'RESULT':<6}  {'STATUS':<17}  QUESTION")
    print("-" * 100)
    for index, case in enumerate(cases, start=1):
        result = ask(case["question"], case["as_of_date"])
        passed = (
            result["answer"] == case["expected_answer"]
            and result["citations"] == case["expected_citations"]
        )
        if not passed:
            failures += 1
        print(
            f"{index:>2}  {'PASS' if passed else 'FAIL':<6}  "
            f"{result['status']:<17}  {case['question']}"
        )
        if not passed:
            print(f"    Expected answer: {case['expected_answer']}")
            print(f"    Actual answer:   {result['answer']}")
            print(f"    Expected cites:  {case['expected_citations']}")
            print(f"    Actual cites:    {result['citations']}")
    passed_count = len(cases) - failures
    print("-" * 100)
    print(f"Score: {passed_count}/{len(cases)} ({passed_count / len(cases):.0%})")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
