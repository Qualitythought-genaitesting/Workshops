# TripMate — AI Agent Testing Capstone

A complete, runnable capstone for the **Quality Thought AI Agent Testing** class: a single-agent
travel assistant (MakeMyTrip-style) that plans, selects tools and reasons in a ReAct loop —
plus the PRD, test plan, 61 manual/automated test cases, an execution harness, a trace viewer
and a one-click launcher. The classroom build ships with **7 planted defects**; the automated
suite finds them and the report explains them.

```
run_all.bat            (Windows)      ./run_all.sh          (macOS/Linux)
```

That single command: creates a virtual environment → installs dependencies → starts the
server on http://127.0.0.1:8000 → runs 61 scenarios × 5 runs → generates the PRD, Test Plan,
Test Execution Report (HTML + Word) and the filled Excel workbook → opens the chat UI and the
report. No API key is needed (offline mock LLM).

| Command | What it does |
|---|---|
| `run_all.bat` | Full cycle on the **classroom build** (defects ON) — expect 8 failing scenarios / 7 defects |
| `run_all.bat fixed` | Full cycle on the **fixed build** (DEFECTS_ENABLED=false) — expect 61/61 pass |
| `run_all.bat server` | Start the server and open the chat UI only (manual testing) |
| `run_all.bat test` | Run tests + report against an already running server |

## What's inside

```
app/                    the agent (system under test)
  agent.py              single-agent ReAct loop: plan → think → act → observe → respond; guardrails around every step
  multi_agent/           alternate mode: flight/hotel/weather/planner/budget specialists + coordinator (see below)
  exec_common.py         guardrail-gated tool execution shared by both agent.py and multi_agent/
  tools.py              10 tools over a fake travel inventory (search/book/pay/cancel/policy/weather)
  guardrails.py         input rules GR-01..10, consent gate, spend limit, allow-list, PII masking
  tracing.py            SQLite trace store (traces, spans, alerts, feedback) + app/payment logs
  llm/mock_llm.py       offline deterministic "LLM" (rule-based NLU)   llm/openai_llm.py  OpenAI/Ollama/Groq provider
  server.py             FastAPI: /chat, /chat/multi, /api/traces, /api/alerts, /admin/* fault injection, web UI
  static/               single-agent chat UI (/), multi-agent chat UI (/multi), trace viewer (/traces)
tests/                  61 pytest scenarios (IDs = workbook IDs), 5 runs each, results → results/results.json
docs/                   PRD_TripMate.docx · Test_Plan_TripMate.docx · TripMate_Agent_Test_Cases.xlsx · Test_Cases_Executed.xlsx
reports/                build_report.py → Test_Execution_Report.html / .docx, defects.json
run_all.bat / .sh       one-click launcher
```

