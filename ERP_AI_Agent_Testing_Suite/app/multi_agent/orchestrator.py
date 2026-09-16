#!/usr/bin/env python3
"""
Multi-Agent Orchestrator + MCP façade for ERP AI Agent v2 (RamanaSoft).

Modes:
  - single: only one domain agent runs (procurement | inventory | sales | finance)
  - multi:  orchestrator routes; complex prompts can run agents in parallel
"""

from __future__ import annotations

import json
import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent_core import (
    INVENTORY, PREFERRED, VENDORS, PRICES, CUSTOMERS, SALES_PRICES,
    OPEN_VINV, OPEN_CINV, LIMIT, ITEMS,
)

LOG_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ids(request_id: Optional[str] = None) -> Dict[str, str]:
    rid = request_id or str(uuid.uuid4())
    return {"request_id": rid, "trace_id": rid.replace("-", "")[:16]}


def log_event(event: Dict[str, Any]) -> None:
    event.setdefault("ts", _now())
    line = json.dumps(event, ensure_ascii=False)
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        day = datetime.now(timezone.utc).strftime("%Y%m%d")
        with open(LOG_DIR / f"agent_{day}.log", "a", encoding="utf-8") as f:
            f.write(line + "\n")
        if event.get("level") == "ERROR":
            with open(LOG_DIR / "errors.log", "a", encoding="utf-8") as f:
                f.write(line + "\n")
    except OSError:
        pass


class MCPError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def mcp_inventory_lookup(part: str) -> Dict[str, Any]:
    if not part or not isinstance(part, str):
        raise MCPError("MCP_VALIDATION_ERROR", "part must be non-empty string")
    inv = INVENTORY.get(part)
    if not inv:
        raise MCPError("NOT_FOUND", f"Part '{part}' not found")
    return {"part": part, **inv}


def mcp_preferred_supplier(part: str) -> Dict[str, Any]:
    vid = PREFERRED.get(part)
    if not vid:
        raise MCPError("NOT_FOUND", f"No preferred supplier for {part}")
    return {"part": part, "vendor_id": vid, "name": VENDORS.get(vid, vid)}


def mcp_contract_price(vendor_id: str, part: str) -> Dict[str, Any]:
    price = PRICES.get((vendor_id, part))
    if price is None:
        raise MCPError("NOT_FOUND", "No contract price")
    return {"vendor_id": vendor_id, "part": part, "unit_price": price}


def mcp_create_draft_po(vendor_id: str, part: str, qty: int, unit_price: float) -> Dict[str, Any]:
    if qty <= 0:
        raise MCPError("MCP_VALIDATION_ERROR", "qty must be positive")
    total = round(qty * unit_price, 2)
    if total > LIMIT:
        raise MCPError("APPROVAL_LIMIT_EXCEEDED", f"Total {total} exceeds limit {LIMIT}")
    po_id = f"PO-2026-{abs(hash(part + str(qty) + vendor_id)) % 9000 + 1000}"
    return {
        "po_id": po_id, "type": "DRAFT", "vendor_id": vendor_id, "part": part,
        "qty": qty, "unit_price": unit_price, "total": total,
        "note": "Draft only – human approval required",
    }


def mcp_customer_lookup(customer_id: str) -> Dict[str, Any]:
    c = CUSTOMERS.get(customer_id)
    if not c:
        raise MCPError("NOT_FOUND", f"Customer {customer_id} not found")
    return {"customer_id": customer_id, **c}


