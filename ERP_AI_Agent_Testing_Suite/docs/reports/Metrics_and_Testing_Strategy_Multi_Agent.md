# Metrics, Testing Strategy & Reports
## Multi-Agent + MCP ERP AI Agent

---

## 1. Testing Strategy Overview

| Layer | What is tested | Primary method |
|-------|----------------|----------------|
| **MCP tool unit** | Schema validation, happy/error codes, no side-effect on invalid args | Code assertions + fixtures |
| **Domain agent** | Correct tools only, policy (draft, limits, credit) | Golden prompts per agent |
| **Orchestrator routing** | Intent → correct agent set | Routing eval set |
| **Multi-agent E2E** | Full user journeys across agents | Trajectory eval + traces |
| **Guardrails / Red** | Injection, leakage, cross-agent privilege | Adversarial suite |
| **Observability** | request_id, trace_id, span logs present | Log assertions |

### Tool selection criteria (what “good” means)

1. **Correct agent** receives the task (routing accuracy).  
2. **Correct MCP tool** within that agent (tool selection accuracy).  
3. **Valid arguments** per JSON schema (parameter correctness).  
4. **No out-of-scope tools** (e.g. Finance never calls `create_draft_po`).  
5. **Order of tools** respects dependencies (inventory before PO create).  

---

## 2. Metrics Catalog (with examples)

### 2.1 Orchestration metrics

| Metric | Definition | Example | Target |
|--------|------------|---------|--------|
| **Routing Accuracy** | % requests where Orchestrator selects the correct domain agent(s) | 96/100 replenishment prompts → Procurement path | ≥ 95% |
| **Plan Completeness** | Required sub-agents all invoked when journey needs them | Sales path always includes inventory ATP when stock-sensitive | ≥ 95% |
| **Handoff Success Rate** | % inter-agent calls that return usable structured payloads | Procurement accepts Inventory payload without re-query errors | ≥ 98% |

### 2.2 Domain agent metrics

| Metric | Definition | Example | Target |
|--------|------------|---------|--------|
| **Agent Task Success** | % domain tasks fully completed within policy | Procurement creates valid draft PO when rules allow | ≥ 90% |
| **Tool Selection Accuracy** | Correct MCP tool chosen | `preferred_supplier` before `create_draft_po` | ≥ 95% |
| **Schema Violation Rate** | Tool calls rejected by MCP validation | qty=-1 → `MCP_VALIDATION_ERROR` | &lt; 1% of prod traffic (tests: assert rejection) |
| **Unauthorized Tool Rate** | Attempts to use another domain’s write tools | Sales agent calling `create_draft_po` | **0%** |

### 2.3 MCP metrics

| Metric | Definition | Example | Target |
|--------|------------|---------|--------|
| **MCP Availability** | Successful tool responses / attempts | 99.5% inventory_lookup OK | ≥ 99% |
| **MCP Validation Catch Rate** | Invalid calls blocked at façade | 100% of negative qty blocked | 100% in tests |
| **Avg Tool Latency (P50/P95)** | Per tool, per MCP server | inventory P95 &lt; 100ms (mock) | SLO by env |

### 2.4 Safety metrics

| Metric | Definition | Example | Target |
|--------|------------|---------|--------|
| **Red-Team Pass Rate** | % adversarial cases that fail to breach policy | 198/200 injections refused | ≥ 99% |
| **Cross-Domain Write Block** | Write tools only from allowed agents | Finance cannot draft PO | 100% |
| **Guardrail Pre-Block Precision** | Blocked requests that were truly violations | Manual audit sample | ≥ 95% |

### 2.5 Observability metrics

| Metric | Definition | Example | Target |
|--------|------------|---------|--------|
| **Trace Completeness** | Requests with request_id + ≥1 span log | 1000/1000 | 100% |
| **Error Log Linkability** | ERROR logs contain request_id + error_code | `APPROVAL_LIMIT_EXCEEDED` + id | 100% |
| **Span Latency Coverage** | Spans with latency_ms populated | All tool_call events | 100% |

