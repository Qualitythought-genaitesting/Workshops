"""Shared plumbing for the multi-agent specialists."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List


@dataclass
class SpecialistResult:
    """What every specialist hands back to the coordinator."""
    agent: str                      # "flight" | "hotel" | "weather" | "planner" | "budget"
    ok: bool
    summary: str                    # one or two sentences folded into the final reply
    data: Dict[str, Any] = field(default_factory=dict)   # offer_id/total_price/etc., consumed by the coordinator and by other specialists (e.g. the planner reads flight/hotel data)
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)


def dispatch_parallel(jobs: Dict[str, Callable[[], SpecialistResult]]) -> Dict[str, SpecialistResult]:
    """Run each job (a zero-arg closure that calls one specialist) in its own
    thread and collect the results keyed by agent name. The specialists only do
    in-memory tool calls (no real network I/O in the classroom build), so this
    is mainly about the *architecture* — independent specialists that don't wait
    on each other — rather than raw speed; swap in a real network-backed tool
    and the concurrency starts paying for itself immediately.
    """
    if not jobs:
        return {}
    if len(jobs) == 1:
        name, fn = next(iter(jobs.items()))
        return {name: fn()}
    with ThreadPoolExecutor(max_workers=len(jobs)) as ex:
        futures = {name: ex.submit(fn) for name, fn in jobs.items()}
        return {name: f.result() for name, f in futures.items()}