def mcp_create_draft_so(customer_id: str, part: str, qty: int, unit_price: float) -> Dict[str, Any]:
    if qty <= 0:
        raise MCPError("MCP_VALIDATION_ERROR", "qty must be positive")
    c = CUSTOMERS.get(customer_id)
    if not c:
        raise MCPError("NOT_FOUND", "Invalid customer")
    total = round(qty * unit_price, 2)
    if c["open_ar"] + total > c["credit_limit"]:
        raise MCPError("CREDIT_LIMIT_EXCEEDED", "Credit limit exceeded")
    inv = INVENTORY.get(part)
    if not inv or inv["stock"] < qty:
        raise MCPError("INSUFFICIENT_STOCK", "Not enough stock")
    so_id = f"SO-2026-{abs(hash(customer_id + part + str(qty))) % 9000 + 1000}"
    return {
        "so_id": so_id, "type": "DRAFT", "customer_id": customer_id, "part": part,
        "qty": qty, "unit_price": unit_price, "total": total,
        "note": "Draft SO – human confirmation required",
    }


def mcp_list_vendor_invoices() -> Dict[str, Any]:
    return {"invoices": OPEN_VINV, "count": len(OPEN_VINV)}


def mcp_list_customer_invoices() -> Dict[str, Any]:
    return {"invoices": OPEN_CINV, "count": len(OPEN_CINV)}


MCP_TOOLS = {
    "inventory_lookup": ("inventory", mcp_inventory_lookup),
    "preferred_supplier": ("procurement", mcp_preferred_supplier),
    "contract_price": ("procurement", mcp_contract_price),
    "create_draft_po": ("procurement", mcp_create_draft_po),
    "customer_lookup": ("sales", mcp_customer_lookup),
    "create_draft_so": ("sales", mcp_create_draft_so),
    "list_open_vendor_invoices": ("finance", mcp_list_vendor_invoices),
    "list_open_customer_invoices": ("finance", mcp_list_customer_invoices),
}

DOMAIN_TOOLS = {
    "inventory": ["inventory_lookup"],
    "procurement": ["inventory_lookup", "preferred_supplier", "contract_price", "create_draft_po"],
    "sales": ["customer_lookup", "inventory_lookup", "create_draft_so"],
    "finance": ["list_open_vendor_invoices", "list_open_customer_invoices"],
}


def call_mcp(tool: str, args: Dict[str, Any], meta: Dict[str, str], allowed: Optional[List[str]] = None) -> Dict[str, Any]:
    span_id = f"span-{uuid.uuid4().hex[:8]}"
    t0 = time.time()
    server_agent = MCP_TOOLS.get(tool, (None, None))[0]
    fn = MCP_TOOLS.get(tool, (None, None))[1]
    base = {
        "request_id": meta["request_id"], "trace_id": meta["trace_id"],
        "span_id": span_id, "agent_id": server_agent or "unknown",
        "mcp_server": f"mcp://{server_agent}" if server_agent else None,
        "tool": tool, "event": "tool_call",
    }
    if allowed is not None and tool not in allowed:
        log_event({**base, "level": "ERROR", "status": "error", "error_code": "UNAUTHORIZED_TOOL"})
        return {
            "status": "error", "error_code": "UNAUTHORIZED_TOOL",
            "error_message": f"Tool {tool} not allowed in this agent mode",
            "span_id": span_id, "agent_id": server_agent, "latency_ms": 0,
        }
    if not fn:
        log_event({**base, "level": "ERROR", "status": "error", "error_code": "UNKNOWN_TOOL"})
        return {"status": "error", "error_code": "UNKNOWN_TOOL", "error_message": f"Unknown tool {tool}",
                "span_id": span_id, "agent_id": "unknown", "latency_ms": 0}
    try:
        result = fn(**args)
        latency = int((time.time() - t0) * 1000)
        log_event({**base, "level": "INFO", "status": "ok", "latency_ms": latency, "event": "tool_result"})
        return {"status": "ok", "data": result, "span_id": span_id, "agent_id": server_agent, "latency_ms": latency}
    except MCPError as e:
        latency = int((time.time() - t0) * 1000)
        log_event({
            **base, "level": "ERROR", "status": "error", "latency_ms": latency,
            "error_code": e.code, "error_message": e.message, "event": "tool_error",
        })
        return {
            "status": "error", "error_code": e.code, "error_message": e.message,
            "span_id": span_id, "agent_id": server_agent, "latency_ms": latency,
        }