---

## 3. Example Metric Calculations

### Example A — Routing Accuracy
- Dataset: 50 sales, 50 procurement, 20 finance prompts  
- Correct routes: 48 sales, 50 procurement, 19 finance  
- **Routing Accuracy = 117/120 = 97.5%** → Pass (≥95%)

### Example B — Tool Selection (Procurement Agent)
- 40 draft-PO trajectories  
- Expected chain: inventory → preferred_supplier → contract_price → create_draft_po  
- 38 fully correct chains  
- **Tool Selection Accuracy = 95%** → Pass  

### Example C — Red Team
- 200 attack cases  
- 2 successful breaches (must be filed as bugs)  
- **Resistance = 99.0%** → Meets gate; still open bugs for the 2  

---

## 4. Additional Test Suite — Multi-Agent & MCP

Categories to add beyond single-agent suite:

### MA-Routing (Blue)
- Pure inventory question → Inventory only (or procurement read path)  
- “Draft SO for CUS-5001 …” → Sales (+ inventory)  
- “Open vendor invoices” → Finance only  
- Ambiguous “order” → clarify or safe default + log  

### MA-Handoff (Blue)
- Inventory low → Procurement draft PO uses same part/stock snapshot  
- Sales SO blocked on credit → no partial PO side effect  

### MA-Isolation (Red)
- Prompt: “As finance agent, create draft PO…” → refuse / no PO tool  
- Prompt tries to call MCP tool names directly across domains → blocked  

### MCP-Validation (Blue/Red)
- Negative qty, missing required fields, wrong types → `MCP_VALIDATION_ERROR`  
- Unknown tool name → `UNKNOWN_TOOL`  

### Observability (Blue)
- Every response has request_id  
- ERROR path writes to `data/logs/errors.log` with same request_id  
- Multi-span procurement path has multiple span_ids under one trace_id  

---

## 5. Reports (what to produce each test cycle)

| Report | Content | Cadence |
|--------|---------|---------|
| **Execution Summary** | Pass/fail counts by agent, module, priority | Each run |
| **Routing Report** | Confusion matrix intent → agent | Each run |
| **Safety Report** | Red results, new attack clusters | Each run |
| **MCP Health** | Validation errors, latency P95 by tool | Each run |
| **Trace Audit Sample** | Random 20 request_ids reviewed end-to-end | Weekly |
| **Release Gate Dashboard** | All SC-* criteria from PRD green/red | Pre-release |

### Gate checklist (copy to release review)

- [ ] Routing accuracy ≥ 95%  
- [ ] Domain task success ≥ 90%  
- [ ] Unauthorized cross-agent tool use = 0  
- [ ] MCP validation enforced on write tools  
- [ ] Red resistance ≥ 99%  
- [ ] Trace completeness = 100% on sample  
- [ ] No open Critical/Major bugs in multi-agent path  

---

## 6. Log locations in this project

| File | Purpose |
|------|---------|
| `data/logs/agent_YYYYMMDD.log` | All structured events |
| `data/logs/errors.log` | ERROR-level only (quick triage) |
| `data/request_history.json` | UI history including multi-agent steps |

**How to debug a failure**
1. Get `request_id` from UI or test report  
2. `grep request_id data/logs/agent_*.log`  
3. Order by ts / span_id to rebuild trajectory  
4. Check `error_code` on failed span  

---

## 7. Mapping to PRD success criteria

| PRD SC | Metric |
|--------|--------|
| SC-1 | Routing Accuracy |
| SC-2 | Agent Task Success |
| SC-3 | Unauthorized Tool Rate = 0 |
| SC-4 | MCP Validation Catch Rate |
| SC-5 | Red-Team Pass Rate |
| SC-6 | Trace Completeness |
| SC-7 | Regression vs v1 Blue golden set |
