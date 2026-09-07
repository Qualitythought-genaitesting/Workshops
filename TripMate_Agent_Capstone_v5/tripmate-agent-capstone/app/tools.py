"""Tool implementations for TripMate.

Every tool receives (args: dict, ctx: ToolContext) and returns a JSON-serialisable
dict. Failures raise ToolError (which the agent observes and reasons about).
Side-effect tools are flagged so the guardrail layer can gate them.
"""
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List

from .data import store, CODE_TO_CITY, WEATHER, POLICIES


class ToolError(Exception):
    def __init__(self, code: str, message: str, http_status: int = 500):
        super().__init__(message)
        self.code, self.message, self.http_status = code, message, http_status


@dataclass
class ToolContext:
    user_id: str
    session_id: str
    trace_id: str
    consent_given: bool = False


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: Dict[str, Any]
    side_effect: bool
    fn: Callable[[dict, ToolContext], dict]


def _maybe_fail(tool: str):
    mode = store.mock.mode(tool)
    if mode == "error_503":
        raise ToolError("UPSTREAM_UNAVAILABLE", f"{tool} upstream returned HTTP 503", 503)
    if mode == "timeout":
        raise ToolError("TIMEOUT", f"{tool} timed out after 8000 ms", 504)
    if mode == "malformed":
        raise ToolError("MALFORMED_RESPONSE", f"{tool} returned non-JSON payload: '<html>502 Bad Gateway</html>'", 502)
    return mode


# ----------------------------------------------------------------------------
# Read-only tools
# ----------------------------------------------------------------------------

def get_user_profile(args, ctx):
    _maybe_fail("get_user_profile")
    uid = args.get("user_id") or ctx.user_id
    if uid != ctx.user_id:
        raise ToolError("FORBIDDEN", "You may only access the current user's profile", 403)
    u = store.users.get(uid)
    if not u:
        raise ToolError("NOT_FOUND", f"user {uid} not found", 404)
    # never expose the card token or number to the model
    return {"user_id": u["user_id"], "name": u["name"], "travellers": u["travellers"],
            "card_on_file": {"brand": u["card_on_file"]["brand"], "last4": u["card_on_file"]["last4"]}}


def search_flights(args, ctx):
    mode = _maybe_fail("search_flights")
    origin, dest, date = args.get("from"), args.get("to"), args.get("date")
    if not (origin and dest and date):
        raise ToolError("BAD_REQUEST", "from, to and date are required", 400)
    if mode == "empty":
        return {"results": [], "count": 0}
    pax = int(args.get("pax") or 1)
    if pax > 9:
        raise ToolError("BAD_REQUEST", "Maximum 9 passengers per booking", 400)
    flights = store.flights_for(origin, dest, date)
    cabin = (args.get("cabin") or "economy").lower()
    flights = [f for f in flights if f["cabin"] == cabin]
    if args.get("depart_before"):
        flights = [f for f in flights if f["depart"] < args["depart_before"]]
    if args.get("depart_after"):
        flights = [f for f in flights if f["depart"] > args["depart_after"]]
    if args.get("non_stop"):
        flights = [f for f in flights if f["stops"] == 0]
    if args.get("max_price") is not None:
        flights = [f for f in flights if f["price"] <= int(args["max_price"])]
    if mode == "dup_price" and flights:
        dup = dict(flights[0]); dup["price"] = flights[0]["price"] + 700
        flights = [flights[0], dup] + flights[1:]
    for f in flights:
        f["pax"] = pax
        f["total_price"] = f["price"] * pax
        store.offers[f["offer_id"]] = f
    return {"results": flights, "count": len(flights)}


def search_hotels(args, ctx):
    mode = _maybe_fail("search_hotels")
    city = (args.get("city") or "").strip().title()
    if not city or not args.get("checkin"):
        raise ToolError("BAD_REQUEST", "city and checkin are required", 400)
    if mode in ("empty", "sold_out"):
        return {"results": [], "count": 0, "note": "sold out" if mode == "sold_out" else None}
    nights = int(args.get("nights") or 1)
    adults = int(args.get("adults") or args.get("guests") or 2)
    children = args.get("children") or []
    out = []
    for h in store.hotels:
        if h["city"] != city:
            continue
        if args.get("area") and h["area"].lower() != str(args["area"]).lower():
            continue
        if args.get("stars") and h["stars"] != int(args["stars"]):
            continue
        item = {k: v for k, v in h.items() if k != "reviews"}
        item.update({"checkin": args["checkin"], "nights": nights, "adults": adults, "children": children,
                     "total_price": h["price_per_night"] * nights,
                     "reviews": h["reviews"] + store.mock.injected_reviews,
                     "offer_id": f"H-{h['hotel_id']}-{args['checkin']}-{nights}"})
        store.offers[item["offer_id"]] = item
        out.append(item)
    return {"results": out, "count": len(out)}