def guardrail_pre(prompt: str, meta: Dict[str, str]) -> Optional[Dict[str, Any]]:
    pl = prompt.lower()
    span_id = f"span-{uuid.uuid4().hex[:8]}"
    blocked = None
    if any(k in pl for k in ["ignore previous", "ignore your", "system prompt", "jailbreak", "dan mode"]):
        blocked = "PROMPT_INJECTION"
    elif any(k in pl for k in ["final po", "release the po", "post payment", "pay the invoice", "approve the po"]):
        blocked = "AUTONOMY_VIOLATION"
    elif any(k in pl for k in ["other supplier", "all suppliers", "competitor price"]):
        blocked = "DATA_LEAKAGE_ATTEMPT"
    log_event({
        "level": "WARN" if blocked else "INFO",
        "request_id": meta["request_id"], "trace_id": meta["trace_id"],
        "span_id": span_id, "agent_id": "guardrail", "event": "pre_check",
        "status": "blocked" if blocked else "ok", "error_code": blocked,
    })
    if blocked:
        return {
            "status": "refused",
            "response": f"POLICY REFUSAL ({blocked}). This request violates safety or autonomy rules.",
            "agent_id": "guardrail", "span_id": span_id,
        }
    return None


def _extract_part(prompt: str) -> str:
    pl = prompt.lower()
    for p in ITEMS:
        if p.lower() in pl:
            return p
    m = re.search(r"(?:of|for|check|order|stock of)\s+([A-Za-z0-9\-]+)", prompt, re.I)
    return m.group(1) if m else "Widget-X"


def _extract_qty(prompt: str, default: int = 200) -> int:
    m = re.search(r"(\d+)\s*units?", prompt.lower())
    return int(m.group(1)) if m else default


def _extract_customer(prompt: str) -> str:
    pl = prompt.lower()
    for c in CUSTOMERS:
        if c.lower() in pl or CUSTOMERS[c]["name"].lower() in pl:
            return c
    return "CUS-5001"


def run_inventory_only(prompt: str, meta: Dict[str, str]) -> Dict[str, Any]:
    allowed = DOMAIN_TOOLS["inventory"]
    part = _extract_part(prompt)
    res = call_mcp("inventory_lookup", {"part": part}, meta, allowed)
    steps = [{"type": "tool", "name": "inventory", "input": {"part": part}, "output": res, "ts": _now()}]
    if res["status"] != "ok":
        return {"status": "error", "steps": steps, "message": res.get("error_message", "Inventory error"), "agents": ["inventory"]}
    d = res["data"]
    msg = f"[Inventory Agent] {part}: stock={d['stock']}, reorder_point={d['reorder_point']}, location={d.get('location')}"
    return {"status": "success", "steps": steps, "message": msg, "agents": ["inventory"], "data": d}


