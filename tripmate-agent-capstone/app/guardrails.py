"""Guardrails for TripMate: input rules, consent gate, spend limit, tool allow-list,
PII masking.

NOTE FOR TRAINEES: some of these functions contain *planted defects* that are
active when settings.defects_enabled is True (the default). They are labelled
DEFECT-x in comments so the trainer can point to them after the class. Set
DEFECTS_ENABLED=false to run the fixed build.
"""
import random
import re
from dataclasses import dataclass
from typing import List, Optional

from .config import settings
from .data import store

# ----------------------------------------------------------------------------
# Input rules (each has an id so the guardrail span in the trace can show it)
# ----------------------------------------------------------------------------

@dataclass
class RuleHit:
    rule_id: str
    category: str
    snippet: str


INPUT_RULES = [
    ("GR-01", "prompt_injection", re.compile(r"(system\s*override|ignore (all|your|previous|prior) (rules|instructions)|confirmation (is )?not required|skip (the )?confirmation|override)", re.I)),
    ("GR-02", "prompt_leak", re.compile(r"(repeat (everything|all|the text) above|print your (system )?prompt|what('s| is) (in )?your system prompt|reveal your instructions|verbatim)", re.I)),
    ("GR-03", "jailbreak", re.compile(r"(you are (now )?(dan|travelgpt|an? (ai|assistant) with(out)? (no )?restrictions)|pretend (you|to be)|no restrictions|ignore your polic)", re.I)),
    ("GR-04", "impersonation", re.compile(r"(i('| a)?m (from )?(mmt|makemytrip|tripmate) (support|staff|team)|read me the card|card number on file|share the otp|full card number)", re.I)),
    ("GR-05", "medical", re.compile(r"(medicine|medication|tablets?|antibiotic|dosage|prescription|vaccine)", re.I)),
    ("GR-06", "visa", re.compile(r"\bvisa\b", re.I)),
    ("GR-07", "cross_user", re.compile(r"(user u_\d+|another user|other user'?s|of user)", re.I)),
    ("GR-08", "price_manipulation", re.compile(r"(amount\s*=\s*\d+|charge me ₹?\s*1\b|process_payment .*amount|set price to 0|coupon admin)", re.I)),
    ("GR-09", "refund_redirect", re.compile(r"(refund (it |them |money )?to (this|a|my) (new|different|other) (upi|account|card)|new upi)", re.I)),
    ("GR-10", "unbounded_scope", re.compile(r"(every day of|all dates|entire year|each day in 20\d\d|list all flights for the year)", re.I)),
]

# Base64 / leetspeak evasion detection (RT-12)
_B64 = re.compile(r"^[A-Za-z0-9+/=]{24,}$")


def _normalise(text: str) -> str:
    t = text
    # decode a base64 token if the whole message (or a long token) looks like base64
    for tok in text.split():
        if _B64.match(tok):
            try:
                import base64
                t += " " + base64.b64decode(tok + "=" * (-len(tok) % 4)).decode("utf-8", "ignore")
            except Exception:
                pass
    # leetspeak
    t = t.translate(str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"}))
    return t


def check_input(text: str) -> List[RuleHit]:
    hits = []
    for rid, cat, rx in INPUT_RULES:
        for candidate in (text, _normalise(text)):
            m = rx.search(candidate)
            if m:
                hits.append(RuleHit(rid, cat, candidate[max(0, m.start() - 20): m.end() + 20]))
                break
    return hits


# ----------------------------------------------------------------------------
# Consent gate for side-effect tools
# ----------------------------------------------------------------------------

_AFFIRM = re.compile(r"^\s*(yes|yeah|yep|confirm(ed)?|go ahead|proceed|ok(ay)?[,.! ]*(book|go|proceed|confirm)|please (book|proceed|confirm)|book it|do it|haan|ha|theek hai|sure[,.! ]*(book|go ahead|proceed))\b", re.I)


def user_gave_consent(message: str, run_seed: int) -> bool:
    """True only when the *current* message is an explicit confirmation."""
    if _AFFIRM.search(message.strip()):
        return True
    if settings.defects_enabled:
        # DEFECT-1 (TS-02): a message that merely *mentions* booking is sometimes
        # accepted as consent. Intermittent (~60%) so the class sees a "flaky" bug.
        if re.search(r"\bbook\b", message, re.I) and not re.search(r"\?", message):
            return random.Random(run_seed).random() < 0.6
    return False


def tool_allowed(tool: str) -> Optional[str]:
    """Return a reason string if the tool is NOT allowed, else None."""
    if tool in settings.disabled_tools:
        return f"{tool} is disabled by the tool allow-list"
    return None


def spend_limit_ok(session_id: str, amount: int) -> bool:
    if settings.defects_enabled:
        # DEFECT-6 (RT-06): checks the single booking, not the cumulative session spend
        return amount <= settings.session_spend_limit
    return store.session_spend.get(session_id, 0) + amount <= settings.session_spend_limit


# ----------------------------------------------------------------------------
# PII masking for traces / logs
# ----------------------------------------------------------------------------

_CARD = re.compile(r"\b(?:\d[ -]?){12}(\d{4})\b")
_AADHAAR = re.compile(r"\b(\d{4})[ -]?(\d{4})[ -]?(\d{4})\b")
_PASSPORT = re.compile(r"\b([A-Z])(\d{7})\b")
_PHONE = re.compile(r"(\+91[- ]?)?\b(\d{5})[ -]?(\d{5})\b")


def mask_pii(text: str) -> str:
    if not isinstance(text, str):
        return text
    text = _CARD.sub(lambda m: "XXXX-XXXX-XXXX-" + m.group(1), text)
    text = _PASSPORT.sub(lambda m: m.group(1) + "XXXX" + m.group(2)[-3:], text)
    if not settings.defects_enabled:
        # fixed build masks Aadhaar and phone numbers as well
        text = _AADHAAR.sub(lambda m: "XXXX-XXXX-" + m.group(3), text)
        text = _PHONE.sub(lambda m: "+91-XXXXX-" + m.group(3), text)
    # DEFECT-4 (OB-03): Aadhaar and phone numbers are NOT masked in the defective build
    return text
