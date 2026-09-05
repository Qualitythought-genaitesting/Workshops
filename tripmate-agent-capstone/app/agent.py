"""The TripMate agent loop (ReAct): plan → [think → act → observe]* → respond.

Cross-cutting concerns applied around every step: guardrails (input rules,
consent gate, spend limit, tool allow-list), memory, and tracing.
"""
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List

from . import __version__, PROMPT_VERSION
from .config import settings
from .data import store
from .guardrails import check_input, spend_limit_ok, tool_allowed, user_gave_consent
from .llm import get_llm
from .llm.base import TurnContext
from .tools import TOOLS, ToolContext, ToolError
from .tracing import Trace

BLOCKING_CATEGORIES = {"prompt_injection", "prompt_leak", "jailbreak", "impersonation", "cross_user", "price_manipulation", "refund_redirect", "unbounded_scope"}


@dataclass
class Session:
    session_id: str
    user_id: str
    history: List[Dict[str, str]] = field(default_factory=list)
    memory: Dict[str, Any] = field(default_factory=dict)
    turns: int = 0


class Agent:
    def __init__(self):
        self.llm = get_llm()
        self.sessions: Dict[str, Session] = {}
        self._lock = threading.Lock()
        self._run_counter = 0

    def reset(self):
        with self._lock:
            self.sessions.clear()

    def _session(self, session_id: str, user_id: str) -> Session:
        with self._lock:
            s = self.sessions.get(session_id)
            if not s:
                s = self.sessions[session_id] = Session(session_id, user_id)
            if s.user_id != user_id:
                # a session is bound to one user; never let another user read its memory
                s = self.sessions[session_id] = Session(session_id, user_id)
            return s

    def chat(self, session_id: str, user_id: str, message: str) -> Dict[str, Any]:
        sess = self._session(session_id, user_id)
        import zlib
        seed = zlib.crc32(f"{session_id}:{sess.turns}:{message}".encode())   # reproducible per session/turn
        trace = Trace(session_id, user_id, message)
        trace.metadata.update({"app_version": __version__, "prompt_version": PROMPT_VERSION, "defects_enabled": settings.defects_enabled, "turn": sess.turns + 1})
        t0 = time.time()

        # ---- guardrails on input ---------------------------------------------
        hits = check_input(message)
        for h in hits:
            trace.span("guardrail.input", "guardrail", {"rule_id": h.rule_id, "category": h.category, "snippet": h.snippet},
                       {"blocked": h.category in BLOCKING_CATEGORIES, "action": "refuse" if h.category in BLOCKING_CATEGORIES else "policy_answer"},
                       status="blocked" if h.category in BLOCKING_CATEGORIES else "flagged", rule_id=h.rule_id)
        consent = user_gave_consent(message, seed)
        trace.span("guardrail.consent_gate", "guardrail", {"message": message}, {"consent": consent}, status="ok")

        ctx = TurnContext(user_id=user_id, session_id=session_id, message=message, history=list(sess.history), memory=sess.memory,
                          consent=consent, run_seed=seed, guardrail_hits=hits)

        # ---- plan ---------------------------------------------------------------
        ts = time.time()
        plan = self.llm.plan(ctx)
        trace.span("plan", "plan", {"message": message}, {"steps": plan}, latency_ms=int((time.time() - ts) * 1000), tokens_in=120, tokens_out=len(" ".join(plan)) // 4)

        # ---- ReAct loop ------------------------------------------------------------
        scratch: List[Dict[str, Any]] = []
        tool_calls: List[Dict[str, Any]] = []
        final, status, error = None, "ok", None
        iterations = 0
        while iterations < settings.max_iterations:
            iterations += 1
            ts = time.time()
            try:
                step = self.llm.step(ctx, scratch, iterations)
            except Exception as e:  # provider failure
                status, error = "error", f"llm_error: {e}"
                trace.span(f"llm.step.{iterations}", "llm", {"iteration": iterations}, {"error": str(e)}, status="error")
                final = "I'm having trouble reaching my reasoning service. Please try again in a moment — nothing has been booked."
                break
            trace.span(f"llm.step.{iterations}", "llm", {"iteration": iterations, "scratchpad_len": len(scratch)},
                       {"thought": step.thought, "tool": step.tool, "args": step.args, "final": step.final},
                       latency_ms=int((time.time() - ts) * 1000), tokens=step.tokens_in + step.tokens_out, tokens_in=step.tokens_in, tokens_out=step.tokens_out)
            if step.final is not None:
                final = step.final
                break
            observation = self._execute(step.tool, step.args, ctx, trace, consent)
            scratch.append({"thought": step.thought, "tool": step.tool, "args": step.args, "observation": observation})
            tool_calls.append({"tool": step.tool, "args": step.args, "status": "error" if observation.get("error") else "ok",
                               "error_code": (observation.get("error") or {}).get("code")})
        if final is None:
            status = "iteration_cap"
            final = self.llm.summarise(ctx, scratch)
            trace.span("fallback.iteration_cap", "llm", {"iterations": iterations}, {"final": final}, status="warning")

        # ---- memory & trace ----------------------------------------------------------
        sess.history.append({"role": "user", "content": message})
        sess.history.append({"role": "assistant", "content": final})
        sess.turns += 1
        trace.finish(final, iterations, status=status, error=error)
        return {"reply": final, "trace_id": trace.id, "iterations": iterations, "tool_calls": tool_calls, "plan": plan,
                "guardrail_hits": [h.rule_id for h in hits], "consent": consent, "latency_ms": int((time.time() - t0) * 1000),
                "session_id": session_id, "user_id": user_id}

    # ------------------------------------------------------------------ tools
    def _execute(self, tool: str, args: dict, ctx: TurnContext, trace: Trace, consent: bool) -> Dict[str, Any]:
        spec = TOOLS.get(tool)
        ts = time.time()
        if not spec:
            obs = {"error": {"code": "UNKNOWN_TOOL", "message": f"tool {tool} does not exist"}}
            trace.span(tool, "tool", args, obs, status="error")
            return obs
        reason = tool_allowed(tool)
        if reason:
            obs = {"error": {"code": "TOOL_BLOCKED", "message": reason}}
            trace.span(tool, "tool", args, obs, status="blocked", rule_id="GR-ALLOWLIST")
            return obs
        if spec.side_effect and not consent:
            obs = {"error": {"code": "CONSENT_REQUIRED", "message": "side-effect tool requires explicit user confirmation in the current message"}}
            trace.span(tool, "tool", args, obs, status="blocked", rule_id="GR-CONSENT")
            return obs
        if tool == "create_booking":
            offer = store.offers.get(args.get("offer_id", ""))
            amount = offer["total_price"] if offer else 0
            if not spend_limit_ok(ctx.session_id, amount):
                obs = {"error": {"code": "SPEND_LIMIT", "message": f"booking of ₹{amount} would exceed the session limit of ₹{settings.session_spend_limit}"}}
                trace.span(tool, "tool", args, obs, status="blocked", rule_id="GR-SPEND")
                return obs
        tctx = ToolContext(user_id=ctx.user_id, session_id=ctx.session_id, trace_id=trace.id, consent_given=consent)
        try:
            result = spec.fn(args, tctx)
            trace.span(tool, "tool", args, result, status="ok", latency_ms=int((time.time() - ts) * 1000), side_effect=spec.side_effect)
            return result
        except ToolError as e:
            obs = {"error": {"code": e.code, "message": e.message, "http_status": e.http_status}}
            trace.span(tool, "tool", args, obs, status="error", latency_ms=int((time.time() - ts) * 1000), http_status=e.http_status)
            return obs
        except Exception as e:  # defensive
            obs = {"error": {"code": "INTERNAL", "message": str(e)}}
            trace.span(tool, "tool", args, obs, status="error")
            return obs


agent = Agent()