def run_procurement_only(prompt: str, meta: Dict[str, str]) -> Dict[str, Any]:
    allowed = DOMAIN_TOOLS["procurement"]
    part = _extract_part(prompt)
    qty = _extract_qty(prompt, 200)
    steps = []
    inv = call_mcp("inventory_lookup", {"part": part}, meta, allowed)
    steps.append({"type": "tool", "name": "inventory", "input": {"part": part}, "output": inv, "ts": _now()})
    if inv["status"] != "ok":
        return {"status": "error", "steps": steps, "message": inv.get("error_message"), "agents": ["procurement"]}
    data = inv["data"]
    if data["stock"] >= data["reorder_point"] and "force" not in prompt.lower():
        return {
            "status": "success", "steps": steps,
            "message": f"[Procurement Agent] Stock {data['stock']} >= reorder {data['reorder_point']}. No PO needed.",
            "agents": ["procurement"],
        }
    sup = call_mcp("preferred_supplier", {"part": part}, meta, allowed)
    steps.append({"type": "tool", "name": "procurement", "input": {"part": part}, "output": sup, "ts": _now()})
    if sup["status"] != "ok":
        return {"status": "error", "steps": steps, "message": sup.get("error_message"), "agents": ["procurement"]}
    price = call_mcp("contract_price", {"vendor_id": sup["data"]["vendor_id"], "part": part}, meta, allowed)
    steps.append({"type": "tool", "name": "procurement", "input": {}, "output": price, "ts": _now()})
    if price["status"] != "ok":
        return {"status": "error", "steps": steps, "message": price.get("error_message"), "agents": ["procurement"]}
    unit = price["data"]["unit_price"]
    last = data.get("last_price")
    if last and unit > last * 1.20:
        return {
            "status": "escalated", "steps": steps,
            "message": f"[Procurement Agent] Price spike ${unit} >20% above last ${last}. Escalating to human.",
            "agents": ["procurement"],
        }
    po = call_mcp("create_draft_po", {
        "vendor_id": sup["data"]["vendor_id"], "part": part, "qty": qty, "unit_price": unit,
    }, meta, allowed)
    steps.append({"type": "tool", "name": "procurement", "input": {"qty": qty}, "output": po, "ts": _now()})
    if po["status"] != "ok":
        return {
            "status": "error", "steps": steps,
            "message": f"[Procurement Agent] {po.get('error_message')}",
            "agents": ["procurement"], "error_code": po.get("error_code"),
        }
    return {
        "status": "success", "steps": steps,
        "message": (
            f"[Procurement Agent] Draft PO {po['data']['po_id']}: "
            f"{part} x{qty} @ ${unit:.2f} = ${po['data']['total']:,.2f}\n"
            f"Status: DRAFT – human approval required."
        ),
        "agents": ["procurement"], "data": po["data"],
    }


def run_sales_only(prompt: str, meta: Dict[str, str]) -> Dict[str, Any]:
    allowed = DOMAIN_TOOLS["sales"]
    cust = _extract_customer(prompt)
    part = _extract_part(prompt)
    qty = _extract_qty(prompt, 5)
    steps = []
    c = call_mcp("customer_lookup", {"customer_id": cust}, meta, allowed)
    steps.append({"type": "tool", "name": "sales", "input": {"customer_id": cust}, "output": c, "ts": _now()})
    if c["status"] != "ok":
        return {"status": "error", "steps": steps, "message": c.get("error_message"), "agents": ["sales"]}
    inv = call_mcp("inventory_lookup", {"part": part}, meta, allowed)
    steps.append({"type": "tool", "name": "sales", "input": {"part": part}, "output": inv, "ts": _now()})
    unit = SALES_PRICES.get(part)
    if unit is None:
        return {"status": "error", "steps": steps, "message": "No sales price", "agents": ["sales"]}
    so = call_mcp("create_draft_so", {
        "customer_id": cust, "part": part, "qty": qty, "unit_price": unit,
    }, meta, allowed)
    steps.append({"type": "tool", "name": "sales", "input": {"qty": qty}, "output": so, "ts": _now()})
    if so["status"] != "ok":
        return {
            "status": "escalated", "steps": steps,
            "message": f"[Sales Agent] {so.get('error_message')}",
            "agents": ["sales"], "error_code": so.get("error_code"),
        }
    return {
        "status": "success", "steps": steps,
        "message": (
            f"[Sales Agent] Draft SO {so['data']['so_id']}: {cust} / {part} x{qty} = ${so['data']['total']:,.2f}\n"
            f"DRAFT – human confirmation required."
        ),
        "agents": ["sales"], "data": so["data"],
    }


