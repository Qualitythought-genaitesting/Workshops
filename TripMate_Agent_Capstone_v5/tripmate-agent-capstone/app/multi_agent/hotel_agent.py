"""Hotel specialist: search_hotels -> pick the best match -> (on explicit
consent) create_booking + process_payment. Same guardrail-gated execution as
every other specialist.
"""
from typing import Optional

from ..exec_common import execute_tool
from ..llm.nlu import Constraints
from ..tracing import Trace
from .base import SpecialistResult


def search(c: Constraints, city: Optional[str], *, user_id: str, session_id: str, trace: Trace, consent: bool) -> SpecialistResult:
    if not city or not c.date:
        return SpecialistResult("hotel", False, "Hotel agent: I need a city and a check-in date to search hotels.")
    args = {"city": city, "checkin": c.date, "nights": c.nights or 1, "adults": c.pax or 2}
    if c.area:
        args["area"] = c.area
    if c.stars:
        args["stars"] = c.stars
    obs = execute_tool("search_hotels", args, user_id=user_id, session_id=session_id, trace=trace, consent=consent)
    tool_calls = [{"tool": "search_hotels", "args": args, "status": "error" if obs.get("error") else "ok"}]
    if obs.get("error"):
        return SpecialistResult("hotel", False, f"Hotel agent: search failed ({obs['error']['message']}).", tool_calls=tool_calls)
    results = obs.get("results", [])
    if not results:
        return SpecialistResult("hotel", False, f"Hotel agent: no hotels matched in {city} — try a different area or star rating.", tool_calls=tool_calls)
    if c.hotel_name:
        named = next((h for h in results if h["name"].lower() == c.hotel_name.lower()), None)
        best = named or min(results, key=lambda h: h["price_per_night"])
    else:
        best = min(results, key=lambda h: h["price_per_night"])
    summary = (f"Hotel agent: {city} — {best['name']} ({best['stars']}★, {best['area']}) ₹{best['price_per_night']}/night "
               f"× {best['nights']} nights = ₹{best['total_price']} total ({len(results)} option(s) found).")
    return SpecialistResult("hotel", True, summary,
                             data={"offer_id": best["offer_id"], "total_price": best["total_price"]}, tool_calls=tool_calls)


def confirm(offer_id: str, travellers: list, *, user_id: str, session_id: str, trace: Trace, consent: bool) -> SpecialistResult:
    obs = execute_tool("create_booking", {"offer_id": offer_id, "travellers": travellers}, user_id=user_id, session_id=session_id, trace=trace, consent=consent)
    tool_calls = [{"tool": "create_booking", "args": {"offer_id": offer_id}, "status": "error" if obs.get("error") else "ok"}]
    if obs.get("error"):
        return SpecialistResult("hotel", False, f"Hotel agent: couldn't create the booking ({obs['error']['message']}).", tool_calls=tool_calls)
    booking = obs
    pay = execute_tool("process_payment", {"booking_id": booking["pnr"]}, user_id=user_id, session_id=session_id, trace=trace, consent=consent)
    tool_calls.append({"tool": "process_payment", "args": {"booking_id": booking["pnr"]}, "status": "error" if pay.get("error") else "ok"})
    if pay.get("error"):
        return SpecialistResult("hotel", False, f"Hotel agent: booking {booking['pnr']} created but payment failed ({pay['error']['message']}).",
                                 data={"pnr": booking["pnr"]}, tool_calls=tool_calls)
    return SpecialistResult("hotel", True, f"Hotel agent: booked! PNR {booking['pnr']}, charged ₹{pay['amount']}.",
                             data={"pnr": booking["pnr"], "amount": pay["amount"]}, tool_calls=tool_calls)
