"""Planning testing — decomposition, ordering, constraint honouring, re-planning."""
from tests.conftest import run_scenario, tools, args_of, side_effects, iso

HAPPY = ("Book me a morning flight Hyderabad → Goa on 15 Oct for 2 adults under ₹6,000 per person, "
         "and add a 3-star hotel near Baga Beach for 3 nights. Use my saved traveller Priya.")


def test_PL_01_single_flight_constraints(api):
    def run(api, i):
        r = api.chat(f"PL01-{i}", "Flight HYD→GOI 15 Oct, 2 adults, under ₹6k pp")
        assert "search_flights" in tools(r), f"expected search_flights, got {tools(r)}"
        assert not side_effects(r), f"side-effect tools called: {side_effects(r)}"
        a = args_of(r, "search_flights")
        assert a.get("from") == "HYD" and a.get("to") == "GOI", f"route wrong: {a}"
        assert a.get("date") == iso("15 Oct"), f"date wrong: {a}"
        assert a.get("pax") == 2, f"pax wrong: {a}"
        assert a.get("max_price") == 6000, f"budget constraint missing/incorrect in tool params: {a}"
    run_scenario("PL-01", api, run)


def test_PL_02_flight_plus_hotel(api):
    def run(api, i):
        r = api.chat(f"PL02-{i}", HAPPY)
        t = tools(r)
        assert t[:3] == ["get_user_profile", "search_flights", "search_hotels"], f"unexpected plan/order: {t}"
        assert not side_effects(r), f"booked without confirmation: {side_effects(r)}"
        f, h = args_of(r, "search_flights"), args_of(r, "search_hotels")
        assert f.get("max_price") == 6000 and f.get("pax") == 2 and f.get("depart_before"), f"flight constraints lost: {f}"
        assert h.get("stars") == 3 and h.get("area") == "Baga" and h.get("nights") == 3 and h.get("adults") == 2, f"hotel constraints lost: {h}"
        assert "yes" in r["reply"].lower() and "confirm" in r["reply"].lower(), "must ask for confirmation"
    run_scenario("PL-02", api, run)


def test_PL_03_round_trip(api):
    def run(api, i):
        r = api.chat(f"PL03-{i}", "Round trip HYD–GOA 15–18 Oct, 2 adults")
        dates = [t["args"].get("date") for t in r["tool_calls"] if t["tool"] == "search_flights"]
        assert sorted(dates) == sorted([iso("15 Oct"), iso("18 Oct")]), f"expected outbound+return searches, got {dates}"
        assert not side_effects(r)
    run_scenario("PL-03", api, run)


def test_PL_04_conflicting_constraints(api):
    def run(api, i):
        r = api.chat(f"PL04-{i}", "Cheapest flight to Goa on 15 Oct but it must be non-stop business class")
        assert tools(r).count("search_flights") <= 2, f"too many searches: {tools(r)}"
        assert any(k in r["reply"].lower() for k in ("different directions", "which matters more", "trade-off")), f"tension not explained: {r['reply']}"
        assert not side_effects(r)
    run_scenario("PL-04", api, run)


def test_PL_05_missing_information(api):
    def run(api, i):
        r = api.chat(f"PL05-{i}", "Book me a hotel in Goa")
        assert tools(r) == [], f"searched before asking for dates: {tools(r)}"
        assert "check-in" in r["reply"].lower() or "dates" in r["reply"].lower(), r["reply"]
    run_scenario("PL-05", api, run)


def test_PL_06_impossible_request(api):
    def run(api, i):
        r = api.chat(f"PL06-{i}", "Flight to Goa on 15 Aug under ₹1,500 per person")
        assert 1 <= tools(r).count("search_flights") <= 2, f"search count: {tools(r)}"
        low = r["reply"].lower()
        assert "found a flight" not in low and "6e-2341" not in low, f"hallucinated a flight on empty results: {r['reply']}"
        assert any(k in low for k in ("no flights", "found no", "nothing", "couldn't find")), f"did not report empty results honestly: {r['reply']}"
    run_scenario("PL-06", api, run)


def test_PL_07_replan_on_empty(api):
    def run(api, i):
        r = api.chat(f"PL07-{i}", "Non-stop morning flight to Goa on 15 Oct for 2 adults under ₹5,000 per person")
        assert tools(r).count("search_flights") == 2, f"expected initial + widened search, got {tools(r)}"
        assert "6E-455" in r["reply"], f"did not offer the afternoon alternative: {r['reply']}"
        assert "6E-2341" not in r["reply"], "offered an over-budget flight as if it matched"
        assert not side_effects(r)
    run_scenario("PL-07", api, run)


def test_PL_08_distraction_then_resume(api):
    def run(api, i):
        sid = f"PL08-{i}"
        api.chat(sid, HAPPY)
        r = api.chat(sid, "…also what's the weather like in Goa then?")
        assert tools(r) == ["get_weather"], f"expected exactly one weather call, got {tools(r)}"
        low = r["reply"].lower()
        assert "°c" in low or "weather" in low
        assert "go ahead" in low or "book" in low, f"booking context lost: {r['reply']}"
    run_scenario("PL-08", api, run)


def test_PL_09_hinglish(api):
    def run(api, i):
        r = api.chat(f"PL09-{i}", "Goa ke liye 15 Oct ko subah ki flight chahiye, 2 log")
        a = args_of(r, "search_flights")
        assert a.get("to") == "GOI" and a.get("date") == iso("15 Oct") and a.get("pax") == 2 and a.get("depart_before"), f"Hinglish constraints lost: {a}"
    run_scenario("PL-09", api, run)
