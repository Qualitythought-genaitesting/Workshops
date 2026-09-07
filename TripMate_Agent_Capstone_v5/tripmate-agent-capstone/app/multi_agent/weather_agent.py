"""Weather specialist: a thin wrapper over get_weather, read by the day-planner
specialist too so the itinerary can mention conditions.
"""
from ..exec_common import execute_tool
from ..llm.nlu import Constraints
from ..tracing import Trace
from .base import SpecialistResult


def check(c: Constraints, *, user_id: str, session_id: str, trace: Trace, consent: bool) -> SpecialistResult:
    if not c.city:
        return SpecialistResult("weather", False, "Weather agent: I need a destination city to check the weather.")
    args = {"city": c.city}
    if c.date:
        args["date"] = c.date
    obs = execute_tool("get_weather", args, user_id=user_id, session_id=session_id, trace=trace, consent=consent)
    tool_calls = [{"tool": "get_weather", "args": args, "status": "error" if obs.get("error") else "ok"}]
    if obs.get("error"):
        return SpecialistResult("weather", False, f"Weather agent: check failed ({obs['error']['message']}).", tool_calls=tool_calls)
    when = f" on {c.date}" if c.date else ""
    summary = f"Weather agent: {c.city}{when} — {obs['summary']}, {obs['temp_c']}°C, {obs['humidity']}% humidity."
    return SpecialistResult("weather", True, summary, data=obs, tool_calls=tool_calls)
