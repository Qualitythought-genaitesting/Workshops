"""Shared, guardrail-gated tool execution.

Both orchestration styles TripMate ships — the single-agent ReAct loop
(`app/agent.py`) and the multi-agent specialists (`app/multi_agent/`) — call
through this one function to actually run a tool. That means both enforce the
exact same rules (tool allow-list, consent gate for side effects, spend
limit): the same guardrails, two different agent architectures on top of them.
"""
import time
from typing import Any, Dict

from .config import settings
from .data import store
from .guardrails import spend_limit_ok, tool_allowed
from .tools import TOOLS, ToolContext, ToolError
from .tracing import Trace


def execute_tool(tool: str, args: dict, *, user_id: str, session_id: str, trace: Trace, consent: bool) -> Dict[str, Any]:
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
        if not spend_limit_ok(session_id, amount):
            obs = {"error": {"code": "SPEND_LIMIT", "message": f"booking of ₹{amount} would exceed the session limit of ₹{settings.session_spend_limit}"}}
            trace.span(tool, "tool", args, obs, status="blocked", rule_id="GR-SPEND")
            return obs
    tctx = ToolContext(user_id=user_id, session_id=session_id, trace_id=trace.id, consent_given=consent)
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
