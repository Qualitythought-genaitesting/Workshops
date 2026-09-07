"""Multi-agent coordinator for TripMate.

Same guardrails as the single ReAct agent (input rules, consent gate, tool
allow-list and spend limit — all enforced through `app.exec_common.execute_tool`,
shared with `app/agent.py`), same tracing, but a different shape: one
lightweight router parses the message, works out which of five specialists
(flight, hotel, weather, day-planner, budget) are relevant, and dispatches the
independent, search-type ones CONCURRENTLY. A combined request like "flight +
hotel to Goa" comes back in one round trip instead of several ReAct
iterations — the point is to complete a booking quickly. The day-planner and
budget specialists run after the others because they read those results.

Purely additive: the classroom single-agent build, its 61 pytest scenarios and
7 planted defects are untouched. Reach this mode via POST /chat/multi (mirrors
POST /chat's request/response shape, plus an `agents` field).
"""
import threading
import time
import zlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from . import budget_agent, flight_agent, hotel_agent, planner_agent, weather_agent
from .base import SpecialistResult, dispatch_parallel
from .. import __version__, PROMPT_VERSION
from ..config import settings
from ..data import store
from ..guardrails import check_input, user_gave_consent
from ..llm.nlu import extract
from ..tracing import Trace

BLOCKING_CATEGORIES = {"prompt_injection", "prompt_leak", "jailbreak", "impersonation", "cross_user", "price_manipulation", "refund_redirect", "unbounded_scope"}


@dataclass
class MultiSession:
    session_id: str
    user_id: str
    history: List[Dict[str, str]] = field(default_factory=list)
    pending_flight_offer: Optional[str] = None
    pending_hotel_offer: Optional[str] = None
    last_city: Optional[str] = None
    last_nights: Optional[int] = None
    turns: int = 0


def _travellers(user_id: str, traveller_name: Optional[str]) -> List[str]:
    profile = store.users.get(user_id, {})
    names = [t["name"] for t in profile.get("travellers", [])]
    if traveller_name:
        chosen = [n for n in names if traveller_name.lower() in n.lower()]
        if chosen:
            return chosen
    return [profile.get("name", user_id)]


