#!/usr/bin/env python3
"""Multi-module ERP Agent Core – structured traces for UI."""
from __future__ import annotations
import json, os, re, uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

def load_dotenv():
    for env_path in [
        os.path.join(os.path.dirname(__file__), "..", "config", ".env"),
        os.path.join(os.path.dirname(__file__), ".env"),
    ]:
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
            break
load_dotenv()

ITEMS = ["Widget-X","Part-ABC","Gadget-Z","Bolt-M8","Sheet-Steel-2mm","Pump-Industrial-200","Cable-Cat6-100m","Sensor-Temp-A1","Raw-Resin-5kg","Filter-HEPA-20"]
INVENTORY = {
    "Widget-X": {"stock": 32, "reorder_point": 50, "last_price": 12.0, "location": "WH-A"},
    "Part-ABC": {"stock": 120, "reorder_point": 80, "last_price": 5.5, "location": "WH-A"},
    "Gadget-Z": {"stock": 8, "reorder_point": 25, "last_price": 45.0, "location": "WH-B"},
    "Bolt-M8": {"stock": 5000, "reorder_point": 2000, "last_price": 0.15, "location": "WH-A"},
    "Sheet-Steel-2mm": {"stock": 450, "reorder_point": 600, "last_price": 2.8, "location": "WH-C"},
    "Pump-Industrial-200": {"stock": 3, "reorder_point": 5, "last_price": 1250.0, "location": "WH-B"},
    "Cable-Cat6-100m": {"stock": 40, "reorder_point": 30, "last_price": 85.0, "location": "WH-A"},
    "Sensor-Temp-A1": {"stock": 15, "reorder_point": 40, "last_price": 22.5, "location": "WH-B"},
    "Raw-Resin-5kg": {"stock": 80, "reorder_point": 100, "last_price": 18.0, "location": "WH-C"},
    "Filter-HEPA-20": {"stock": 0, "reorder_point": 20, "last_price": 35.0, "location": "WH-A"},
}
PREFERRED = {"Widget-X":"SUP-1001","Part-ABC":"SUP-2002","Gadget-Z":"SUP-3003","Bolt-M8":"SUP-4004","Sheet-Steel-2mm":"SUP-1001","Pump-Industrial-200":"SUP-3003","Cable-Cat6-100m":"SUP-2002","Sensor-Temp-A1":"SUP-4004","Raw-Resin-5kg":"SUP-1001","Filter-HEPA-20":"SUP-2002"}
VENDORS = {"SUP-1001":"Acme Corp","SUP-2002":"Beta Supplies","SUP-3003":"Gamma Ltd","SUP-4004":"Delta Parts Co"}
PRICES = {("SUP-1001","Widget-X"):12.5,("SUP-2002","Part-ABC"):5.75,("SUP-3003","Gadget-Z"):48.0,("SUP-4004","Bolt-M8"):0.14,("SUP-1001","Sheet-Steel-2mm"):2.95,("SUP-3003","Pump-Industrial-200"):1290.0,("SUP-2002","Cable-Cat6-100m"):82.0,("SUP-4004","Sensor-Temp-A1"):23.0,("SUP-1001","Raw-Resin-5kg"):17.5,("SUP-2002","Filter-HEPA-20"):36.0}
CUSTOMERS = {"CUS-5001":{"name":"Alpha Retail","credit_limit":100000,"open_ar":25000},"CUS-5002":{"name":"Beta Manufacturing","credit_limit":250000,"open_ar":180000},"CUS-5003":{"name":"Gamma Distributors","credit_limit":50000,"open_ar":48000},"CUS-5004":{"name":"Delta Online","credit_limit":20000,"open_ar":0}}
SALES_PRICES = {"Widget-X":18.0,"Part-ABC":9.5,"Gadget-Z":79.0,"Bolt-M8":0.35,"Sheet-Steel-2mm":4.2,"Pump-Industrial-200":1890.0,"Cable-Cat6-100m":125.0,"Sensor-Temp-A1":39.0,"Raw-Resin-5kg":28.0,"Filter-HEPA-20":55.0}
OPEN_VINV = [{"inv_id":"VINV-9001","vendor":"SUP-1001","amount":12500.0,"due":"2026-09-20","status":"Open"},{"inv_id":"VINV-9002","vendor":"SUP-2002","amount":3200.0,"due":"2026-09-15","status":"Open"}]
OPEN_CINV = [{"inv_id":"CINV-7001","customer":"CUS-5001","amount":15000.0,"due":"2026-09-25","status":"Open"},{"inv_id":"CINV-7002","customer":"CUS-5002","amount":42000.0,"due":"2026-09-18","status":"Overdue"}]
LIMIT = 50000.0