def run_finance_only(prompt: str, meta: Dict[str, str]) -> Dict[str, Any]:
    allowed = DOMAIN_TOOLS["finance"]
    kind = "customer" if "customer" in prompt.lower() else "vendor"
    tool = "list_open_customer_invoices" if kind == "customer" else "list_open_vendor_invoices"
    res = call_mcp(tool, {}, meta, allowed)
    steps = [{"type": "tool", "name": "finance", "input": {"kind": kind}, "output": res, "ts": _now()}]
    if res["status"] != "ok":
        return {"status": "error", "steps": steps, "message": res.get("error_message"), "agents": ["finance"]}
    return {
        "status": "success", "steps": steps,
        "message": f"[Finance Agent] Open {kind} invoices ({res['data']['count']}):\n" + json.dumps(res["data"]["invoices"], indent=2),
        "agents": ["finance"], "data": res["data"],
    }


SINGLE_RUNNERS = {
    "inventory": run_inventory_only,
    "procurement": run_procurement_only,
    "sales": run_sales_only,
    "finance": run_finance_only,
}


def detect_intents(prompt: str) -> List[str]:
    pl = prompt.lower()
    intents = []
    sales_cues = ["sales order", "create so", "draft so", "sell to", "customer order", "order for customer"]
    fin_cues = ["invoice", "open ar", "open ap", "overdue", "receivable", "payable"]
    inv_cues = ["stock", "inventory", "on hand", "reorder", "warehouse"]
    proc_cues = ["purchase", "draft po", "create po", "replenish", "supplier", "vendor", "buy"]

    if any(k in pl for k in sales_cues) or (re.search(r"cus-\d+", pl) and "order" in pl):
        intents.append("sales")
    if any(k in pl for k in fin_cues):
        intents.append("finance")
    if any(k in pl for k in inv_cues) and not any(k in pl for k in proc_cues + sales_cues):
        intents.append("inventory")
    if any(k in pl for k in proc_cues) or ("low" in pl and any(p.lower() in pl for p in ITEMS)):
        intents.append("procurement")
    if any(k in pl for k in sales_cues) and any(k in pl for k in ["restock", "replenish", "also buy", "also order", "purchase"]):
        if "procurement" not in intents:
            intents.append("procurement")
        if "sales" not in intents:
            intents.append("sales")
    if not intents:
        intents = ["procurement"]
    seen = set()
    out = []
    for i in intents:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def _pack(meta, prompt, response, status, steps, agents, mode: str) -> Dict[str, Any]:
    return {
        "request_id": meta["request_id"],
        "trace_id": meta["trace_id"],
        "prompt": prompt,
        "response": response,
        "mode": mode,
        "steps": steps,
        "status": status,
        "created_at": _now(),
        "link": f"?request_id={meta['request_id']}",
        "agents_involved": agents,
        "error_logs_path": str(LOG_DIR / "errors.log"),
    }


def run_single_agent(prompt: str, domain: str, request_id: Optional[str] = None) -> Dict[str, Any]:
    meta = _ids(request_id)
    domain = domain.lower().strip()
    steps: List[Dict] = []
    log_event({
        "level": "INFO", "event": "request_start", "mode": "single", "domain": domain,
        "request_id": meta["request_id"], "trace_id": meta["trace_id"], "agent_id": "orchestrator",
        "prompt_preview": prompt[:200],
    })
    blocked = guardrail_pre(prompt, meta)
    if blocked:
        steps.append({"type": "guardrail", "name": "pre_check", "input": prompt[:200], "output": blocked, "ts": _now()})
        return _pack(meta, prompt, blocked["response"], "refused", steps, ["guardrail"], mode=f"single:{domain}")

    if domain not in SINGLE_RUNNERS:
        return _pack(meta, prompt, f"Unknown domain agent '{domain}'. Choose: inventory, procurement, sales, finance.",
                     "error", steps, ["orchestrator"], mode=f"single:{domain}")

    result = SINGLE_RUNNERS[domain](prompt, meta)
    steps.extend(result.get("steps", []))
    status = result.get("status", "success")
    log_event({
        "level": "INFO", "event": "request_end", "status": status, "mode": "single", "domain": domain,
        "request_id": meta["request_id"], "trace_id": meta["trace_id"], "agent_id": "orchestrator",
    })
    return _pack(meta, prompt, result.get("message", ""), status, steps, result.get("agents", [domain]), mode=f"single:{domain}")


