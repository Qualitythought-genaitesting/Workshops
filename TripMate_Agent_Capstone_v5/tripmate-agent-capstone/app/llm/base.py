"""Common LLM interface used by the agent loop.

The agent is provider-agnostic: each *step* the LLM either asks for a tool call
(thought + tool + args) or produces a final answer. `scratchpad` holds this
turn's Thought → Action → Observation history (the ReAct trace).
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class LLMStep:
    thought: str
    tool: Optional[str] = None
    args: Dict[str, Any] = field(default_factory=dict)
    final: Optional[str] = None
    tokens_in: int = 0
    tokens_out: int = 0


@dataclass
class TurnContext:
    user_id: str
    session_id: str
    message: str
    history: List[Dict[str, str]]            # prior turns [{role, content}]
    memory: Dict[str, Any]                   # agent working memory (constraints, offers, pending)
    consent: bool                            # did the *current* message give explicit consent?
    run_seed: int
    guardrail_hits: List[Any]


class BaseLLM:
    name = "base"

    def plan(self, ctx: TurnContext) -> List[str]:
        """Return a short ordered plan (list of steps) for this turn."""
        raise NotImplementedError

    def step(self, ctx: TurnContext, scratchpad: List[Dict[str, Any]], iteration: int) -> LLMStep:
        raise NotImplementedError

    def summarise(self, ctx: TurnContext, scratchpad: List[Dict[str, Any]]) -> str:
        """Graceful message when the iteration cap is hit."""
        found = [s for s in scratchpad if s.get("observation") and not s["observation"].get("error")]
        if found:
            return ("I couldn't complete this request within my step limit. Here is what I found so far: "
                    + "; ".join(f"{s['tool']} → {str(s['observation'])[:120]}" for s in found[-3:])
                    + ". Would you like me to continue with a narrower request?")
        return "I couldn't complete this request within my step limit and did not get usable results. Could you narrow the request (dates, area or budget) so I can try again?"