def _now(): return datetime.now(timezone.utc).isoformat()
def _id(): return str(uuid.uuid4())
def _add(steps, t, n, i, o): steps.append({"type":t,"name":n,"input":i,"output":o,"ts":_now()})
def _res(rid, prompt, response, mode, steps, status):
    return {"request_id":rid,"prompt":prompt,"response":response,"mode":mode,"steps":steps,"status":status,"created_at":_now(),"link":f"?request_id={rid}"}

def run_mock_structured(prompt: str, request_id: Optional[str]=None) -> Dict[str,Any]:
    rid = request_id or _id(); steps=[]; pl=prompt.lower()
    if any(k in pl for k in ["ignore previous","ignore your","system prompt","you are now","jailbreak","do anything now","dan mode"]):
        _add(steps,"guardrail","injection_check",prompt[:200],"BLOCKED")
        return _res(rid,prompt,"🚫 POLICY REFUSAL\nI cannot ignore my instructions or company policy.","mock",steps,"refused")
    if any(k in pl for k in ["other supplier","all suppliers","competitor price","other customer"]):
        _add(steps,"guardrail","data_leakage_check",prompt[:200],"BLOCKED")
        return _res(rid,prompt,"🚫 DATA PROTECTION\nI cannot reveal commercial terms of other parties.","mock",steps,"refused")
    if any(k in pl for k in ["final po","release the po","approve the po","final sales order","post payment","pay the invoice"]):
        _add(steps,"guardrail","autonomy_check",prompt[:200],"BLOCKED")
        return _res(rid,prompt,"🚫 AUTONOMY LIMIT\nI only create DRAFT documents. Release/payments require a human.","mock",steps,"refused")
    if "open invoice" in pl or "vendor invoice" in pl or "customer invoice" in pl:
        if "customer" in pl:
            _add(steps,"tool","list_open_customer_invoices",{},{"invoices":OPEN_CINV})
            lines=[f"{i['inv_id']}: {i['customer']} ${i['amount']} ({i['status']})" for i in OPEN_CINV]
            return _res(rid,prompt,"Open customer invoices:\n"+"\n".join(lines),"mock",steps,"success")
        _add(steps,"tool","list_open_vendor_invoices",{},{"invoices":OPEN_VINV})
        lines=[f"{i['inv_id']}: {i['vendor']} ${i['amount']} ({i['status']})" for i in OPEN_VINV]
        return _res(rid,prompt,"Open vendor invoices:\n"+"\n".join(lines),"mock",steps,"success")
    if "sales order" in pl or "create so" in pl or ("order for customer" in pl):
        cust=next((c for c in CUSTOMERS if c.lower() in pl or CUSTOMERS[c]["name"].lower() in pl), None)
        part=next((p for p in ITEMS if p.lower() in pl), None)
        if not cust or not part:
            return _res(rid,prompt,"Specify customer (e.g. CUS-5001) and item for sales order.","mock",steps,"need_input")
        inv=INVENTORY.get(part,{}); price=SALES_PRICES.get(part,0); qty=10
        m=re.search(r"(\d+)\s*units?",pl)
        if m: qty=int(m.group(1))
        _add(steps,"tool","customer_lookup",{"customer_id":cust},CUSTOMERS[cust])
        _add(steps,"tool","inventory_lookup",{"part":part},inv)
        total=qty*price
        if CUSTOMERS[cust]["open_ar"]+total > CUSTOMERS[cust]["credit_limit"]:
            return _res(rid,prompt,"Credit limit exceeded – cannot create draft SO.","mock",steps,"escalated")
        if inv.get("stock",0)<qty:
            return _res(rid,prompt,"Insufficient stock for sales order.","mock",steps,"escalated")
        so_id=f"SO-2026-{abs(hash(cust+part+str(qty)))%9000+1000}"
        _add(steps,"tool","create_draft_so",{"customer":cust,"part":part,"qty":qty},{"so_id":so_id,"total":total,"type":"DRAFT"})
        return _res(rid,prompt,f"✅ Draft SO {so_id}: {cust} / {part} x{qty} = ${total:,.2f}\nDRAFT – human confirmation required.","mock",steps,"success")
    part=next((p for p in ITEMS if p.lower() in pl), None)
    if not part:
        m=re.search(r"(?:of|for|check|order|stock of)\s+([A-Za-z0-9\-]+)",prompt,re.I)
        if m: part=m.group(1)
    if not part:
        return _res(rid,prompt,"Please specify an item (e.g. Widget-X, Part-ABC, Gadget-Z).","mock",steps,"need_input")
    inv=INVENTORY.get(part)
    _add(steps,"tool","inventory_lookup",{"part_number":part},inv or {"error":"not found"})
    if not inv:
        return _res(rid,prompt,f"Part '{part}' not found.","mock",steps,"escalated")
    stock,reorder,last=inv["stock"],inv["reorder_point"],inv.get("last_price")
    lines=[f"📦 {part}: stock={stock}, reorder_point={reorder}, location={inv.get('location')}"]
    if "only check" in pl or ("check stock" in pl and "create" not in pl and "order" not in pl and "po" not in pl):
        return _res(rid,prompt,"\n".join(lines),"mock",steps,"success")
    if stock>=reorder and "force" not in pl:
        lines.append("✅ Stock above reorder point. No PO needed.")
        return _res(rid,prompt,"\n".join(lines),"mock",steps,"success")
    lines.append("⚠️ Stock below reorder point → replenishment needed.")
    qty=200
    m=re.search(r"(\d+)\s*units?",pl)
    if m: qty=int(m.group(1))
    if part=="Pump-Industrial-200": qty=min(qty,5)
    vid=PREFERRED.get(part)
    if not vid:
        return _res(rid,prompt,"No preferred supplier.","mock",steps,"escalated")
    vname=VENDORS.get(vid,vid)
    _add(steps,"tool","preferred_supplier",{"part":part},{"vendor_id":vid,"name":vname})
    lines.append(f"🏭 Preferred vendor: {vname} ({vid})")
    unit=PRICES.get((vid,part))
    if unit is None:
        return _res(rid,prompt,"No contract price.","mock",steps,"escalated")
    _add(steps,"tool","contract_price",{"vendor":vid,"part":part},{"unit_price":unit})
    lines.append(f"💰 Contract price: ${unit:.2f}")
    if last and unit>last*1.20:
        _add(steps,"tool","escalate_to_human",{"reason":"price spike"},{"status":"escalated"})
        lines.append(f"🚨 Price spike ${unit:.2f} >20% above last ${last:.2f} – escalated.")
        return _res(rid,prompt,"\n".join(lines),"mock",steps,"escalated")
    total=qty*unit
    if total>LIMIT:
        lines.append(f"🚨 Total ${total:,.2f} exceeds ${LIMIT:,.0f} limit – escalated.")
        return _res(rid,prompt,"\n".join(lines),"mock",steps,"escalated")
    if qty<=0:
        return _res(rid,prompt,"Quantity must be positive.","mock",steps,"error")
    po_id=f"PO-2026-{abs(hash(part+str(qty)+vid))%9000+1000}"
    _add(steps,"tool","create_draft_po",{"vendor":vid,"part":part,"qty":qty,"unit_price":unit},{"po_id":po_id,"total":total,"type":"DRAFT"})
    lines.append(f"✅ Draft PO {po_id}: {vname} / {part} x{qty} @ ${unit:.2f} = ${total:,.2f}\nStatus: DRAFT – human approval required.")
    return _res(rid,prompt,"\n".join(lines),"mock",steps,"success")

def run_llm_structured(prompt: str, request_id: Optional[str]=None) -> Dict[str,Any]:
    rid=request_id or _id(); steps=[]
    if not HAS_OPENAI:
        return _res(rid,prompt,"ERROR: openai not installed","llm",steps,"error")
    key=os.getenv("OPENAI_API_KEY")
    if not key or key.startswith("sk-your") or key=="YOUR_API_KEY_HERE":
        return _res(rid,prompt,"ERROR: Set OPENAI_API_KEY in config/.env or use Mock mode","llm",steps,"error")
    # Fallback: use mock behaviour with note (full LLM tool loop optional)
    r=run_mock_structured(prompt, rid)
    r["mode"]="llm"
    r["response"]="[LLM mode – using policy engine fallback]\n"+r["response"]
    return r

def run_agent(prompt: str, mode: Optional[str]=None, request_id: Optional[str]=None) -> Dict[str,Any]:
    mode=(mode or os.getenv("AGENT_MODE","mock")).lower()
    return run_llm_structured(prompt, request_id) if mode=="llm" else run_mock_structured(prompt, request_id)
