"""Offline, rule-based assistant for the merchant-services policy assignment."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any


MASTER = "ai-2-data/policy_master_v1.md"
CIRCULAR = "ai-2-data/circular_2026_08_amendment.md"
FAQ = "ai-2-data/merchant_faq_2026-03.md"
AMENDMENT_EFFECTIVE = date(2026, 8, 1)
DELETION_EFFECTIVE = date(2026, 9, 1)


def _parse_date(value: date | str) -> date:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("as_of_date must be a date or an ISO date (YYYY-MM-DD)") from exc


def _cite(document: str, clause: str) -> dict[str, str]:
    return {"document": document, "clause": clause}


def _money(value: Decimal) -> str:
    rounded = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"₹{rounded:,.2f}"


def _answer(
    text: str, citations: list[dict[str, str]], status: str = "ANSWERED"
) -> dict[str, Any]:
    return {"answer": text, "citations": citations, "status": status}


def _amount_from_question(question: str) -> Decimal | None:
    matches = re.findall(
        r"(?:₹|rs\.?\s*)\s*([\d,]+(?:\.\d+)?)(?![\d,]|\s*lakh)",
        question,
        re.IGNORECASE,
    )
    if not matches:
        return None
    try:
        return Decimal(matches[-1].replace(",", ""))
    except InvalidOperation:
        return None


def _is_large_merchant(question: str) -> bool | None:
    text = question.lower()
    if re.search(r"\b(large|above|over|more than)\b.{0,35}\b(10\s*lakh|10,?00,?000)\b", text):
        return True
    if re.search(r"\b(above|over|more than)\s*(?:₹|rs\.?\s*)?\s*10\s*lakh", text):
        return True
    if "large merchant" in text or "large merchants" in text:
        return True
    if re.search(r"\b(small|up to|upto|at most)\b.{0,35}\b(10\s*lakh|10,?00,?000)\b", text):
        return False
    if "small merchant" in text or "small merchants" in text:
        return False
    return None


def _fee_answer(question: str, effective_date: date) -> dict[str, Any]:
    amount = _amount_from_question(question)
    large = _is_large_merchant(question)
    if amount is None or large is None:
        return _answer(
            "I cannot calculate the MDR without both the transaction amount and whether the merchant's monthly UPI volume is up to or above ₹10 lakh.",
            [],
            "CANNOT_ANSWER",
        )

    if effective_date >= AMENDMENT_EFFECTIVE:
        rate = Decimal("0.005") if large else Decimal("0.0025")
        cap = Decimal("25") if large else Decimal("15")
        rate_citation = (
            _cite(MASTER, "2.2")
            if large
            else _cite(CIRCULAR, "B (amends 2.1)")
        )
        citations = [
            rate_citation,
            _cite(CIRCULAR, "C (amends 2.3)"),
            _cite(MASTER, "2.4"),
        ]
    else:
        rate = Decimal("0.005") if large else Decimal("0.003")
        cap = Decimal("15")
        rate_clause = "2.2" if large else "2.1"
        citations = [
            _cite(MASTER, rate_clause),
            _cite(MASTER, "2.3"),
            _cite(MASTER, "2.4"),
        ]

    raw_mdr = amount * rate
    mdr = min(raw_mdr, cap)
    gst = (mdr * Decimal("0.18")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    total = mdr + gst
    rate_text = f"{rate * 100:.2f}%"
    cap_text = f"₹{cap:,.0f}"
    cap_note = (
        f" The applicable MDR cap is {cap_text}."
        if raw_mdr > cap
        else f" The applicable MDR cap is {cap_text}, and it does not reduce this MDR."
    )
    if effective_date >= AMENDMENT_EFFECTIVE and not large:
        cap_note += " The ₹15 cap applies to merchants with monthly volume up to ₹10 lakh."
    elif effective_date >= AMENDMENT_EFFECTIVE and large:
        cap_note += " The ₹25 cap applies to merchants with monthly volume above ₹10 lakh."

    return _answer(
        f"The MDR is {rate_text} of { _money(amount) } ({_money(raw_mdr)} before the cap), "
        f"so the MDR charged is {_money(mdr)}.{cap_note} "
        f"GST at 18% on the MDR is {_money(gst)}; the total deduction is {_money(total)}.",
        citations,
        "CONFLICT_RESOLVED" if effective_date >= AMENDMENT_EFFECTIVE else "ANSWERED",
    )


def ask(question: str, as_of_date: date | str = "2026-08-15") -> dict[str, Any]:
    """Answer a supported policy question for the policy effective on a date.

    Dates before 2026-08-01 use the master policy as written. The circular is
    effective from 2026-08-01 except its Clause 3.3 deletion, effective 2026-09-01.
    """
    if not isinstance(question, str) or not question.strip():
        return _answer("Please provide a non-empty policy question.", [], "CANNOT_ANSWER")
    effective_date = _parse_date(as_of_date)
    text = question.lower()

    if any(word in text for word in ("faq", "frequently asked")) and any(
        word in text for word in ("mdr", "fee", "cap", "upper limit")
    ):
        cap_rule = (
            "The FAQ is stale and incorrect: since 1 August 2026, the circular caps "
            "MDR at ₹15 for merchants up to ₹10 lakh monthly volume and ₹25 for those "
            "above ₹10 lakh."
            if effective_date >= AMENDMENT_EFFECTIVE
            else "The FAQ is stale and incorrect: the master policy caps MDR at ₹15 per UPI transaction."
        )
        citations = [
            _cite(FAQ, "entry: What do I pay on a UPI transaction?"),
            _cite(MASTER, "2.3"),
        ]
        if effective_date >= AMENDMENT_EFFECTIVE:
            citations.append(_cite(CIRCULAR, "C (amends 2.3)"))
        return _answer(
            f"The March 2026 FAQ says there is no upper limit on the fee. {cap_rule}",
            citations,
            "CONFLICT_RESOLVED",
        )

    if any(
        term in text
        for term in (
            "mdr",
            "gst",
            "fee",
            "fees",
            "pay on a upi",
            "transaction cost",
            "what do they pay",
            "what do i pay",
        )
    ):
        if _amount_from_question(question) is not None:
            return _fee_answer(question, effective_date)

    if any(term in text for term in ("refund", "refunded", "reverse the fee", "get the mdr back")) and any(
        term in text for term in ("mdr", "fee", "back", "return", "refund")
    ):
        hours_match = re.search(r"(\d+(?:\.\d+)?)\s*hours?", text)
        within_24 = bool(hours_match and Decimal(hours_match.group(1)) <= 24)
        if effective_date >= DELETION_EFFECTIVE:
            return _answer(
                "No. From 1 September 2026, Clause 3.3 is deleted and Clause 3.2 applies without exception: MDR charged on a refunded transaction is not returned. The FAQ's same-day reversal claim is stale.",
                [
                    _cite(CIRCULAR, "D (deletes 3.3; effective 1 September 2026)"),
                    _cite(MASTER, "3.2"),
                    _cite(FAQ, "entry: If a customer asks for a refund the same day, do I get my fee back?"),
                ],
                "CONFLICT_RESOLVED",
            )
        if within_24:
            citations = [_cite(MASTER, "3.2"), _cite(MASTER, "3.3")]
            if "faq" in text:
                citations.append(
                    _cite(FAQ, "entry: If a customer asks for a refund the same day, do I get my fee back?")
                )
            return _answer(
                "Yes. Before 1 September 2026, a refund initiated within 24 hours reverses the MDR in full; a refund 3 hours after the sale qualifies.",
                citations,
                "ANSWERED",
            )
        if hours_match:
            return _answer(
                "No. Before 1 September 2026, the exception only applies when the refund is initiated within 24 hours; Clause 3.2 says MDR is otherwise not returned.",
                [_cite(MASTER, "3.2"), _cite(MASTER, "3.3")],
            )
        if "same day" in text or "same calendar day" in text or "within 24" in text:
            return _answer(
                "I cannot determine eligibility from 'same day' alone: the policy exception is specifically within 24 hours of the transaction. Before 1 September 2026, a refund within 24 hours reverses MDR; from that date, no exception applies.",
                [
                    _cite(MASTER, "3.2"),
                    _cite(MASTER, "3.3"),
                    _cite(CIRCULAR, "D (deletes 3.3; effective 1 September 2026)"),
                ],
                "CANNOT_ANSWER",
            )
        return _answer(
            "MDR is not returned on a refunded transaction, except for refunds initiated within 24 hours before 1 September 2026. From 1 September 2026, the exception is deleted.",
            [
                _cite(MASTER, "3.2"),
                _cite(MASTER, "3.3"),
                _cite(CIRCULAR, "D (deletes 3.3; effective 1 September 2026)"),
            ],
            "CONFLICT_RESOLVED",
        )

    if (
        "daily" in text
        or "one day" in text
        or "per day" in text
        or "twice" in text
    ) and not any(term in text for term in ("capital", "insurance", "enhanced kyc", "per transaction")):
        if effective_date >= AMENDMENT_EFFECTIVE:
            return _answer(
                "No. The daily limit is ₹1,00,000 per customer account or the customer's own bank limit, whichever is lower, across all UPI transactions. Two ₹1,00,000 payments in one day would exceed it.",
                [_cite(CIRCULAR, "E (amends 4.3)")],
                "CONFLICT_RESOLVED",
            )
        return _answer(
            "No. The daily limit is ₹1,00,000 per customer account across all UPI transactions, so two ₹1,00,000 payments in one day exceed it.",
            [_cite(MASTER, "4.3")],
        )

    if (
        "limit" in text
        and ("per transaction" in text or "maximum amount" in text or "customer pay" in text)
    ) or any(term in text for term in ("capital-markets", "capital markets", "enhanced kyc")):
        if effective_date >= AMENDMENT_EFFECTIVE:
            return _answer(
                "The standard UPI per-transaction limit is ₹1,00,000. Capital Markets and Insurance merchants may accept up to ₹2,00,000 per transaction only after enhanced KYC; separately, the customer's total daily UPI limit is the lower of ₹1,00,000 and their bank's limit.",
                [
                    _cite(MASTER, "4.1"),
                    _cite(MASTER, "4.2"),
                    _cite(MASTER, "4.4"),
                    _cite(CIRCULAR, "E (amends 4.3)"),
                ],
                "CONFLICT_RESOLVED",
            )
        return _answer(
            "The standard UPI per-transaction limit is ₹1,00,000. Capital Markets and Insurance merchants may accept up to ₹2,00,000 only after enhanced KYC; the separate daily limit is ₹1,00,000 per customer account.",
            [_cite(MASTER, "4.1"), _cite(MASTER, "4.2"), _cite(MASTER, "4.3"), _cite(MASTER, "4.4")],
        )

    if any(term in text for term in ("close my account", "closed my account", "account closure", "close the account")):
        return _answer(
            "Pending settlements are released within 10 working days of account closure, after deducting outstanding dues. The policy does not provide enough information to calculate the exact release date without the closure date and applicable bank holidays.",
            [_cite(MASTER, "5.2")],
        )

    if "card" in text and any(term in text for term in ("settle", "settlement", "money", "payment")):
        return _answer(
            "No. Card transactions settle T+2 (two working days); bank holidays can move settlement to the next working day.",
            [_cite(MASTER, "1.2"), _cite(MASTER, "1.3")],
        )

    if "upi" in text and any(term in text for term in ("settle", "settlement", "money", "receive", "when")):
        if effective_date >= AMENDMENT_EFFECTIVE:
            return _answer(
                "UPI settlement is T+0 (same day, by 11:59 PM) for merchants with an active Instant Settlement add-on, and T+1 (next working day) for all others. The question does not specify whether the add-on is active.",
                [_cite(CIRCULAR, "A (amends 1.1)")],
                "CONFLICT_RESOLVED",
            )
        return _answer(
            "UPI settlement is T+1 (the next working day). Sundays and bank holidays are excluded, and a settlement date falling on a bank holiday moves to the next working day.",
            [_cite(MASTER, "1.1"), _cite(MASTER, "1.3")],
        )

    return _answer(
        "I cannot answer this from the supplied policy documents. Please ask about a documented policy topic or provide more detail.",
        [],
        "CANNOT_ANSWER",
    )
