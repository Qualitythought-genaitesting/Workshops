"""Flight specialist: search_flights -> pick the best match -> (on explicit
consent) create_booking + process_payment. Runs through the same
guardrail-gated `execute_tool` as the single ReAct agent, so switching between
single-agent and multi-agent mode never changes what's allowed.
"""
from ..exec_common import execute_tool
from ..llm.nlu import Constraints
from ..tracing import Trace
from .base import SpecialistResult


def search(c: Constraints, *, user_id: str, session_id: str, trace: Trace, consent: bool) -> SpecialistResult:
    if not (c.origin and c.dest and c.date):
        return SpecialistResult("flight", False, "Flight agent: I need an origin, destination and date to search flights.")
    args = {"from": c.origin, "to": c.dest, "date": c.date, "pax": c.pax or 1}
    if c.depart_before:
        args["depart_before"] = c.depart_before
    if c.depart_after:
        args["depart_after"] = c.depart_after
    if c.cabin:
        args["cabin"] = c.cabin
    if c.non_stop:
        args["non_stop"] = True
    if c.budget:
        args["max_price"] = c.budget
    obs = execute_tool("search_flights", args, user_id=user_id, session_id=session_id, trace=trace, consent=consent)
    tool_calls = [{"tool": "search_flights", "args": args, "status": "error" if obs.get("error") else "ok"}]
    if obs.get("error"):
        return SpecialistResult("flight", False, f"Flight agent: search failed ({obs['error']['message']}).", tool_calls=tool_calls)
    results = obs.get("results", [])
    if not results:
        return SpecialistResult("flight", False, "Flight agent: no flights matched — try relaxing the budget or time window.", tool_calls=tool_calls)
    if c.cheapest:
        results = sorted(results, key=lambda f: f["price"])
    if c.airline:
        matched = [f for f in results if c.airline.lower() in f["airline"].lower()]
        results = matched or results
    best = results[0]
    summary = (f"Flight agent: {c.origin}→{c.dest} on {c.date} — {best['airline']} {best['flight_no']} "
               f"{best['depart']}→{best['arrive']}, ₹{best['price']}/person (₹{best['total_price']} total, "
               f"{len(results)} option(s) found).")
    return SpecialistResult("flight", True, summary,
                             data={"offer_id": best["offer_id"], "total_price": best["total_price"], "options": results[:5]},
                             tool_calls=tool_calls)


def confirm(offer_id: str, travellers: list, *, user_id: str, session_id: str, trace: Trace, consent: bool) -> SpecialistResult:
    obs = execute_tool("create_booking", {"offer_id": offer_id, "travellers": travellers}, user_id=user_id, session_id=session_id, trace=trace, consent=consent)
    tool_calls = [{"tool": "create_booking", "args": {"offer_id": offer_id}, "status": "error" if obs.get("error") else "ok"}]
    if obs.get("error"):
        return SpecialistResult("flight", False, f"Flight agent: couldn't create the booking ({obs['error']['message']}).", tool_calls=tool_calls)
    booking = obs
    pay = execute_tool("process_payment", {"booking_id": booking["pnr"]}, user_id=user_id, session_id=session_id, trace=trace, consent=consent)
    tool_calls.append({"tool": "process_payment", "args": {"booking_id": booking["pnr"]}, "status": "error" if pay.get("error") else "ok"})
    if pay.get("error"):
        return SpecialistResult("flight", False, f"Flight agent: booking {booking['pnr']} created but payment failed ({pay['error']['message']}).",
                                 data={"pnr": booking["pnr"]}, tool_calls=tool_calls)
    return SpecialistResult("flight", True, f"Flight agent: booked! PNR {booking['pnr']}, charged ₹{pay['amount']}.",
                             data={"pnr": booking["pnr"], "amount": pay["amount"]}, tool_calls=tool_calls)
