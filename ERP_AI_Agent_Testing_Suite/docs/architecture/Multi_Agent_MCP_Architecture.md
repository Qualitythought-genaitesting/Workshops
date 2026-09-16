# Multi-Agent + MCP Architecture
## ERP AI Agent Testing Suite v2

---

## 1. High-Level View

```
                    ┌─────────────────────────────────────┐
                    │           User / UI / API            │
                    │     (request_id generated here)      │
                    └─────────────────┬───────────────────┘
                                      │
                                      ▼
                    ┌─────────────────────────────────────┐
                    │         Guardrail Agent (pre)         │
                    │   injection / scope / PII checks      │
                    └─────────────────┬───────────────────┘
                                      │
                                      ▼
                    ┌─────────────────────────────────────┐
                    │           Orchestrator Agent          │
                    │  plan · route · fan-out · aggregate   │
                    └───────────┬─────────────┬─────────────┘
                    ┌───────────┼─────────────┼─────────────┐
                    ▼           ▼             ▼             ▼
             ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
             │Inventory │ │Procurement│ │  Sales   │ │ Finance  │
             │  Agent   │ │  Agent   │ │  Agent   │ │  Agent   │
             └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘
                  │            │            │            │
                  ▼            ▼            ▼            ▼
             ┌──────────────────────────────────────────────┐
             │              MCP Tool Layer                   │
             │  mcp://inventory  mcp://procurement  ...      │
             │  schema validate · authz · timeouts           │
             └──────────────────┬───────────────────────────┘
                                ▼
             ┌──────────────────────────────────────────────┐
             │     Mock ERP  /  Future SAP·Oracle adapters   │
             └──────────────────────────────────────────────┘
                                │
                                ▼
             ┌──────────────────────────────────────────────┐
             │   Structured Logs (trace_id, span_id, agent)  │
             └──────────────────────────────────────────────┘
```

---

## 2. Components

### 2.1 Orchestrator Agent
- **Input:** user message + request_id  
- **Output:** final natural-language answer + aggregated trace  
- **Tools (MCP):** `route_intent`, `call_inventory`, `call_procurement`, `call_sales`, `call_finance`, `merge_results`  
- **Does not** call ERP write APIs directly  

### 2.2 Domain Agents
Each domain agent:
- Holds a **small** system prompt and **only its** MCP tools  
- Returns structured result `{ status, data, errors[], agent_id, span_id }`  
- Must not invoke another domain’s write tools  

### 2.3 Guardrail Agent
- Pre-check: injection patterns, out-of-scope intents (payments, release PO)  
- Post-check: response does not leak commercial data across parties  
- Can short-circuit the pipeline with `status=refused`  

### 2.4 MCP Layer
Each MCP server exposes:

| Capability | Example |
|------------|---------|
| **Tools** | `inventory_lookup`, `create_draft_po`, … |
| **Resources** | `policy://procurement/approval_limit`, `catalog://items` |
| **Prompts** (optional) | domain-specific prompt fragments |

**Contract rules:**
1. JSON Schema required for every tool  
2. Invalid args → `MCP_VALIDATION_ERROR` (not LLM retry storm)  
3. Timeouts and retries configured per tool  
4. Every invocation tagged with `trace_id` + `span_id` + `agent_id`  

---

## 3. Request Lifecycle & IDs

| ID | Scope | Purpose |
|----|-------|---------|
| **request_id** | Entire user request (UI/API) | External correlation; shareable link |
| **trace_id** | Same as request or W3C trace parent | Log aggregation across agents |
| **span_id** | Single agent or tool call | Latency & error localization |
| **agent_id** | inventory / procurement / … | Ownership & metrics dimensions |

### Example log line (JSON)

```json
{
  "ts": "2026-09-13T10:15:30.123Z",
  "level": "INFO",
  "request_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "trace_id": "a1b2c3d4e5f67890abcd",
  "span_id": "span-proc-01",
  "agent_id": "procurement",
  "event": "tool_call",
  "tool": "create_draft_po",
  "mcp_server": "mcp://procurement",
  "latency_ms": 42,
  "status": "ok",
  "error_code": null
}
```

### Error log example

```json
{
  "ts": "2026-09-13T10:15:31.000Z",
  "level": "ERROR",
  "request_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "trace_id": "a1b2c3d4e5f67890abcd",
  "span_id": "span-proc-02",
  "agent_id": "procurement",
  "event": "tool_error",
  "tool": "create_draft_po",
  "mcp_server": "mcp://procurement",
  "status": "error",
  "error_code": "APPROVAL_LIMIT_EXCEEDED",
  "error_message": "Total 62500.00 exceeds limit 50000.00",
  "args_redacted": {"part": "Widget-X", "qty": 5000}
}
```

---

## 4. Implementation Mapping (This Repo)

| Path | Role |
|------|------|
| `app/agent_core.py` | v1 single-agent (still supported) |
| `app/multi_agent/` | v2 orchestrator + domain agents + MCP façade |
| `app/ui.py` | UI shows request_id; can display multi-agent spans |
| `data/request_history.json` | Persists full traces including agent spans |
| `docs/prd/PRD_Multi_Agent_MCP.md` | Requirements |
| `docs/architecture/` | This document |
| `docs/reports/` | Metrics definitions & templates |

### MCP façade (project approach)
For the **testing suite**, MCP is implemented as an **in-process façade**:
- Same schemas as real MCP tools  
- Mock ERP backends  
- Ready to replace with real MCP servers (stdio/HTTP) without changing agent prompts  

---

## 5. Security Architecture

- Guardrail pre-hook on all requests  
- Domain agents cannot register tools outside their MCP server  
- Write tools only on Procurement/Sales MCP servers, draft-only  
- Finance MCP: read tools only (enforced in server, not only prompt)  
- Logs redact secrets; never log full API keys  

---

## 6. Failure Modes & Handling

| Failure | Handling |
|---------|----------|
| MCP validation error | Return structured error to Orchestrator; user-friendly message |
| Domain agent timeout | Mark span failed; Orchestrator may partial-answer or escalate |
| Guardrail block | Terminate pipeline; status=refused; full audit log |
| Downstream ERP 5xx | Retry once (idempotent reads); else escalate_to_human |

---

## 7. Evolution Path

1. **Now:** In-process multi-agent + MCP schema façade + mock data  
2. **Next:** Out-of-process MCP servers per domain  
3. **Later:** Real ERP adapters behind same MCP contracts; shadow traffic compare v1 vs v2  