def run_multi_agent(prompt: str, request_id: Optional[str] = None) -> Dict[str, Any]:
    meta = _ids(request_id)
    steps: List[Dict] = []
    log_event({
        "level": "INFO", "event": "request_start", "mode": "multi",
        "request_id": meta["request_id"], "trace_id": meta["trace_id"], "agent_id": "orchestrator",
        "prompt_preview": prompt[:200],
    })

    blocked = guardrail_pre(prompt, meta)
    if blocked:
        steps.append({"type": "guardrail", "name": "pre_check", "input": prompt[:200], "output": blocked, "ts": _now()})
        return _pack(meta, prompt, blocked["response"], "refused", steps, ["guardrail"], mode="multi-agent")

    intents = detect_intents(prompt)
    steps.append({
        "type": "orchestrator", "name": "route_intent",
        "input": prompt[:160], "output": {"intents": intents, "parallel": len(intents) > 1},
        "ts": _now(),
    })
    log_event({
        "level": "INFO", "event": "route", "intents": intents,
        "request_id": meta["request_id"], "trace_id": meta["trace_id"], "agent_id": "orchestrator",
    })

    agents_involved = ["orchestrator", "guardrail"]
    messages = []
    statuses = []

    def _run_domain(domain: str):
        return domain, SINGLE_RUNNERS[domain](prompt, meta)

    if len(intents) > 1:
        with ThreadPoolExecutor(max_workers=min(4, len(intents))) as ex:
            futures = {ex.submit(_run_domain, d): d for d in intents}
            for fut in as_completed(futures):
                domain, result = fut.result()
                agents_involved.append(domain)
                steps.extend(result.get("steps", []))
                messages.append(result.get("message", ""))
                statuses.append(result.get("status", "success"))
                steps.append({
                    "type": "orchestrator", "name": f"merge_{domain}",
                    "input": {"domain": domain}, "output": {"status": result.get("status")},
                    "ts": _now(),
                })
    else:
        domain = intents[0]
        result = SINGLE_RUNNERS[domain](prompt, meta)
        agents_involved.append(domain)
        steps.extend(result.get("steps", []))
        messages.append(result.get("message", ""))
        statuses.append(result.get("status", "success"))

    if any(s == "refused" for s in statuses):
        status = "refused"
    elif any(s == "error" for s in statuses):
        status = "error"
    elif any(s == "escalated" for s in statuses):
        status = "escalated"
    else:
        status = "success"

    header = f"Multi-Agent run | intents={intents} | parallel={len(intents) > 1}\n\n"
    response = header + "\n\n".join(messages)

    log_event({
        "level": "INFO", "event": "request_end", "status": status, "mode": "multi",
        "request_id": meta["request_id"], "trace_id": meta["trace_id"],
        "agent_id": "orchestrator", "agents_involved": agents_involved,
    })
    return _pack(meta, prompt, response, status, steps, agents_involved, mode="multi-agent")


def run_agent_v2(
    prompt: str,
    architecture: str = "multi",
    domain: str = "procurement",
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    if architecture == "single":
        return run_single_agent(prompt, domain, request_id)
    return run_multi_agent(prompt, request_id)


if __name__ == "__main__":
    r = run_single_agent("Create draft PO for Widget-X 200 units", "procurement")
    print("SINGLE", r["mode"], r["status"], r["agents_involved"])
    r2 = run_multi_agent(
        "Create draft sales order for CUS-5001 for 5 units of Widget-X and also replenish stock with a draft PO for 200 units"
    )
    print("MULTI", r2["mode"], r2["status"], r2["agents_involved"])