def get_weather(args, ctx):
    _maybe_fail("get_weather")
    if not store.mock.weather_enabled:
        raise ToolError("TOOL_DISABLED", "get_weather is not available", 503)
    city = (args.get("city") or "").title()
    w = WEATHER.get(city)
    if not w:
        raise ToolError("NOT_FOUND", f"no forecast for {city}", 404)
    return {"city": city, "date": args.get("date"), **w}


def retrieve_policy(args, ctx):
    _maybe_fail("retrieve_policy")
    q = (args.get("query") or "").lower()
    scored = []
    for p in POLICIES:
        score = sum(1 for w in q.split() if w in (p["title"] + " " + p["text"]).lower())
        scored.append((score, p))
    scored.sort(key=lambda x: -x[0])
    return {"documents": [p for s, p in scored[:2]]}


def get_bookings(args, ctx):
    _maybe_fail("get_bookings")
    uid = args.get("user_id") or ctx.user_id
    if uid != ctx.user_id:
        raise ToolError("FORBIDDEN", "You may only list the current user's bookings", 403)
    return {"bookings": [b for b in store.bookings.values() if b["user_id"] == uid and b["status"] == "CONFIRMED"]}


def get_booking(args, ctx):
    _maybe_fail("get_booking")
    pnr = (args.get("pnr") or "").upper()
    b = store.bookings.get(pnr)
    if not b:
        raise ToolError("NOT_FOUND", f"PNR {pnr} not found", 404)
    if b["user_id"] != ctx.user_id:
        raise ToolError("FORBIDDEN", "PNR does not belong to the current user", 403)
    return b


def get_payment_status(args, ctx):
    _maybe_fail("get_payment_status")
    p = store.payments.get(args.get("payment_id", ""))
    if not p:
        # look up by booking id
        for pay in store.payments.values():
            if pay["booking_id"] == args.get("booking_id"):
                return pay
        raise ToolError("NOT_FOUND", "payment not found", 404)
    return p


# ----------------------------------------------------------------------------
# Side-effect tools
# ----------------------------------------------------------------------------

def create_booking(args, ctx):
    _maybe_fail("create_booking")
    offer = store.offers.get(args.get("offer_id", ""))
    if not offer:
        raise ToolError("NOT_FOUND", f"offer {args.get('offer_id')} not found or expired", 404)
    travellers = args.get("travellers") or []
    if not travellers:
        raise ToolError("BAD_REQUEST", "travellers are required", 400)
    pnr = store.new_pnr()
    booking = {"pnr": pnr, "user_id": ctx.user_id, "type": "flight" if "flight_no" in offer else "hotel",
               "travellers": travellers, "amount": offer["total_price"], "status": "PENDING_PAYMENT",
               "payment_method": store.users[ctx.user_id]["card_on_file"]["token"], "offer_id": offer["offer_id"]}
    if booking["type"] == "flight":
        booking.update({"flight_no": offer["flight_no"], "date": offer["date"], "from": offer["from"], "to": offer["to"]})
    else:
        booking.update({"hotel_id": offer["hotel_id"], "hotel": offer["name"], "checkin": offer["checkin"], "nights": offer["nights"]})
    store.bookings[pnr] = booking
    return booking


def process_payment(args, ctx):
    mode = _maybe_fail("process_payment")
    booking = store.bookings.get(args.get("booking_id") or args.get("pnr") or "")
    if not booking:
        raise ToolError("NOT_FOUND", "booking not found", 404)
    if booking["user_id"] != ctx.user_id:
        raise ToolError("FORBIDDEN", "booking does not belong to current user", 403)
    # SECURITY: amount is always taken from the booking record, never from arguments
    amount = booking["amount"]
    idem = args.get("idempotency_key") or f"idem-{booking['pnr']}"
    for p in store.payments.values():
        if p["idempotency_key"] == idem and p["status"] == "SUCCESS":
            return {**p, "note": "idempotent replay — no new charge"}
    pid = store.new_payment_id()
    rec = {"payment_id": pid, "booking_id": booking["pnr"], "amount": amount, "currency": "INR", "status": "SUCCESS",
           "method": booking["payment_method"], "idempotency_key": idem, "ts": time.time()}
    store.payments[pid] = rec
    booking["status"] = "CONFIRMED"
    store.session_spend[ctx.session_id] = store.session_spend.get(ctx.session_id, 0) + amount
    if mode == "payment_timeout_after_debit":
        # money moved, but the response is lost
        raise ToolError("TIMEOUT", "process_payment timed out after 8000 ms (status unknown)", 504)
    return rec


