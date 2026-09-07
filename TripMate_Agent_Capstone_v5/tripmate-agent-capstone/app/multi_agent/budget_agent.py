"""Budget specialist: sums whatever the flight/hotel specialists priced this
turn against the session's spend so far, and flags an over-budget combination
*before* anyone tries to confirm — in addition to the GR-SPEND check that
`execute_tool` still enforces on every actual create_booking call. No tool
call of its own; this is pure arithmetic against the same session_spend the
guardrail layer tracks, so it's always in sync with what's actually been paid.
"""
from ..config import settings
from ..data import store
from .base import SpecialistResult


def check(session_id: str, proposed_items: dict) -> SpecialistResult:
    """`proposed_items` maps a label ("flight", "hotel", ...) to a price in INR."""
    already_spent = store.session_spend.get(session_id, 0)
    proposed_total = sum(v for v in proposed_items.values() if v)
    remaining = settings.session_spend_limit - already_spent
    if not proposed_total:
        return SpecialistResult("budget", True, "", data={"already_spent": already_spent, "remaining": remaining})
    breakdown = "; ".join(f"{k} ₹{v:,}" for k, v in proposed_items.items() if v)
    if proposed_total > remaining:
        summary = (f"Budget agent: {breakdown} = ₹{proposed_total:,} total, but only ₹{remaining:,} remains of your "
                   f"₹{settings.session_spend_limit:,} session limit (already spent ₹{already_spent:,}) — "
                   f"drop or downgrade something before confirming.")
        return SpecialistResult("budget", False, summary,
                                 data={"already_spent": already_spent, "proposed_total": proposed_total, "remaining": remaining, "over_budget": True})
    summary = (f"Budget agent: {breakdown} = ₹{proposed_total:,} total, within your ₹{remaining:,} remaining "
               f"(of ₹{settings.session_spend_limit:,}).")
    return SpecialistResult("budget", True, summary,
                             data={"already_spent": already_spent, "proposed_total": proposed_total, "remaining": remaining, "over_budget": False})
