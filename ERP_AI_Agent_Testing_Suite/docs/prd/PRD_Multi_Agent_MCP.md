# Product Requirements Document (PRD)
## Multi-Agent ERP Assistant with Model Context Protocol (MCP)

**Product:** ERP AI Agent Testing Suite – Multi-Agent + MCP Evolution  
**Organization:** Ramana Soft Consulting Services  
**Version:** 2.0  
**Status:** Approved for design & test expansion  

---

## 1. Executive Summary

The current single-agent ERP assistant handles Inventory, Procurement, Sales, and Finance in one monolithic planner. As scope grows, this creates:

- Long, fragile prompts and tool lists  
- Mixed responsibility (harder to test and audit)  
- Weak isolation of blast radius when a tool or policy fails  
- Difficulty plugging in new enterprise systems  

**v2 introduces a multi-agent architecture** where specialized agents collaborate, and **MCP (Model Context Protocol)** standardizes how agents discover and call tools/data sources.

---

## 2. Problem Statement

| Pain (Single Agent) | Impact |
|---------------------|--------|
| One agent owns 12+ tools across domains | High regression risk; hard to reason about failures |
| No clear handoff between procurement vs sales vs finance | Escalation and policy bugs |
| Custom tool adapters per system | Slow integration of new ERP modules / APIs |
| Traces mix all domains | Debugging and compliance reviews are expensive |
| Limited parallel work | Latency grows with sequential tool chains |

---

## 3. Goals

1. **Decompose** the assistant into specialized agents with clear contracts.  
2. **Adopt MCP** so tools and data sources are discoverable, schema-validated, and swappable.  
3. **Preserve** existing safety gates (draft-only, limits, injection resistance).  
4. **Enable** independent testing of each agent + integration testing of orchestrated flows.  
5. **Improve** observability: per-agent spans under a single **trace_id** / **request_id**.  

### Non-Goals (v2)
- Full autonomous release of POs/SOs without human approval  
- Payment posting or GL journal creation  
- Replacing the ERP system of record  

---

## 4. Why Multi-Agent?

| Benefit | Description |
|---------|-------------|
| Separation of concerns | Inventory Agent never creates SOs; Finance Agent is read-only by design |
| Smaller prompts / toolsets | Each agent has 3–5 tools → higher tool-selection accuracy |
| Independent scaling & ownership | Teams can own Procurement Agent tests without touching Sales |
| Parallelism | Orchestrator can fan-out inventory + credit checks |
| Safer blast radius | Compromised sales tools cannot call procurement write tools |
| Clearer evals | Per-agent metrics + end-to-end orchestration metrics |

---

## 5. Why MCP (Model Context Protocol)?

MCP provides a **standard protocol** for:

- **Tool discovery** – agents list available tools and JSON schemas  
- **Typed invocation** – arguments validated before execution  
- **Resource access** – read-only context (policies, catalogs) as MCP resources  
- **Transport flexibility** – local stdio, HTTP/SSE, or gateway  

### Need in this project

| Need | MCP capability |
|------|----------------|
| Stable contract between Orchestrator and domain agents | MCP tools with versioned schemas |
| Plug mock ERP now, real SAP/Oracle later | Swap MCP server implementation; agent code unchanged |
| Audit who called what | MCP session + tool call metadata in traces |
| Prevent free-form “stringly typed” tool calls | Schema validation at MCP boundary |
| Multi-team tool ownership | Each domain publishes its own MCP server |

---

## 6. Functional Requirements

### 6.1 Agents

| Agent ID | Responsibility | Write actions | MCP Server |
|----------|----------------|---------------|------------|
| **Orchestrator** | Intent routing, plan, aggregate results, user response | None (coordinates only) | `mcp://orchestrator` |
| **InventoryAgent** | Stock, locations, reorder signals | None (read) | `mcp://inventory` |
| **ProcurementAgent** | Preferred vendor, contract price, **draft PO** | Draft PO only | `mcp://procurement` |
| **SalesAgent** | Customer, ATP, credit, **draft SO** | Draft SO only | `mcp://sales` |
| **FinanceAgent** | Open AR/AP invoices, status | **None** (read-only) | `mcp://finance` |
| **GuardrailAgent** | Injection/leakage/policy checks (pre/post) | None | `mcp://guardrails` |

### 6.2 Core user journeys (multi-agent)

1. **Replenishment:** User → Orchestrator → Inventory → Procurement → (optional Guardrail) → response  
2. **Order capture:** User → Orchestrator → Sales (+ Inventory ATP) → Guardrail → response  
3. **AR/AP inquiry:** User → Orchestrator → Finance → response  
4. **Cross-domain:** “Can we sell 50 Widget-X to CUS-5001 and restock if needed?” → Sales + Inventory + optional Procurement plan  

### 6.3 Non-functional

- Every request has **request_id** (external) and **trace_id** (internal correlation).  
- Each agent span logs: agent_id, tool, latency_ms, status, error_code.  
- P95 end-to-end latency target documented in metrics (env-specific).  
- MCP schema validation failures → structured error, no silent partial writes.  

---

## 7. Success Criteria

| ID | Criterion | Target |
|----|-----------|--------|
| SC-1 | Orchestrator routes to correct agent(s) | ≥ 95% on golden set |
| SC-2 | Domain agent task success (own scope) | ≥ 90% |
| SC-3 | No cross-domain unauthorized tool use | 100% |
| SC-4 | MCP schema validation on all tool calls | 100% |
| SC-5 | Red-team resistance (system-level) | ≥ 99% |
| SC-6 | Full trace with request_id + per-agent spans | 100% of requests |
| SC-7 | Existing single-agent Blue cases still pass via orchestration | ≥ 95% |

---

## 8. Out of Scope / Risks

- Risk: Orchestrator mis-routing → mitigate with routing eval set + fallback clarify.  
- Risk: MCP server down → circuit breaker + user-visible degradation message.  
- Risk: Multi-agent cost/latency → cache read tools; parallelize independent calls.  

---

## 9. Dependencies

- Existing mock ERP data and policies (v1)  
- MCP-compatible runtime (reference SDK or internal gateway)  
- Logging backend supporting structured JSON logs + trace_id  

---

## 10. Approval

| Role | Name | Sign-off |
|------|------|----------|
| Product | — | |
| Architecture | — | |
| QA / Gen AI Testing | — | |
| Security | — | |
