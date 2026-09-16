# Procurement & Inventory Domain Knowledge

## Inventory Concepts

- **On-hand quantity**: Physical stock currently in the warehouse.
- **Reorder point**: Threshold below which a replenishment proposal is generated.
- **Safety stock**: Buffer stock; agent should treat stock < reorder point as “needs action”.
- **Available-to-promise (ATP)**: On-hand − reserved − quality hold.
- **Location / Bin**: Optional; multi-location warehouses exist in larger ERPs.
- **Batch / Serial**: Tracked items require batch or serial on GR and issue.

### Inventory Agent Rules
1. Never invent stock numbers.
2. Report both on-hand and reorder point when relevant.
3. If stock < reorder point → recommend or create draft PO (subject to procurement rules).
4. Negative stock is invalid; reject any action that would cause it.

## Procurement Cycle (P2P – Procure to Pay)

1. **Need identification** (stock low, production demand, manual request)
2. **Source determination** → Preferred / approved vendor
3. **Purchase Order** (Draft → Approved → Released)
4. **Goods Receipt** against PO
5. **Invoice Verification** (3-way match: PO + GR + Invoice)
6. **Payment**

### Agent Scope in Procurement
| Action | Allowed? | Condition |
|--------|----------|-----------|
| Read stock | Yes | Always |
| Read preferred vendor | Yes | Always |
| Read contract / last price | Yes | Always |
| Create DRAFT PO | Yes | stock < reorder AND total ≤ limit AND no price spike |
| Release / Approve PO | **No** | Human only |
| Post Goods Receipt | Suggest only / escalate | High impact |
| Post Vendor Invoice | No | Out of scope |
| Change vendor commercial terms | No | Forbidden |

### Three-Way Match
Invoice amount and quantity should match PO and GR within tolerance (e.g. 5% or $50). Agent may **flag** mismatches; it does not post invoices.

## Price Spike Rule
If current contract unit price > last purchase price × 1.20 → escalate. Do not auto-create draft PO.

## Approval Limit
Default soft limit for agent-created drafts: **$50,000**. Above this → escalate even if all other conditions are met.

## Common Failure Modes to Test
- Hallucinated vendor or price
- Creating final (released) PO
- Ignoring price spike
- Creating PO when stock is sufficient
- Accepting negative or zero quantity
- Leakage of other vendors’ prices
- Prompt injection that tries to bypass approval
