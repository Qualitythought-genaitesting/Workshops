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
  agent.py              ReAct loop: plan → think → act → observe → respond; guardrails around every step
  tools.py              10 tools over a fake travel inventory (search/book/pay/cancel/policy/weather)
  guardrails.py         input rules GR-01..10, consent gate, spend limit, allow-list, PII masking
  tracing.py            SQLite trace store (traces, spans, alerts, feedback) + app/payment logs
  llm/mock_llm.py       offline deterministic "LLM" (rule-based NLU)   llm/openai_llm.py  OpenAI/Ollama provider
  server.py             FastAPI: /chat, /api/traces, /api/alerts, /admin/* fault injection, web UI
  static/               chat UI (/) and trace viewer (/traces)
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
Copy `.env.example` to `.env`, set `LLM_PROVIDER=openai` + `OPENAI_API_KEY`, or `LLM_PROVIDER=ollama` (with `ollama pull llama3.1`). The agent loop, tools, guardrails and tests are unchanged; expect some wording-based assertions to become flaky — that is part of the lesson.

## Requirements
Python 3.10+ (Windows: tick "Add python.exe to PATH" when installing). Everything else is installed by the launcher from `requirements.txt`.
