"""ReAct loop testing — grounding, termination, error reaction, answer consistency."""
import json
import re

from tests.conftest import run_scenario, tools, args_of, side_effects, iso
from tests.test_01_planning import HAPPY

HOTEL_ONLY = "3-star hotel near Baga from 15 Oct for 3 nights, 2 adults"


def test_RA_01_happy_loop_efficiency(api):
    def run(api, i):
        r = api.chat(f"RA01-{i}", HAPPY)
        assert r["iterations"] <= 6, f"too many iterations: {r['iterations']}"
        calls = [(t["tool"], json.dumps(t["args"], sort_keys=True)) for t in r["tool_calls"]]
        assert len(calls) == len(set(calls)), f"redundant identical tool calls: {calls}"
        assert not side_effects(r)
        tr = api.trace(r["trace_id"])
        thoughts = [json.loads(s["output"]).get("thought", "") for s in tr["spans"] if s["type"] == "llm"]
        assert all(thoughts), "empty thought in a reasoning step"
    run_scenario("RA-01", api, run)


def test_RA_02_empty_result_grounding(api):
    def run(api, i):
        api.mock("search_flights", "empty")
        r = api.chat(f"RA02-{i}", "Flight to Goa on 15 Oct for 2 adults")
        low = r["reply"].lower()
        assert "found a flight" not in low and not re.search(r"6e-\d+|qp-\d+|ai-\d+", low), f"claimed a flight that no observation contains: {r['reply']}"
        assert any(k in low for k in ("no flights", "found no", "couldn't find", "nothing")), r["reply"]
    run_scenario("RA-02", api, run)


def test_RA_03_malformed_tool_output(api):
    def run(api, i):
        api.mock("search_flights", "malformed")
        r = api.chat(f"RA03-{i}", "Flight to Goa on 15 Oct")
        assert tools(r).count("search_flights") == 2, f"expected one retry, got {tools(r)}"
        assert "₹" not in r["reply"], f"parsed garbage into a fake flight: {r['reply']}"
        assert "not responding" in r["reply"].lower() or "try again" in r["reply"].lower()
    run_scenario("RA-03", api, run)


def test_RA_04_termination_under_persistent_failure(api):
    def run(api, i):
        api.mock("search_hotels", "sold_out")
        r = api.chat(f"RA04-{i}", HOTEL_ONLY)
        n = tools(r).count("search_hotels")
        assert n <= 3, f"kept looping: {n} hotel searches, {r['iterations']} iterations"
        assert "sold out" in r["reply"].lower() or "different dates" in r["reply"].lower(), r["reply"]
    run_scenario("RA-04", api, run)


def test_RA_05_change_of_mind(api):
    def run(api, i):
        sid = f"RA05-{i}"
        api.chat(sid, "Show me flights to Goa on 15 Oct for 2 adults")
        r = api.chat(sid, "Actually make it 16 Oct")
        a = args_of(r, "search_flights")
        assert a.get("date") == iso("16 Oct") and a.get("pax") == 2, f"stale plan not discarded: {a}"
        assert not side_effects(r)
    run_scenario("RA-05", api, run)


def test_RA_06_contradictory_observations(api):
    def run(api, i):
        api.mock("search_flights", "dup_price")
        r = api.chat(f"RA06-{i}", "Flight to Goa on 15 Oct")
        assert "two different fares" in r["reply"].lower() or "re-check" in r["reply"].lower(), f"conflict not flagged: {r['reply']}"
    run_scenario("RA-06", api, run)


def test_RA_07_long_conversation_memory(api):
    def run(api, i):
        sid = f"RA07-{i}"
        api.chat(sid, "Show me flights to Goa on 15 Oct for 2 adults under ₹6,000 per person")
        for k in range(36):
            api.chat(sid, "What's the baggage policy?" if k % 2 else "hi")
        r = api.chat(sid, "Actually make it 16 Oct")
        a = args_of(r, "search_flights")
        assert a.get("pax") == 2 and a.get("max_price") == 6000 and a.get("date") == iso("16 Oct"), f"context lost after 38 turns: {a}"
    run_scenario("RA-07", api, run)


def test_RA_08_final_answer_faithfulness(api):
    def run(api, i):
        r = api.chat(f"RA08-{i}", HAPPY)
        tr = api.trace(r["trace_id"])
        observed = " ".join(s["output"] for s in tr["spans"] if s["type"] == "tool")
        reply = r["reply"]
        for fno in set(re.findall(r"\b(?:6E|QP|AI|UK|SG)-\d{3,4}\b", reply)):
            assert fno in observed, f"flight {fno} in answer but in no observation"
        for price in set(re.findall(r"₹([\d,]+)/person", reply)):
            assert price.replace(",", "") in observed, f"per-person price ₹{price} not in any observation"
        for hotel in ("Baga Bay Resort", "Sea Breeze Inn", "Palm Grove Baga", "Calangute Grand", "Fort Aguada Palace"):
            if hotel in reply:
                assert hotel in observed, f"hotel {hotel} not in any observation"
    run_scenario("RA-08", api, run)


def test_RA_09_iteration_cap_graceful(api):
    def run(api, i):
        api.config(max_iterations=2)
        api.mock("search_hotels", "sold_out")
        r = api.chat(f"RA09-{i}", HOTEL_ONLY)
        assert r["iterations"] == 2
        low = r["reply"].lower()
        assert len(r["reply"]) > 40 and ("couldn't complete" in low or "step limit" in low), f"not graceful: {r['reply']}"
        assert api.trace(r["trace_id"])["status"] == "iteration_cap"
    run_scenario("RA-09", api, run)
