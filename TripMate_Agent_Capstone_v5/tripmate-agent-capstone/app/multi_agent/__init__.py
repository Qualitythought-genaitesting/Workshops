"""Multi-agent mode for TripMate — five narrow specialists (flight, hotel,
weather, day-planner, budget) coordinated by `coordinator.MultiAgentCoordinator`,
dispatched concurrently where possible so a combined request ("flight + hotel
to Goa") comes back in one round trip.

This package is purely additive: the classroom single-agent build in
`app/agent.py`, its 61 pytest scenarios and 7 planted defects are untouched.
Reach this mode via `POST /chat/multi` (see app/server.py) or the "Multi-agent"
toggle in the chat UI.
"""
from .coordinator import coordinator

__all__ = ["coordinator"]