def cancel_booking(args, ctx):
    _maybe_fail("cancel_booking")
    pnr = (args.get("pnr") or "").upper()
    b = store.bookings.get(pnr)
    if not b:
        raise ToolError("NOT_FOUND", f"PNR {pnr} not found", 404)
    if b["user_id"] != ctx.user_id:
        raise ToolError("FORBIDDEN", "PNR does not belong to the current user", 403)
    if b["status"] == "CANCELLED":
        raise ToolError("CONFLICT", f"PNR {pnr} is already cancelled", 409)
    b["status"] = "CANCELLED"
    refund = {"refund_to": "original_payment_method", "method": b["payment_method"], "amount": max(0, b["amount"] - 300), "eta_days": "5-7"}
    return {"pnr": pnr, "status": "CANCELLED", "refund": refund}


# ----------------------------------------------------------------------------
# Registry
# ----------------------------------------------------------------------------

TOOLS: Dict[str, ToolSpec] = {}


def _reg(name, desc, params, side_effect, fn):
    TOOLS[name] = ToolSpec(name, desc, {"type": "object", "properties": params.get("properties", {}), "required": params.get("required", [])}, side_effect, fn)


_reg("get_user_profile", "Get the current user's profile and saved travellers.",
     {"properties": {"user_id": {"type": "string"}}, "required": []}, False, get_user_profile)
_reg("search_flights", "Search flights. Dates are ISO (YYYY-MM-DD). Prices in INR per person.",
     {"properties": {"from": {"type": "string"}, "to": {"type": "string"}, "date": {"type": "string"}, "pax": {"type": "integer"},
                     "depart_before": {"type": "string"}, "depart_after": {"type": "string"}, "max_price": {"type": "integer"},
                     "cabin": {"type": "string"}, "non_stop": {"type": "boolean"}}, "required": ["from", "to", "date"]}, False, search_flights)
_reg("search_hotels", "Search hotels in a city.",
     {"properties": {"city": {"type": "string"}, "area": {"type": "string"}, "checkin": {"type": "string"}, "nights": {"type": "integer"},
                     "stars": {"type": "integer"}, "adults": {"type": "integer"}, "children": {"type": "array", "items": {"type": "integer"}}},
      "required": ["city", "checkin"]}, False, search_hotels)
_reg("get_weather", "Weather forecast for a city.", {"properties": {"city": {"type": "string"}, "date": {"type": "string"}}, "required": ["city"]}, False, get_weather)
_reg("retrieve_policy", "Retrieve refund/baggage/change policy documents.", {"properties": {"query": {"type": "string"}}, "required": ["query"]}, False, retrieve_policy)
_reg("get_bookings", "List the current user's confirmed bookings.", {"properties": {}, "required": []}, False, get_bookings)
_reg("get_booking", "Get one booking by PNR (must belong to the user).", {"properties": {"pnr": {"type": "string"}}, "required": ["pnr"]}, False, get_booking)
_reg("get_payment_status", "Check a payment's status after a timeout.", {"properties": {"payment_id": {"type": "string"}, "booking_id": {"type": "string"}}, "required": []}, False, get_payment_status)
_reg("create_booking", "Create a booking from an offer_id. SIDE-EFFECT: requires explicit user confirmation.",
     {"properties": {"offer_id": {"type": "string"}, "travellers": {"type": "array", "items": {"type": "string"}}}, "required": ["offer_id", "travellers"]}, True, create_booking)
_reg("process_payment", "Charge the card on file for a booking. SIDE-EFFECT. Amount comes from the booking record.",
     {"properties": {"booking_id": {"type": "string"}, "idempotency_key": {"type": "string"}}, "required": ["booking_id"]}, True, process_payment)
_reg("cancel_booking", "Cancel a booking by PNR. SIDE-EFFECT: requires explicit confirmation. Refund goes to original method.",
     {"properties": {"pnr": {"type": "string"}}, "required": ["pnr"]}, True, cancel_booking)

SIDE_EFFECT_TOOLS: List[str] = [n for n, t in TOOLS.items() if t.side_effect]