class MultiAgentCoordinator:
    def __init__(self):
        self.sessions: Dict[str, MultiSession] = {}
        self._lock = threading.Lock()

    def reset(self):
        with self._lock:
            self.sessions.clear()

    def _session(self, session_id: str, user_id: str) -> MultiSession:
        with self._lock:
            s = self.sessions.get(session_id)
            if not s or s.user_id != user_id:
                s = self.sessions[session_id] = MultiSession(session_id, user_id)
            return s

    def chat(self, session_id: str, user_id: str, message: str, provider: Optional[str] = None) -> Dict[str, Any]:
        sess = self._session(session_id, user_id)
        seed = zlib.crc32(f"multi:{session_id}:{sess.turns}:{message}".encode())
        trace = Trace(session_id, user_id, message)
        trace.metadata.update({"app_version": __version__, "prompt_version": PROMPT_VERSION, "defects_enabled": settings.defects_enabled,
                               "turn": sess.turns + 1, "mode": "multi_agent"})
        t0 = time.time()

        hits = check_input(message)
        for h in hits:
            trace.span("guardrail.input", "guardrail", {"rule_id": h.rule_id, "category": h.category, "snippet": h.snippet},
                       {"blocked": h.category in BLOCKING_CATEGORIES, "action": "refuse" if h.category in BLOCKING_CATEGORIES else "policy_answer"},
                       status="blocked" if h.category in BLOCKING_CATEGORIES else "flagged", rule_id=h.rule_id)
        blocking = [h for h in hits if h.category in BLOCKING_CATEGORIES]
        consent = user_gave_consent(message, seed)
        trace.span("guardrail.consent_gate", "guardrail", {"message": message}, {"consent": consent}, status="ok")

        if blocking:
            reply = "I can't help with that — it looks like it's trying to change my instructions or bypass a safety rule."
            sess.history += [{"role": "user", "content": message}, {"role": "assistant", "content": reply}]
            sess.turns += 1
            trace.finish(reply, 0, status="blocked")
            return {"reply": reply, "trace_id": trace.id, "agents": [], "agent_details": {},
                    "guardrail_hits": [h.rule_id for h in hits], "consent": consent,
                    "latency_ms": int((time.time() - t0) * 1000), "session_id": session_id, "user_id": user_id, "mode": "multi_agent"}

        c = extract(message)
        results: Dict[str, SpecialistResult] = {}
        agents_run: List[str] = []

        if consent and (sess.pending_flight_offer or sess.pending_hotel_offer):
            # ---- confirmation turn: book everything pending, in parallel ------
            travellers = _travellers(user_id, c.traveller_name)
            jobs = {}
            if sess.pending_flight_offer:
                offer = sess.pending_flight_offer
                jobs["flight"] = lambda offer=offer: flight_agent.confirm(offer, travellers, user_id=user_id, session_id=session_id, trace=trace, consent=consent)
            if sess.pending_hotel_offer:
                offer = sess.pending_hotel_offer
                jobs["hotel"] = lambda offer=offer: hotel_agent.confirm(offer, travellers, user_id=user_id, session_id=session_id, trace=trace, consent=consent)
            results = dispatch_parallel(jobs)
            agents_run = list(results.keys())
            if results.get("flight") and results["flight"].ok:
                sess.pending_flight_offer = None
            if results.get("hotel") and results["hotel"].ok:
                sess.pending_hotel_offer = None
            reply = " ".join(r.summary for r in results.values() if r.summary) or "Nothing pending to confirm."
        else:
            # ---- search/plan turn: dispatch the independent specialists together
            city = c.city or sess.last_city
            want_hotel = c.hotel or bool(c.nights)
            want_flight = bool(c.dest) and not (want_hotel and not c.flight and not c.wants_booking and not c.origin)
            want_weather = bool(city) and (want_flight or want_hotel or "weather" in message.lower() or "forecast" in message.lower())

            jobs = {}
            if want_flight:
                jobs["flight"] = lambda: flight_agent.search(c, user_id=user_id, session_id=session_id, trace=trace, consent=consent)
            if want_hotel:
                jobs["hotel"] = lambda: hotel_agent.search(c, city, user_id=user_id, session_id=session_id, trace=trace, consent=consent)
            if want_weather:
                jobs["weather"] = lambda: weather_agent.check(c, user_id=user_id, session_id=session_id, trace=trace, consent=consent)
            results = dispatch_parallel(jobs)
            agents_run = list(results.keys())

            want_planner = bool(city) and ("plan" in message.lower() or "itinerary" in message.lower() or ("flight" in jobs and "hotel" in jobs))
            if want_planner:
                results["planner"] = planner_agent.plan(city, c.nights or sess.last_nights, results.get("flight"), results.get("hotel"), results.get("weather"))
                agents_run.append("planner")

            proposed = {}
            if results.get("flight") and results["flight"].ok:
                proposed["flight"] = results["flight"].data.get("total_price")
            if results.get("hotel") and results["hotel"].ok:
                proposed["hotel"] = results["hotel"].data.get("total_price")
            if proposed:
                results["budget"] = budget_agent.check(session_id, proposed)
                agents_run.append("budget")

            if results.get("flight") and results["flight"].ok:
                sess.pending_flight_offer = results["flight"].data.get("offer_id")
            if results.get("hotel") and results["hotel"].ok:
                sess.pending_hotel_offer = results["hotel"].data.get("offer_id")
            if city:
                sess.last_city = city
            if c.nights:
                sess.last_nights = c.nights

            parts = [r.summary for r in results.values() if r.summary]
            if not parts:
                reply = ("Tell me a destination (and dates) and I'll have my flight, hotel, weather and budget "
                         "specialists pull everything together in one go.")
            else:
                reply = " ".join(parts)
                if sess.pending_flight_offer or sess.pending_hotel_offer:
                    reply += " Reply 'yes' to confirm and I'll book everything above."

        sess.history += [{"role": "user", "content": message}, {"role": "assistant", "content": reply}]
        sess.turns += 1
        trace.finish(reply, len(agents_run), status="ok")
        return {"reply": reply, "trace_id": trace.id, "agents": agents_run,
                "agent_details": {k: {"ok": v.ok, "summary": v.summary} for k, v in results.items()},
                "guardrail_hits": [h.rule_id for h in hits], "consent": consent,
                "latency_ms": int((time.time() - t0) * 1000), "session_id": session_id, "user_id": user_id, "mode": "multi_agent"}


coordinator = MultiAgentCoordinator()
