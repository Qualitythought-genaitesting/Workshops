"""Shared harness: talks to the *deployed* TripMate server over HTTP, runs every
scenario N times (agents are non-deterministic) and records per-run outcomes
to results/results.json for the report builder.
"""
import json
import os
import re
import sys
import time
import traceback
from typing import Callable, Dict, List

import httpx
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tests.scenarios import SCENARIOS, SEVERITY_THRESHOLD  # noqa: E402

BASE_URL = os.getenv("TRIPMATE_URL", "http://127.0.0.1:8000")
RUNS = int(os.getenv("RUNS", "5"))
RESULTS_FILE = os.path.join(ROOT, "results", ".runs.jsonl")   # shared between pytest's conftest instance and test modules
SIDE_EFFECT_TOOLS = {"create_booking", "process_payment", "cancel_booking"}


class Api:
    def __init__(self):
        self.c = httpx.Client(base_url=BASE_URL, timeout=60)

    def health(self):
        return self.c.get("/health").json()

    def reset(self, clear_traces: bool = False):
        self.c.post("/admin/config/defaults")
        return self.c.post("/admin/reset", params={"clear_traces": clear_traces}).json()

    def chat(self, session_id: str, message: str, user_id: str = "u_1287") -> dict:
        r = self.c.post("/chat", json={"session_id": session_id, "user_id": user_id, "message": message})
        r.raise_for_status()
        return r.json()

    def mock(self, tool: str, mode: str):
        return self.c.post("/admin/mock", json={"tool": tool, "mode": mode}).json()

    def config(self, **kw):
        return self.c.post("/admin/config", json=kw).json()

    def review(self, text: str):
        return self.c.post("/admin/reviews", json={"text": text}).json()

    def trace(self, trace_id: str) -> dict:
        return self.c.get(f"/api/traces/{trace_id}").json()

    def traces(self, limit=200):
        return self.c.get("/api/traces", params={"limit": limit}).json()

    def alerts(self):
        return self.c.get("/api/alerts").json()

    def logs(self, name: str, grep: str):
        return self.c.get(f"/api/logs/{name}", params={"grep": grep}).json()["lines"]

    def bookings(self, user_id=None):
        return self.c.get("/api/bookings", params={"user_id": user_id} if user_id else None).json()

    def payments(self):
        return self.c.get("/api/payments").json()

    def feedback(self, trace_id: str, score: int):
        return self.c.post("/api/feedback", json={"trace_id": trace_id, "score": score, "comment": "test"}).json()


@pytest.fixture(scope="session")
def api():
    a = Api()
    for _ in range(30):
        try:
            a.health(); break
        except Exception:
            time.sleep(1)
    else:
        pytest.exit(f"TripMate server not reachable at {BASE_URL}")
    return a


# ----------------------------------------------------------------------------- helpers
def tools(r: dict) -> List[str]:
    return [t["tool"] for t in r["tool_calls"]]


def args_of(r: dict, tool: str, idx: int = 0) -> dict:
    calls = [t for t in r["tool_calls"] if t["tool"] == tool]
    return calls[idx]["args"] if len(calls) > idx else {}


def side_effects(r: dict) -> List[str]:
    return [t for t in tools(r) if t in SIDE_EFFECT_TOOLS]


def executed_side_effects(r: dict) -> List[str]:
    return [t["tool"] for t in r["tool_calls"] if t["tool"] in SIDE_EFFECT_TOOLS and t["status"] == "ok"]


def iso(text: str) -> str:
    """Expected ISO date for a phrase like '15 Oct' using the same calendar logic as the agent."""
    from app.llm.nlu import parse_dates
    d, _, _, _ = parse_dates(text)
    return d


def run_scenario(scenario_id: str, api: Api, fn: Callable[[Api, int], None], runs: int = RUNS):
    """Execute `fn` `runs` times; record per-run outcome; enforce severity threshold."""
    area, stage, title, severity = SCENARIOS[scenario_id]
    outcomes, traces, failures = [], [], []
    for i in range(runs):
        api.reset()
        api._trace_ids = []
        orig_chat = api.chat

        def chat_rec(session_id, message, user_id="u_1287", _o=orig_chat):
            r = _o(session_id, message, user_id)
            api._trace_ids.append(r["trace_id"])
            return r
        api.chat = chat_rec
        try:
            fn(api, i)
            outcomes.append(True)
        except AssertionError as e:
            outcomes.append(False); failures.append(str(e).splitlines()[0][:300])
        except Exception as e:  # harness/infra error counts as a failed run
            outcomes.append(False); failures.append(f"{type(e).__name__}: {e}"[:300])
        finally:
            api.chat = orig_chat
            traces.append(",".join(api._trace_ids[-3:]))
    passed = sum(outcomes)
    rate = passed / runs
    result = "Pass" if passed == runs else ("Fail" if passed == 0 else "Flaky")
    os.makedirs(os.path.dirname(RESULTS_FILE), exist_ok=True)
    with open(RESULTS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps({"id": scenario_id, "area": area, "stage": stage, "title": title, "severity": severity, "runs": runs, "passed": passed,
                    "pass_rate": rate, "result": result, "verdict": "PASS" if rate >= SEVERITY_THRESHOLD[severity] else "FAIL",
                    "failures": sorted(set(failures)), "trace_ids": traces}, ensure_ascii=False) + "\n")
    assert rate >= SEVERITY_THRESHOLD[severity], f"{scenario_id} {title}: {passed}/{runs} runs passed (need ≥{int(SEVERITY_THRESHOLD[severity]*100)}% for {severity}). First failure: {failures[0] if failures else ''}"


def pytest_sessionstart(session):
    os.makedirs(os.path.dirname(RESULTS_FILE), exist_ok=True)
    open(RESULTS_FILE, "w").close()


def pytest_sessionfinish(session, exitstatus):
    out_dir = os.path.join(ROOT, "results")
    if not os.path.exists(RESULTS_FILE):
        return
    with open(RESULTS_FILE, encoding="utf-8") as f:
        RESULTS = [json.loads(l) for l in f if l.strip()]
    if not RESULTS:
        return
    env = {}
    try:
        env = Api().health()
    except Exception:
        pass
    payload = {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "base_url": BASE_URL, "runs_per_scenario": RUNS, "environment": env,
               "python": sys.version.split()[0], "results": sorted(RESULTS, key=lambda r: r["id"])}
    with open(os.path.join(out_dir, "results.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
