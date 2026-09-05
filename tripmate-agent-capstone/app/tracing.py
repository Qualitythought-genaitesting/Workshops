"""Built-in observability: traces + spans in SQLite, alerts, feedback, log files.

Design mirrors Langfuse: one *trace* per user request, nested *spans* for
plan / llm / tool / guardrail steps. If LANGFUSE_* keys are configured the
trace is also exported (best-effort) so the class can compare.
"""
import json
import logging
import os
import sqlite3
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

from .config import settings
from .guardrails import mask_pii

_lock = threading.RLock()

os.makedirs(settings.log_dir, exist_ok=True)
os.makedirs(os.path.dirname(settings.db_path), exist_ok=True)

app_log = logging.getLogger("tripmate.app")
pay_log = logging.getLogger("tripmate.payment")
for lg, fname in ((app_log, "app.log"), (pay_log, "payment.log")):
    lg.setLevel(logging.INFO)
    if not lg.handlers:
        h = logging.FileHandler(os.path.join(settings.log_dir, fname), encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        lg.addHandler(h)
    lg.propagate = False

SCHEMA = """
CREATE TABLE IF NOT EXISTS traces (
  id TEXT PRIMARY KEY, session_id TEXT, user_id TEXT, ts REAL, input TEXT, output TEXT,
  iterations INTEGER, tokens_in INTEGER, tokens_out INTEGER, cost_inr REAL, latency_ms INTEGER,
  status TEXT, model TEXT, prompt_version TEXT, app_version TEXT, temperature REAL, error TEXT, metadata TEXT
);
CREATE TABLE IF NOT EXISTS spans (
  id TEXT PRIMARY KEY, trace_id TEXT, parent_id TEXT, seq INTEGER, name TEXT, type TEXT,
  input TEXT, output TEXT, status TEXT, latency_ms INTEGER, tokens INTEGER, metadata TEXT, ts REAL
);
CREATE TABLE IF NOT EXISTS alerts (id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, trace_id TEXT, kind TEXT, message TEXT);
CREATE TABLE IF NOT EXISTS feedback (id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, trace_id TEXT, score INTEGER, comment TEXT);
CREATE INDEX IF NOT EXISTS idx_spans_trace ON spans(trace_id);
"""


def _conn():
    c = sqlite3.connect(settings.db_path, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


with _lock, _conn() as c:
    c.executescript(SCHEMA)


def _j(v: Any) -> str:
    try:
        return mask_pii(json.dumps(v, ensure_ascii=False, default=str))
    except Exception:
        return mask_pii(str(v))


class Trace:
    """Collects spans in memory and flushes once at the end of the request."""

    def __init__(self, session_id: str, user_id: str, user_input: str):
        self.id = "tr_" + uuid.uuid4().hex[:12]
        self.session_id, self.user_id = session_id, user_id
        self.input = user_input
        self.start = time.time()
        self.spans: List[Dict[str, Any]] = []
        self.tokens_in = self.tokens_out = 0
        self.iterations = 0
        self.status = "ok"
        self.error: Optional[str] = None
        self.output = ""
        self.metadata: Dict[str, Any] = {}
        app_log.info(f"trace_id={self.id} session={session_id} user={user_id} event=request_start input={mask_pii(user_input)[:200]!r}")

    def span(self, name: str, type_: str, input_: Any, output: Any = None, status: str = "ok",
             latency_ms: int = 0, tokens: int = 0, parent_id: Optional[str] = None, **meta) -> str:
        sid = "sp_" + uuid.uuid4().hex[:10]
        self.spans.append({"id": sid, "trace_id": self.id, "parent_id": parent_id, "seq": len(self.spans) + 1, "name": name,
                           "type": type_, "input": _j(input_), "output": _j(output), "status": status, "latency_ms": latency_ms,
                           "tokens": tokens, "metadata": _j(meta), "ts": time.time()})
        self.tokens_in += meta.get("tokens_in", 0)
        self.tokens_out += meta.get("tokens_out", 0)
        if type_ == "tool" and name == "process_payment":
            pay_log.info(f"trace_id={self.id} tool=process_payment status={status} output={_j(output)[:300]}")
        return sid

    def finish(self, output: str, iterations: int, status: str = "ok", error: Optional[str] = None):
        self.output, self.iterations, self.status, self.error = output, iterations, status, error
        latency = int((time.time() - self.start) * 1000)
        # mock cost model: ₹0.0004 per input token, ₹0.0016 per output token (gpt-4o-mini-ish in INR)
        cost = round(self.tokens_in * 0.0004 + self.tokens_out * 0.0016, 4)
        from . import __version__, PROMPT_VERSION
        with _lock, _conn() as c:
            c.execute("INSERT INTO traces VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (self.id, self.session_id, self.user_id, self.start, mask_pii(self.input), mask_pii(output), iterations,
                       self.tokens_in, self.tokens_out, cost, latency, status, settings.model_name(), PROMPT_VERSION, __version__,
                       settings.temperature, error, _j(self.metadata)))
            c.executemany("INSERT INTO spans VALUES (:id,:trace_id,:parent_id,:seq,:name,:type,:input,:output,:status,:latency_ms,:tokens,:metadata,:ts)", self.spans)
            if iterations >= settings.max_iterations:
                c.execute("INSERT INTO alerts (ts, trace_id, kind, message) VALUES (?,?,?,?)", (time.time(), self.id, "iteration_cap", f"trace hit iteration cap ({iterations})"))
            if cost > settings.cost_alert_threshold_inr:
                c.execute("INSERT INTO alerts (ts, trace_id, kind, message) VALUES (?,?,?,?)", (time.time(), self.id, "cost", f"trace cost ₹{cost} exceeded threshold"))
            if status == "error":
                c.execute("INSERT INTO alerts (ts, trace_id, kind, message) VALUES (?,?,?,?)", (time.time(), self.id, "error", error or "unknown"))
        app_log.info(f"trace_id={self.id} event=request_end status={status} iterations={iterations} latency_ms={latency} cost_inr={cost}")
        _export_langfuse(self, cost, latency)


def _export_langfuse(tr: "Trace", cost: float, latency: int):
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        return
    try:  # optional dependency
        from langfuse import Langfuse  # type: ignore
        lf = Langfuse(public_key=settings.langfuse_public_key, secret_key=settings.langfuse_secret_key, host=settings.langfuse_host)
        t = lf.trace(id=tr.id, name="tripmate.chat", user_id=tr.user_id, session_id=tr.session_id, input=tr.input, output=tr.output,
                     metadata={"iterations": tr.iterations, "cost_inr": cost, "latency_ms": latency})
        for s in tr.spans:
            t.span(name=s["name"], input=s["input"], output=s["output"], metadata={"type": s["type"], "status": s["status"]})
        lf.flush()
    except Exception as e:  # never fail the request because of the exporter
        app_log.warning(f"trace_id={tr.id} langfuse_export_failed={e}")


# ----------------------------------------------------------------------------
# Query helpers used by the API / viewer
# ----------------------------------------------------------------------------

def list_traces(limit: int = 100, session_id: Optional[str] = None) -> List[dict]:
    with _lock, _conn() as c:
        if session_id:
            rows = c.execute("SELECT * FROM traces WHERE session_id=? ORDER BY ts DESC LIMIT ?", (session_id, limit)).fetchall()
        else:
            rows = c.execute("SELECT * FROM traces ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]


def get_trace(trace_id: str) -> Optional[dict]:
    with _lock, _conn() as c:
        t = c.execute("SELECT * FROM traces WHERE id=?", (trace_id,)).fetchone()
        if not t:
            return None
        spans = [dict(r) for r in c.execute("SELECT * FROM spans WHERE trace_id=? ORDER BY seq", (trace_id,)).fetchall()]
        fb = [dict(r) for r in c.execute("SELECT * FROM feedback WHERE trace_id=?", (trace_id,)).fetchall()]
        return {**dict(t), "spans": spans, "feedback": fb}


def add_feedback(trace_id: str, score: int, comment: str = "") -> bool:
    with _lock, _conn() as c:
        if not c.execute("SELECT 1 FROM traces WHERE id=?", (trace_id,)).fetchone():
            return False
        c.execute("INSERT INTO feedback (ts, trace_id, score, comment) VALUES (?,?,?,?)", (time.time(), trace_id, score, comment))
        return True


def list_alerts(limit: int = 100) -> List[dict]:
    with _lock, _conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM alerts ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()]


def count_traces() -> int:
    with _lock, _conn() as c:
        return c.execute("SELECT COUNT(*) FROM traces").fetchone()[0]


def clear_all():
    with _lock, _conn() as c:
        for t in ("traces", "spans", "alerts", "feedback"):
            c.execute(f"DELETE FROM {t}")
