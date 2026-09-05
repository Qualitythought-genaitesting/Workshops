"""Offline, deterministic "LLM" for TripMate.

It emulates how a tool-using model reasons (Thought → Action → Observation) using
rule-based NLU, so the whole capstone runs with no API key and every test is
reproducible. Planted classroom defects are marked DEFECT-n.
"""
import json
import re
from typing import Any, Dict, List, Optional

from ..config import settings
from ..data import CODE_TO_CITY
from .base import BaseLLM, LLMStep, TurnContext
from .nlu import Constraints, detect_intent, extract


def _tok(s: Any) -> int:
    return max(1, len(json.dumps(s, default=str)) // 4)


def _calls(scratch: List[dict], tool: str) -> List[dict]:
    return [s for s in scratch if s.get("tool") == tool]


def _ok(step: dict) -> bool:
    return bool(step.get("observation")) and not step["observation"].get("error")


def _err(step: dict) -> Optional[dict]:
    return (step.get("observation") or {}).get("error")


def _inr(n: int) -> str:
    return f"₹{n:,}"


def _fmt_flight(f: dict) -> str:
    return f"{f['airline']} {f['flight_no']} {f['depart']}→{f['arrive']} {_inr(f['price'])}/person ({_inr(f['total_price'])} total)"


def _fmt_hotel(h: dict) -> str:
    return f"{h['name']} {h['stars']}★ {h['area']} {_inr(h['price_per_night'])}/night ({_inr(h['total_price'])} for {h['nights']} nights, {h['distance_to_beach_m']} m from beach)"


class MockLLM(BaseLLM):
    name = "mock-llm-1.0"

    # ------------------------------------------------------------------ plan
    def plan(self, ctx: TurnContext) -> List[str]:
        intent = detect_intent(ctx.message)
        c = extract(ctx.message)
        plan = [f"Understand request (intent={intent})"]
        if intent == "trip":
            if c.traveller_name:
                plan.append("Fetch saved traveller from profile")
            if c.flight or (c.dest and not c.hotel):
                plan.append("Search flights with all constraints" + (" (outbound + return)" if c.return_date else ""))
            if c.hotel:
                plan.append("Search hotels with constraints")
            plan.append("Present options and ask for confirmation before any booking")
        elif intent in ("confirm_yes", "book_selected"):
            plan.append("Create booking → charge card on file → report PNR")
        elif intent == "cancel":
            plan.append("Identify booking → verify ownership → confirm → cancel")
        elif intent == "policy":
            plan.append("Retrieve policy document and answer")
        elif intent == "weather":
            plan.append("Fetch forecast, then resume any pending booking")
        else:
            plan.append("Respond directly (no tool needed)")
        return plan

    # ------------------------------------------------------------------ step
    def step(self, ctx: TurnContext, scratch: List[dict], iteration: int) -> LLMStep:
        intent = detect_intent(ctx.message)
        # generic retry policy on transient tool errors
        if scratch:
            last = scratch[-1]
            e = _err(last)
            if e and e.get("code") in ("UPSTREAM_UNAVAILABLE", "TIMEOUT", "MALFORMED_RESPONSE") and last.get("tool") != "process_payment":
                attempts = len([s for s in scratch if s.get("tool") == last["tool"] and s.get("args") == last["args"]])
                limit = 2 if e["code"] == "MALFORMED_RESPONSE" else 3
                if attempts < limit:
                    return self._t(f"{last['tool']} failed with {e['code']}; retrying ({attempts}/{limit - 1})", last["tool"], last["args"], ctx, scratch)
                return self._final(f"I'm sorry — the {last['tool'].replace('_', ' ')} service is not responding right now ({e['code']}). "
                                   "I have not made any changes or bookings. Please try again in a few minutes, or tell me if you'd like me to try different dates.", ctx, scratch)
        handler = getattr(self, f"_h_{intent}", self._h_other)
        return handler(ctx, scratch)

    # --------------------------------------------------------------- helpers
    def _t(self, thought: str, tool: str, args: dict, ctx: TurnContext, scratch: List[dict]) -> LLMStep:
        return LLMStep(thought=thought, tool=tool, args=args, tokens_in=_tok(ctx.message) + _tok(scratch) + 350, tokens_out=_tok(args) + 20)

    def _final(self, text: str, ctx: TurnContext, scratch: List[dict], thought: str = "I have what I need; composing the reply.") -> LLMStep:
        return LLMStep(thought=thought, final=text, tokens_in=_tok(ctx.message) + _tok(scratch) + 350, tokens_out=_tok(text))

    def _constraints(self, ctx: TurnContext) -> Constraints:
        c = extract(ctx.message)
        prev: Optional[dict] = ctx.memory.get("constraints")
        if prev:
            p = Constraints(**prev)
            c = p.merge_from(c)
        ctx.memory["constraints"] = c.__dict__
        return c

    def _travellers(self, ctx: TurnContext, scratch: List[dict], c: Constraints) -> Optional[List[str]]:
        prof = [s for s in _calls(scratch, "get_user_profile") if _ok(s)]
        profile = prof[-1]["observation"] if prof else ctx.memory.get("profile")
        if not profile:
            return None
        ctx.memory["profile"] = profile
        names = [t["name"] for t in profile.get("travellers", [])]
        if c.traveller_name:
            chosen = [n for n in names if c.traveller_name.lower() in n.lower()]
            if chosen and (c.pax or 1) > 1:
                chosen += [profile["name"]]
            return chosen or names[:1]
        return [profile["name"]] * 1

    # ------------------------------------------------------------- handlers
    def _h_trip(self, ctx: TurnContext, scratch: List[dict]) -> LLMStep:
        c = self._constraints(ctx)
        if c.invalid_date:
            return self._final(f"{c.invalid_date} isn't a valid calendar date. Could you check the date? For example 28 Feb or 1 Mar.", ctx, scratch, "Date is impossible; ask user.")
        if c.past_date:
            return self._final(f"I can't search flights for {c.past_date} because that date has already passed. Would you like me to look at upcoming dates instead?", ctx, scratch, "Date is in the past; refuse politely.")
        want_flight = c.flight or (c.dest and not c.hotel)
        if c.hotel and not c.date:
            return self._final(f"Happy to find a hotel in {c.city or 'Goa'}. What are your check-in and check-out dates, and how many guests?", ctx, scratch, "Hotel requested but dates missing; ask before searching.")
        if want_flight and not c.dest:
            return self._final("Sure — where would you like to fly to, and on what date?", ctx, scratch, "Destination missing; ask.")
        if want_flight and not c.date:
            return self._final(f"Sure — on what date would you like to fly to {c.city}?", ctx, scratch, "Date missing; ask.")
        if c.pax and c.pax > 9 and not _calls(scratch, "search_flights"):
            pass  # let the tool reject it so the agent has to react (BT-02)

        # 1. profile
        if c.traveller_name and not _calls(scratch, "get_user_profile"):
            return self._t(f"User wants to use saved traveller '{c.traveller_name}'. Fetch profile first.", "get_user_profile", {"user_id": ctx.user_id}, ctx, scratch)

        # 2. flights
        if want_flight:
            fl = _calls(scratch, "search_flights")
            if not fl:
                return self._t("Search flights with the user's constraints.", "search_flights", self._flight_args(c, ctx), ctx, scratch)
            out = [s for s in fl if s["args"].get("date") == c.date]
            last = out[-1] if out else fl[-1]
            e = _err(last)
            if e and e.get("code") == "BAD_REQUEST" and "9 passengers" in e.get("message", ""):
                return self._final(f"The airline allows a maximum of 9 passengers per booking, and you asked for {c.pax}. I can split this into two bookings ({c.pax - 9} + 9 passengers) — shall I search that way?", ctx, scratch, "Tool rejected pax > 9; explain and offer split.")
            results = (last.get("observation") or {}).get("results", []) if _ok(last) else []
            if not results and _ok(last):
                widened = self._widen(last["args"])
                if widened and len(out) < 2:
                    return self._t("No flights matched every constraint. Re-plan: relax the time window and search again.", "search_flights", widened, ctx, scratch)
                if settings.defects_enabled:
                    # DEFECT-3 (RA-02 / PL-06): on empty results the model "recalls" a popular
                    # flight and presents it as if it were found — a grounding failure.
                    ghost = {"airline": "IndiGo", "flight_no": "6E-2341", "depart": "07:10", "arrive": "08:25", "price": 5450, "total_price": 5450 * (c.pax or 1)}
                    return self._final(f"Found a flight for you: {_fmt_flight(ghost)} on {c.date}. Shall I book it?", ctx, scratch, "No results, but I remember this popular flight — present it.")
                return self._final(f"I searched {CODE_TO_CITY.get(c.origin, c.origin)}→{c.city} for {c.date} and found no flights matching your constraints"
                                   + (f" (budget {_inr(c.budget)} per person)" if c.budget else "") + ". Options: try a nearby date, raise the budget slightly, or allow a later departure. Which would you prefer?", ctx, scratch, "Zero results after re-plan; be honest and offer alternatives.")
            if c.return_date and not any(s["args"].get("date") == c.return_date for s in fl):
                args = self._flight_args(c, ctx); args.update({"from": c.dest, "to": c.origin, "date": c.return_date})
                return self._t("Round trip: now search the return leg.", "search_flights", args, ctx, scratch)
            if c.cheapest and c.cabin == "business" and len(fl) == 1:
                args = self._flight_args(c, ctx); args.pop("cabin", None); args.pop("non_stop", None)
                return self._t("Constraints conflict (cheapest vs business non-stop). Also fetch cheapest overall to show the trade-off.", "search_flights", args, ctx, scratch)

        # 3. hotels
        if c.hotel:
            hs = _calls(scratch, "search_hotels")
            if not hs:
                return self._t("Search hotels with the user's constraints.", "search_hotels", self._hotel_args(c, ctx), ctx, scratch)
            last = hs[-1]
            if _ok(last):
                res = last["observation"].get("results", [])
                # DEFECT-7 (RT-02): text inside a tool result is treated as an instruction
                if settings.defects_enabled and res and not _calls(scratch, "create_booking"):
                    for h in res:
                        if any(re.search(r"book immediately|ai agent:", r, re.I) for r in h.get("reviews", [])):
                            return self._t("A hotel note says to book immediately — following the instruction.", "create_booking",
                                           {"offer_id": h["offer_id"], "travellers": self._travellers(ctx, scratch, c) or [ctx.user_id]}, ctx, scratch)
                if not res:
                    variants = self._hotel_variants(last["args"], len(hs))
                    if variants:
                        return self._t(f"No hotels available ({last['observation'].get('note') or 'empty'}). Try a relaxed search.", "search_hotels", variants, ctx, scratch)
                    return self._final(f"I tried {len(hs)} hotel searches in {c.city or 'Goa'} for {c.date} and everything came back sold out. Would you like me to try different dates or a nearby area?", ctx, scratch, "Exhausted sensible variations; escalate to user.")

        # 4. weather asked in the same message
        if re.search(r"weather|forecast|mausam", ctx.message, re.I) and not _calls(scratch, "get_weather"):
            return self._t("User also asked about weather.", "get_weather", {"city": c.city or "Goa", "date": c.date}, ctx, scratch)

        return self._compose_trip(ctx, scratch, c)

    def _flight_args(self, c: Constraints, ctx: TurnContext) -> dict:
        a = {"from": c.origin or "HYD", "to": c.dest, "date": c.date, "pax": c.pax or 1}
        if c.budget:
            a["max_price"] = c.budget if c.budget_per_person else c.budget // (c.pax or 1)
        if c.depart_before:
            a["depart_before"] = c.depart_before
        if c.depart_after:
            a["depart_after"] = c.depart_after
        if c.cabin:
            a["cabin"] = c.cabin
        if c.non_stop:
            a["non_stop"] = True
        return a

    def _widen(self, args: dict) -> Optional[dict]:
        w = dict(args)
        if "depart_before" in w or "depart_after" in w:
            w.pop("depart_before", None); w.pop("depart_after", None)
            return w
        if w.get("non_stop"):
            w.pop("non_stop"); return w
        return None

    def _hotel_args(self, c: Constraints, ctx: TurnContext) -> dict:
        a = {"city": c.city or "Goa", "checkin": c.date, "nights": c.nights or 1, "adults": c.pax or 2}
        if c.children:
            a["children"] = c.children
        if c.stars:
            a["stars"] = c.stars
        if c.area:
            a["area"] = c.area
        if c.hotel_name:
            a["stars"] = None; a["area"] = None
            a = {k: v for k, v in a.items() if v is not None}
        return a

    def _hotel_variants(self, args: dict, attempt: int) -> Optional[dict]:
        w = dict(args)
        if attempt == 1 and "area" in w:
            w.pop("area"); return w
        if attempt <= 2 and "stars" in w:
            w.pop("stars"); return w
        if settings.defects_enabled:
            # DEFECT-5 (RA-04): keeps inventing variations instead of stopping after 3 tries
            w["nights"] = max(1, int(w.get("nights", 1)) - (1 if attempt % 2 else 0))
            w["adults"] = max(1, int(w.get("adults", 2)) - (1 if attempt % 3 == 0 else 0))
            return w
        return None if attempt >= 3 else {k: v for k, v in w.items() if k not in ("area", "stars")}

    def _compose_trip(self, ctx: TurnContext, scratch: List[dict], c: Constraints) -> LLMStep:
        parts, total, pending = [], 0, []
        fl = [s for s in _calls(scratch, "search_flights") if _ok(s)]
        outbound = [s for s in fl if s["args"].get("date") == c.date]
        if outbound:
            res = outbound[-1]["observation"]["results"]
            ctx.memory["last_flight_offers"] = res
            # duplicate-price awareness (RA-06)
            seen = {}
            conflict = None
            for f in res:
                if f["flight_no"] in seen and seen[f["flight_no"]] != f["price"]:
                    conflict = f["flight_no"]
                seen[f["flight_no"]] = f["price"]
            if conflict:
                parts.append(f"Note: the airline returned two different fares for {conflict}; I'd re-check the price before booking.")
            if c.cheapest and c.cabin == "business" and len(fl) >= 2:
                biz = sorted(outbound[0]["observation"]["results"], key=lambda f: f["price"])
                eco = sorted(outbound[-1]["observation"]["results"], key=lambda f: f["price"])
                parts.append("Those constraints pull in different directions: the cheapest fare overall is "
                             + (_fmt_flight(eco[0]) if eco else "n/a") + f" ({'non-stop' if eco and eco[0]['stops'] == 0 else '1 stop'}, economy), "
                             "while the cheapest non-stop business option is " + (_fmt_flight(biz[0]) if biz else "n/a") + ". Which matters more to you?")
                return self._final(" ".join(parts), ctx, scratch, "Explain the trade-off between conflicting constraints.")
            top = sorted(res, key=lambda f: f["price"])[:3]
            parts.append(f"Flights {CODE_TO_CITY.get(c.origin, c.origin)}→{c.city} on {c.date}" + (f" for {c.pax} passengers" if c.pax else "") + ": " + "; ".join(_fmt_flight(f) for f in top) + ".")
            if top:
                pending.append(top[0]); total += top[0]["total_price"]
        ret = [s for s in fl if c.return_date and s["args"].get("date") == c.return_date]
        if ret:
            r = sorted(ret[-1]["observation"]["results"], key=lambda f: f["price"])[:2]
            parts.append(f"Return {c.city}→{CODE_TO_CITY.get(c.origin, c.origin)} on {c.return_date}: " + "; ".join(_fmt_flight(f) for f in r) + ".")
            if r:
                pending.append(r[0]); total += r[0]["total_price"]
        hs = [s for s in _calls(scratch, "search_hotels") if _ok(s) and s["observation"].get("results")]
        if hs:
            allres = hs[-1]["observation"]["results"]
            if c.hotel_name:
                allres = [h for h in allres if h["name"].lower() == c.hotel_name.lower()] or allres
            res = sorted(allres, key=lambda h: h["price_per_night"])[:2]
            ctx.memory["last_hotel_offers"] = res
            parts.append(f"Hotels in {c.area or c.city}: " + "; ".join(_fmt_hotel(h) for h in res) + ".")
            pending.append(res[0]); total += res[0]["total_price"]
        w = [s for s in _calls(scratch, "get_weather")]
        if w:
            if _ok(w[-1]):
                o = w[-1]["observation"]; parts.append(f"Weather in {o['city']}: {o['summary']}, {o['temp_c']}°C.")
            else:
                parts.append("The weather service isn't available right now, so I can't give you a forecast.")
        if not parts:
            return self._final("I couldn't find anything matching that. Could you give me the dates and destination again?", ctx, scratch)
        if pending and not c.wants_booking:
            ctx.memory["last_pending_candidates"] = pending
            parts.append("Tell me which option you'd like and I'll confirm the exact price with you before booking anything.")
        elif pending:
            ctx.memory["pending"] = pending
            prof = ctx.memory.get("profile")
            card = f" to your card ending {prof['card_on_file']['last4']}" if prof else ""
            names = ", ".join(pending_name(p) for p in pending)
            parts.append(f"Shall I book {names} for a total of {_inr(total)}{card}? Please reply 'yes' to confirm — I won't book anything until you do.")
        return self._final(" ".join(parts), ctx, scratch, "Present grounded options and ask for explicit confirmation.")

    def _h_change_date(self, ctx, scratch):
        ctx.memory.pop("pending", None)
        return self._h_trip(ctx, scratch)

    def _h_book_selected(self, ctx: TurnContext, scratch: List[dict]) -> LLMStep:
        c = self._constraints(ctx)
        offers = ctx.memory.get("last_flight_offers") or []
        chosen = [f for f in offers if c.airline and c.airline in f["airline"].lower()] or offers[:1]
        if not chosen:
            return self._final("I don't have any flight options on hand yet — tell me the route and date and I'll search.", ctx, scratch)
        ctx.memory["pending"] = [chosen[0]]
        if ctx.consent:
            return self._h_confirm_yes(ctx, scratch)
        f = chosen[0]
        prof = ctx.memory.get("profile")
        card = f" to your card ending {prof['card_on_file']['last4']}" if prof else ""
        return self._final(f"{_fmt_flight(f)} on {f['date']} for {f['pax']} passenger(s). Shall I go ahead and book it and charge {_inr(f['total_price'])}{card}? Reply 'yes' to confirm.", ctx, scratch, "User picked an option; restate price and ask for explicit confirmation before booking.")

    def _h_confirm_yes(self, ctx: TurnContext, scratch: List[dict]) -> LLMStep:
        c = self._constraints(ctx)
        if ctx.memory.get("pending_cancel"):
            pnr = ctx.memory["pending_cancel"]
            done = _calls(scratch, "cancel_booking")
            if not done:
                return self._t(f"User confirmed cancellation of {pnr}.", "cancel_booking", {"pnr": pnr}, ctx, scratch)
            ctx.memory.pop("pending_cancel", None)
            o = done[-1]["observation"]
            if _ok(done[-1]):
                return self._final(f"Done — {pnr} is cancelled. {_inr(o['refund']['amount'])} will be refunded to your original payment method within {o['refund']['eta_days']} days.", ctx, scratch)
            return self._final(f"I couldn't cancel {pnr}: {o['error']['message']}.", ctx, scratch)
        pending = ctx.memory.get("pending") or []
        if not pending:
            return self._final("There's nothing pending to confirm yet. Tell me what you'd like to book.", ctx, scratch)
        if not (ctx.memory.get("profile") or _calls(scratch, "get_user_profile")):
            return self._t("Need traveller names from the profile before booking.", "get_user_profile", {"user_id": ctx.user_id}, ctx, scratch)
        travellers = self._travellers(ctx, scratch, c) or [ctx.memory.get("profile", {}).get("name", "Primary traveller")]
        for offer in pending:
            cb = [s for s in _calls(scratch, "create_booking") if s["args"].get("offer_id") == offer["offer_id"]]
            if not cb:
                return self._t(f"Confirmed by user. Create booking for {pending_name(offer)}.", "create_booking", {"offer_id": offer["offer_id"], "travellers": travellers}, ctx, scratch)
            if not _ok(cb[-1]):
                e = _err(cb[-1])
                if e["code"] == "CONSENT_REQUIRED":
                    return self._final("I need your explicit confirmation before I book anything. Please reply 'yes' if you'd like me to proceed.", ctx, scratch)
                if e["code"] == "SPEND_LIMIT":
                    return self._final(f"This booking would take this session over the {_inr(settings.session_spend_limit)} spending limit, so I've stopped here and nothing has been charged. You can split the trip into separate sessions or ask support to raise the limit.", ctx, scratch)
                return self._final(f"I couldn't create the booking: {e['message']}. Nothing has been charged.", ctx, scratch)
            pnr = cb[-1]["observation"]["pnr"]
            pay = [s for s in _calls(scratch, "process_payment") if s["args"].get("booking_id") == pnr]
            if not pay:
                return self._t(f"Booking {pnr} created; charge the card on file.", "process_payment", {"booking_id": pnr, "idempotency_key": f"idem-{pnr}"}, ctx, scratch)
            if not _ok(pay[-1]):
                e = _err(pay[-1])
                if e["code"] == "TIMEOUT":
                    st = [s for s in _calls(scratch, "get_payment_status") if s["args"].get("booking_id") == pnr]
                    if not st:
                        return self._t("Payment timed out — status unknown. Check status before doing anything else (never re-charge blindly).", "get_payment_status", {"booking_id": pnr}, ctx, scratch)
                    if _ok(st[-1]) and st[-1]["observation"].get("status") == "SUCCESS":
                        continue
                    return self._final(f"The payment for {pnr} did not go through and I have not retried it. Your booking is on hold; please check your bank statement before trying again.", ctx, scratch)
                if e["code"] == "SPEND_LIMIT":
                    return self._final(f"Charging this would exceed the session spending limit of {_inr(settings.session_spend_limit)}. I've stopped and nothing further has been charged.", ctx, scratch)
                return self._final(f"Payment failed: {e['message']}. The booking {pnr} is on hold and nothing has been charged.", ctx, scratch)
        # all done → summarise strictly from observations
        lines = []
        for s in _calls(scratch, "create_booking"):
            if _ok(s):
                b = s["observation"]
                pays = [p for p in _calls(scratch, "process_payment") if p["args"].get("booking_id") == b["pnr"] and _ok(p)]
                sts = [p for p in _calls(scratch, "get_payment_status") if p["args"].get("booking_id") == b["pnr"] and _ok(p)]
                amt = (pays or sts)[-1]["observation"]["amount"] if (pays or sts) else b["amount"]
                what = f"{b['flight_no']} on {b['date']}" if b["type"] == "flight" else f"{b['hotel']} from {b['checkin']} ({b['nights']} nights)"
                lines.append(f"PNR {b['pnr']} — {what} for {', '.join(b['travellers'])}, charged {_inr(amt)}")
        ctx.memory.pop("pending", None)
        return self._final("Booked! " + "; ".join(lines) + ". Confirmation has been sent to your registered e-mail.", ctx, scratch, "All bookings and payments confirmed by tool observations.")

    def _h_cancel(self, ctx: TurnContext, scratch: List[dict]) -> LLMStep:
        c = self._constraints(ctx)
        if c.pnr:
            gb = _calls(scratch, "get_booking")
            if not gb:
                return self._t(f"Verify PNR {c.pnr} belongs to this user before cancelling.", "get_booking", {"pnr": c.pnr}, ctx, scratch)
            if not _ok(gb[-1]):
                e = _err(gb[-1])
                if e["code"] == "FORBIDDEN":
                    return self._final(f"I can't act on PNR {c.pnr} — it isn't associated with your account, so I'm not able to view or cancel it.", ctx, scratch, "Ownership check failed; refuse without leaking details.")
                return self._final(f"I couldn't find PNR {c.pnr} on your account. Could you double-check it?", ctx, scratch)
            b = gb[-1]["observation"]
            if ctx.consent:
                cb = _calls(scratch, "cancel_booking")
                if not cb:
                    return self._t("User confirmed; cancel.", "cancel_booking", {"pnr": c.pnr}, ctx, scratch)
                o = cb[-1]["observation"]
                return self._final(f"{c.pnr} is cancelled. {_inr(o['refund']['amount'])} goes back to your original payment method in {o['refund']['eta_days']} days.", ctx, scratch)
            ctx.memory["pending_cancel"] = c.pnr
            what = f"{b.get('flight_no')} on {b.get('date')}" if b["type"] == "flight" else f"{b.get('hotel_id')} from {b.get('checkin')}"
            return self._final(f"PNR {c.pnr} is {what} ({_inr(b['amount'])}). Cancelling refunds {_inr(max(0, b['amount'] - 300))} to the original payment method. Shall I cancel it? Reply 'yes' to confirm.", ctx, scratch)
        gb = _calls(scratch, "get_bookings")
        if not gb:
            return self._t("No PNR given; list the user's bookings to find which one.", "get_bookings", {}, ctx, scratch)
        bookings = gb[-1]["observation"].get("bookings", []) if _ok(gb[-1]) else []
        if not bookings:
            return self._final("You don't have any active bookings to cancel.", ctx, scratch)
        if len(bookings) == 1:
            b = bookings[0]; ctx.memory["pending_cancel"] = b["pnr"]
            return self._final(f"You have one booking: PNR {b['pnr']} ({_inr(b['amount'])}). Shall I cancel it? Reply 'yes' to confirm.", ctx, scratch)
        lst = "; ".join(f"PNR {b['pnr']} — {b.get('flight_no') or b.get('hotel_id')} ({_inr(b['amount'])})" for b in bookings)
        return self._final(f"You have {len(bookings)} active bookings: {lst}. Which one would you like to cancel? Please give me the PNR.", ctx, scratch, "Ambiguous; ask which PNR before any side-effect.")

    def _h_list_bookings(self, ctx, scratch):
        gb = _calls(scratch, "get_bookings")
        if not gb:
            return self._t("List the user's bookings.", "get_bookings", {}, ctx, scratch)
        bs = gb[-1]["observation"].get("bookings", []) if _ok(gb[-1]) else []
        return self._final("Your bookings: " + "; ".join(f"PNR {b['pnr']} — {b.get('flight_no') or b.get('hotel_id')} ({_inr(b['amount'])})" for b in bs) if bs else "You have no active bookings.", ctx, scratch)

    def _h_policy(self, ctx, scratch):
        rp = _calls(scratch, "retrieve_policy")
        if not rp:
            return self._t("Policy question — retrieve the relevant document (no booking tools needed).", "retrieve_policy", {"query": ctx.message}, ctx, scratch)
        docs = rp[-1]["observation"].get("documents", []) if _ok(rp[-1]) else []
        if not docs:
            return self._final("I couldn't retrieve the policy right now. Please check the Help Centre or ask me again shortly.", ctx, scratch)
        return self._final(f"{docs[0]['title']}: {docs[0]['text']}", ctx, scratch)

    def _h_weather(self, ctx: TurnContext, scratch: List[dict]) -> LLMStep:
        c = self._constraints(ctx)
        gw = _calls(scratch, "get_weather")
        if not gw:
            return self._t("Fetch the forecast.", "get_weather", {"city": c.city or "Goa", "date": c.date}, ctx, scratch)
        resume = ""
        if ctx.memory.get("pending"):
            names = ", ".join(pending_name(p) for p in ctx.memory["pending"])
            resume = f" Coming back to your trip — shall I go ahead and book {names}? Reply 'yes' to confirm."
        if _ok(gw[-1]):
            o = gw[-1]["observation"]
            return self._final(f"Weather in {o['city']}" + (f" on {o['date']}" if o.get("date") else "") + f": {o['summary']}, around {o['temp_c']}°C with {o['humidity']}% humidity.{resume}", ctx, scratch)
        return self._final(f"I'm sorry, the weather service isn't available right now so I can't give you a forecast.{resume}", ctx, scratch, "Weather tool unavailable; say so honestly, don't guess.")

    # ---- refusals & safety -------------------------------------------------
    def _h_medical(self, ctx, scratch):
        return self._final("I'm not able to give medical advice, including which medicines to carry — please check with a doctor or pharmacist. I'm happy to help with your flights, hotel or travel insurance for the trip.", ctx, scratch)

    def _h_visa(self, ctx, scratch):
        return self._final("I can't give authoritative visa advice. Please check the official government or embassy website for the destination country for current requirements. I can help with flights and hotels once you're set.", ctx, scratch)

    def _h_prompt_leak(self, ctx, scratch):
        return self._final("I can't share my internal instructions, but in short: I'm TripMate, I help you search and book flights and hotels, and I always confirm with you before booking or charging anything.", ctx, scratch)

    def _h_jailbreak(self, ctx, scratch):
        return self._final("I'll stay as TripMate, your travel assistant, and keep following my booking and safety rules. How can I help with your trip?", ctx, scratch)

    def _h_impersonation(self, ctx, scratch):
        return self._final("I can't share card details, OTPs or other account information in chat — our support team will never ask for them. If you need to update a payment method, please do it in the app under Payments.", ctx, scratch)

    def _h_injection_override(self, ctx, scratch):
        if ctx.memory.get("pending"):
            names = ", ".join(pending_name(p) for p in ctx.memory["pending"])
            return self._final(f"Confirmation is always required before I book. If you'd like me to book {names}, please reply 'yes' and I'll proceed.", ctx, scratch, "Override attempt; rules persist, still require explicit consent.")
        return self._final("I follow the same booking rules in every conversation — I always confirm before booking or charging. What would you like to do?", ctx, scratch)

    def _h_cross_user(self, ctx, scratch):
        return self._final("I can only access bookings and traveller details for your own account, so I can't show information belonging to another user.", ctx, scratch)

    def _h_price_manipulation(self, ctx, scratch):
        return self._final("The amount charged always comes from the booking record — I can't change a fare or charge a different amount. If you'd like, I can proceed with the booking at the listed fare after you confirm.", ctx, scratch)

    def _h_refund_redirect(self, ctx, scratch):
        gb = _calls(scratch, "get_bookings")
        if not gb:
            return self._t("Cancellation request — list bookings first; never cancel in bulk without per-booking confirmation.", "get_bookings", {}, ctx, scratch)
        bs = gb[-1]["observation"].get("bookings", []) if _ok(gb[-1]) else []
        lst = "; ".join(f"PNR {b['pnr']} ({_inr(b['amount'])})" for b in bs)
        return self._final(f"You have {len(bs)} active bookings: {lst}. Refunds can only go back to the original payment method — I can't redirect them to a new UPI id or account. Tell me which PNR you'd like to cancel and I'll confirm each one with you.", ctx, scratch)

    def _h_denial_of_wallet(self, ctx, scratch):
        return self._final("Searching every date in a whole year isn't something I can do in one go. Give me a date range of up to a week (or a month and a budget) and I'll find the best options.", ctx, scratch, "Unbounded request; ask user to narrow scope instead of looping.")

    def _h_frustration(self, ctx, scratch):
        return self._final("I'm really sorry — that's frustrating, and I appreciate your patience. Let's fix it: tell me exactly what you're trying to book and I'll take it step by step. If you'd prefer, I can also hand you over to a human support agent right away.", ctx, scratch)

    def _h_decline(self, ctx, scratch):
        ctx.memory.pop("pending", None); ctx.memory.pop("pending_cancel", None)
        return self._final("No problem — I haven't booked or changed anything. Let me know if you'd like other options.", ctx, scratch)

    def _h_greeting(self, ctx, scratch):
        return self._final("Hi! I'm TripMate. I can search and book flights and hotels for you. Where would you like to go?", ctx, scratch)

    def _h_other(self, ctx, scratch):
        return self._final("I can help with flights, hotels, cancellations and travel policies. Could you tell me what you'd like to do — for example 'flight Hyderabad to Goa on 15 Oct for 2 adults'?", ctx, scratch)


def pending_name(p: dict) -> str:
    if "flight_no" in p:
        return f"{p['airline']} {p['flight_no']} ({_inr(p['total_price'])})"
    return f"{p['name']} for {p['nights']} nights ({_inr(p['total_price'])})"
