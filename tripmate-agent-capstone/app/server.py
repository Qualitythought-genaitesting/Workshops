"""FastAPI server: chat API, trace viewer API, admin/test-control endpoints, web UI."""
import os
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__, PROMPT_VERSION
from .agent import agent
from .config import settings
from .data import store
from .tools import TOOLS
from . import tracing

app = FastAPI(title="TripMate Agent", version=__version__, description="Single-agent travel assistant — system under test for the AI Agent Testing capstone.")
STATIC = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


# ----------------------------------------------------------------------------- models
class ChatIn(BaseModel):
    session_id: str = Field(..., examples=["s-demo-1"])
    user_id: str = Field("u_1287", examples=["u_1287"])
    message: str


class FeedbackIn(BaseModel):
    trace_id: str
    score: int = Field(..., ge=-1, le=1)
    comment: str = ""


class MockIn(BaseModel):
    tool: str
    mode: str = "normal"   # normal|empty|error_503|timeout|malformed|sold_out|dup_price|payment_timeout_after_debit


class ConfigIn(BaseModel):
    max_iterations: Optional[int] = None
    defects_enabled: Optional[bool] = None
    disabled_tools: Optional[List[str]] = None
    session_spend_limit: Optional[int] = None
    weather_enabled: Optional[bool] = None


class ReviewIn(BaseModel):
    text: str


# ----------------------------------------------------------------------------- UI
@app.get("/", include_in_schema=False)
def ui():
    return FileResponse(os.path.join(STATIC, "index.html"))


@app.get("/traces", include_in_schema=False)
def traces_ui():
    return FileResponse(os.path.join(STATIC, "traces.html"))


# ----------------------------------------------------------------------------- core API
@app.get("/health")
def health():
    return {"status": "ok", "app": "TripMate", "version": __version__, "prompt_version": PROMPT_VERSION, "llm_provider": settings.llm_provider,
            "model": settings.model_name(), "defects_enabled": settings.defects_enabled, "tools": list(TOOLS.keys())}


@app.post("/chat")
def chat(body: ChatIn):
    if not body.message.strip():
        raise HTTPException(400, "message is required")
    if body.user_id not in store.users:
        raise HTTPException(404, f"unknown user {body.user_id}")
    return agent.chat(body.session_id, body.user_id, body.message[:8000])


@app.get("/api/traces")
def api_traces(limit: int = 100, session_id: Optional[str] = None):
    return tracing.list_traces(limit, session_id)


@app.get("/api/traces/{trace_id}")
def api_trace(trace_id: str):
    t = tracing.get_trace(trace_id)
    if not t:
        raise HTTPException(404, "trace not found")
    return t


@app.post("/api/feedback")
def api_feedback(body: FeedbackIn):
    if not tracing.add_feedback(body.trace_id, body.score, body.comment):
        raise HTTPException(404, "trace not found")
    return {"ok": True}


@app.get("/api/alerts")
def api_alerts(limit: int = 100):
    return tracing.list_alerts(limit)


@app.get("/api/bookings")
def api_bookings(user_id: Optional[str] = None):
    bs = list(store.bookings.values())
    return [b for b in bs if not user_id or b["user_id"] == user_id]


@app.get("/api/payments")
def api_payments():
    return list(store.payments.values())


@app.get("/api/logs/{name}")
def api_logs(name: str, grep: Optional[str] = None, tail: int = 200):
    if name not in ("app", "payment"):
        raise HTTPException(404, "unknown log")
    path = os.path.join(settings.log_dir, f"{name}.log")
    if not os.path.exists(path):
        return {"lines": []}
    with open(path, encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    if grep:
        lines = [l for l in lines if grep in l]
    return {"lines": [l.rstrip("\n") for l in lines[-tail:]]}


# ----------------------------------------------------------------------------- admin / test control
@app.post("/admin/reset")
def admin_reset(clear_traces: bool = False):
    """Reset inventory, bookings, payments, sessions and mock modes (config is kept)."""
    store.reset()
    agent.reset()
    if clear_traces:
        tracing.clear_all()
    return {"ok": True}


@app.post("/admin/mock")
def admin_mock(body: MockIn):
    if body.tool not in TOOLS:
        raise HTTPException(404, f"unknown tool {body.tool}")
    if body.mode == "normal":
        store.mock.modes.pop(body.tool, None)
    else:
        store.mock.modes[body.tool] = body.mode
    return {"ok": True, "modes": store.mock.modes}


@app.post("/admin/reviews")
def admin_reviews(body: ReviewIn):
    store.mock.injected_reviews.append(body.text)
    return {"ok": True, "injected_reviews": store.mock.injected_reviews}


@app.get("/admin/config")
def admin_get_config():
    return {"max_iterations": settings.max_iterations, "defects_enabled": settings.defects_enabled, "disabled_tools": settings.disabled_tools,
            "session_spend_limit": settings.session_spend_limit, "weather_enabled": store.mock.weather_enabled, "llm_provider": settings.llm_provider,
            "model": settings.model_name(), "prompt_version": PROMPT_VERSION, "app_version": __version__, "mock_modes": store.mock.modes}


@app.post("/admin/config")
def admin_set_config(body: ConfigIn):
    if body.max_iterations is not None:
        settings.max_iterations = max(1, body.max_iterations)
    if body.defects_enabled is not None:
        settings.defects_enabled = body.defects_enabled
    if body.disabled_tools is not None:
        settings.disabled_tools = body.disabled_tools
    if body.session_spend_limit is not None:
        settings.session_spend_limit = body.session_spend_limit
    if body.weather_enabled is not None:
        store.mock.weather_enabled = body.weather_enabled
    return admin_get_config()


@app.post("/admin/config/defaults")
def admin_defaults():
    settings.max_iterations = 10
    settings.disabled_tools = []
    settings.session_spend_limit = 50000
    store.mock.weather_enabled = True
    store.mock.modes.clear()
    store.mock.injected_reviews.clear()
    return admin_get_config()


def main():
    import uvicorn
    uvicorn.run("app.server:app", host=settings.host, port=settings.port, log_level="warning")


if __name__ == "__main__":
    main()