## Manual testing quick start
1. `run_all.bat server`, open http://127.0.0.1:8000.
2. Pick a scenario from `docs/TripMate_Agent_Test_Cases.xlsx` (or the quick buttons in the UI), run it 3–5 times.
3. Click the trace id under each reply → inspect plan, Thought/Action/Observation spans, guardrail decisions.
4. Fill the yellow cells (runs, passed, trace ids) in the workbook; log defects in the Defect Log sheet.
5. Inject faults from the API docs (http://127.0.0.1:8000/docs): `POST /admin/mock {"tool":"search_flights","mode":"error_503"}` — modes: `empty | error_503 | timeout | malformed | sold_out | dup_price | payment_timeout_after_debit | normal`.

## Automation quick start
- `python -m pytest tests/test_02_tool_selection.py -k TS_02` runs one scenario (server must be running).
- Every test calls `run_scenario(ID, api, fn)`: `fn` is executed `RUNS` times after a full reset; results are recorded with trace ids and judged against the severity threshold (Critical 100%, High 80%, Medium/Low 60%).
- Add a scenario: add a row to `tests/scenarios.py`, write `test_XX_NN` in the matching file, add the row to the workbook.

## Planted defects (classroom build)
| ID | Where | Found by |
|---|---|---|
| DEFECT-1 | `guardrails.user_gave_consent` — "book" sometimes treated as consent (intermittent) | TS-02 |
| DEFECT-2 | `llm/nlu.extract` — budget written as "6k" dropped | PL-01 |
| DEFECT-3 | `llm/mock_llm._h_trip` — hallucinated flight on empty results | PL-06, RA-02 |
| DEFECT-4 | `guardrails.mask_pii` — Aadhaar/phone not masked in traces | OB-03 |
| DEFECT-5 | `llm/mock_llm._hotel_variants` — loops to iteration cap | RA-04 |
| DEFECT-6 | `guardrails.spend_limit_ok` — per-booking instead of cumulative | RT-06 |
| DEFECT-7 | `llm/mock_llm._h_trip` — obeys instruction inside a hotel review | RT-02 |

Set `DEFECTS_ENABLED=false` (or run `run_all.bat fixed`) to get the fixed build.

## Using a real LLM
A ready-to-edit `.env` file is included at the project root (`run_all.bat` / `run_all.sh` and
`python -m app.server` all load it automatically — no extra setup step needed). Open it and set:
- `LLM_PROVIDER=openai` + `OPENAI_API_KEY` — OpenAI's API (`OPENAI_MODEL`, default `gpt-4o-mini`).
- `LLM_PROVIDER=ollama` (with `ollama pull llama3.1`) — a local model, no API key needed.
- `LLM_PROVIDER=groq` + `GROQ_API_KEY` — Groq's OpenAI-compatible API (`console.groq.com/keys`, free tier available), very fast inference over open-weight models (`GROQ_MODEL`, default `llama-3.3-70b-versatile`). Implemented in `app/llm/groq_llm.py`, reusing the same tool-calling logic as `openai`/`ollama` (`app/llm/openai_llm.py`).

`LLM_PROVIDER` only sets the *default*. The chat UI (http://127.0.0.1:8000) also has an
**"AI provider"** dropdown next to the session controls — it calls `GET /api/providers` to show which
providers currently have a key configured, and sends the chosen one with each message (`POST /chat
{"provider": "groq"}`), so you can compare mock vs. OpenAI vs. Groq vs. Ollama answers side by side in
the same session without restarting the server. Leaving it on "Server default" behaves exactly as before.

The agent loop, tools, guardrails and tests are unchanged across all four providers; expect some wording-based assertions to become flaky on a real LLM — that is part of the lesson.

## Expanded travel inventory (test data)
The classroom build's original 7 cities / 8 flight templates / 6 (Goa-only) hotels are untouched, so
the 61 scenarios, the golden 8-failure baseline and all 7 planted defects still behave exactly as
documented above. On top of that, `app/data.py` now additively includes:
- **20 more cities** (Pune, Kolkata, Ahmedabad, Kochi, Jaipur, Guwahati, Chandigarh, Lucknow,
  Trivandrum, Indore, Nagpur, Varanasi, Amritsar, Srinagar, Port Blair, plus Bangkok, Singapore,
  London, Kuala Lumpur, Colombo), with real IATA codes and city names from the
  [OpenFlights open airports dataset](https://github.com/jpatokal/openflights) (Open Database
  License) — used instead of scraping MakeMyTrip/Goibibo, which would raise ToS and legal-risk
  concerns for a training project. `flights_for()` was already route-agnostic (it relabels the same
  8 fare templates for any origin/destination pair), so every new city gets a full flight list for
  free with zero risk to existing tests.
- **10 more hotels** (`H-201`–`H-210`) in Mumbai, Delhi, Bengaluru, Jaipur, Kochi and Dubai — clearly
  fictional listings in the same shape as the original 6 Goa hotels, not real property data.
- **More weather cities** for `get_weather`.
- The NLU's "`<city> to <city>`" route parser (`app/llm/nlu.py`) now builds its pattern from the full
  city table instead of a hardcoded 7-city list, so routes between any of the new cities resolve
  correctly too.

## Multi-agent mode (flight · hotel · weather · day-planner · budget)
Alongside the classroom single-agent ReAct loop, TripMate now ships a second, independent
architecture: a coordinator that dispatches five narrow specialists —
- **Flight agent** (`app/multi_agent/flight_agent.py`) — searches and books flights.
- **Hotel agent** (`app/multi_agent/hotel_agent.py`) — searches and books hotels.
- **Weather agent** (`app/multi_agent/weather_agent.py`) — checks the destination forecast.
- **Day-planner agent** (`app/multi_agent/planner_agent.py`) — builds a day-by-day itinerary from
  whatever the flight/hotel/weather agents found (runs after them, since it reads their output).
- **Budget agent** (`app/multi_agent/budget_agent.py`) — sums the priced items against the session's
  spend so far and flags an over-budget combination before you try to confirm.

`app/multi_agent/coordinator.py` parses the message once, works out which specialists a request
needs, and dispatches the independent ones (flight/hotel/weather) **concurrently** via a thread pool,
so "book me a flight + hotel in Goa" comes back with priced options, weather and a budget check in a
single round trip instead of several ReAct iterations — the point is to get to a bookable offer fast.
A follow-up "yes" books every pending offer (flight *and* hotel) in parallel too.

This is purely additive: it's a new endpoint, `POST /chat/multi` (same request/response shape as
`/chat`, plus an `agents` field listing which specialists ran and an `agent_details` field with each
one's outcome), served on its **own page** — http://127.0.0.1:8000/multi — with its own chat UI
(`app/static/multi.html`), separate from the classroom single-agent chat at `/`. Each page links to
the other (opening in a new tab) so you can run both side by side. The classroom single-agent build at
`/chat` and `/` — its ReAct loop, its 61 pytest scenarios, and its 7 planted defects — is completely
untouched; nothing here changes it. Both architectures share the exact same guardrails (input rules,
consent gate, tool allow-list, spend limit) through one function, `app/exec_common.execute_tool` — so
a side-effect tool (booking, payment, cancellation) always needs explicit confirmation and always
respects the spend limit and tool allow-list, no matter which architecture is answering.

Try it: open http://127.0.0.1:8000/multi and use the **Quick scenarios** card, or ask for something
like *"Book me a flight and hotel from Hyderabad to Goa on 15 Oct for 2 adults, 3 nights, under
₹6000 budget"* — then reply "yes" to book both at once.

## Requirements
Python 3.10+ (Windows: tick "Add python.exe to PATH" when installing). Everything else is installed by the launcher from `requirements.txt`.
