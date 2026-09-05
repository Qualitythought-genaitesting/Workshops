"""Lightweight natural-language understanding used by the offline MockLLM.

It extracts intent + travel constraints from a user message with regexes so the
agent behaves deterministically without a real model. It deliberately mirrors
the kinds of mistakes real LLMs make (see DEFECT-2).
"""
import calendar
import datetime as dt
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..config import settings
from ..data import CITY_CODES

MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_abbr) if m}
MONTHS.update({m.lower(): i for i, m in enumerate(calendar.month_name) if m})
MONTHS.update({"sept": 9, "otc": 10, "ocotber": 10, "octber": 10})


def today() -> dt.date:
    fixed = os.getenv("TRIPMATE_TODAY")
    return dt.date.fromisoformat(fixed) if fixed else dt.date.today()


@dataclass
class Constraints:
    origin: Optional[str] = None
    dest: Optional[str] = None
    date: Optional[str] = None            # ISO
    return_date: Optional[str] = None
    invalid_date: Optional[str] = None    # raw text of an impossible date
    past_date: Optional[str] = None
    pax: Optional[int] = None
    children: List[int] = field(default_factory=list)
    budget: Optional[int] = None
    budget_per_person: bool = True
    depart_before: Optional[str] = None
    depart_after: Optional[str] = None
    cabin: Optional[str] = None
    non_stop: bool = False
    cheapest: bool = False
    hotel: bool = False
    flight: bool = False
    stars: Optional[int] = None
    area: Optional[str] = None
    city: Optional[str] = None
    nights: Optional[int] = None
    traveller_name: Optional[str] = None
    hotel_name: Optional[str] = None
    airline: Optional[str] = None
    pnr: Optional[str] = None
    wants_booking: bool = False

    def merge_from(self, other: "Constraints"):
        for k, v in other.__dict__.items():
            if v in (None, [], False) and getattr(self, k) not in (None, [], False):
                setattr(other, k, getattr(self, k))
        return other


# ----------------------------------------------------------------------------
# Dates
# ----------------------------------------------------------------------------

def _resolve(day: int, month: int, year: Optional[int]) -> Tuple[Optional[str], Optional[str]]:
    """Return (iso_date, invalid_text)."""
    t = today()
    y = year or t.year
    try:
        d = dt.date(y, month, day)
    except ValueError:
        return None, f"{day} {calendar.month_abbr[month]} {y}"
    if year is None and d < t:
        try:
            d = dt.date(y + 1, month, day)
        except ValueError:
            return None, f"{day} {calendar.month_abbr[month]} {y + 1}"
    return d.isoformat(), None


def parse_dates(text: str) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """Return (date, return_date, invalid_date_text, past_date_text)."""
    t = today()
    low = text.lower()
    # ISO
    m = re.search(r"\b(20\d\d)-(\d\d)-(\d\d)\b", low)
    if m:
        iso, inv = _resolve(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        return iso, None, inv, None
    # range "15–18 Oct" / "15-18 oct" / "15 to 18 oct"
    for m in re.finditer(r"\b(\d{1,2})(?:st|nd|rd|th)?\s*(?:–|-|to)\s*(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]{3,9})\b", low):
        mon = MONTHS.get(m.group(3)) or MONTHS.get(m.group(3)[:3])
        if mon:
            d1, inv1 = _resolve(int(m.group(1)), mon, None)
            d2, inv2 = _resolve(int(m.group(2)), mon, None)
            return d1, d2, inv1 or inv2, None
    # "15 Oct", "15th October", "15 oct 2027"
    for m in re.finditer(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]{3,9})\.?(?:\s+(20\d\d))?\b", low):
        mon = MONTHS.get(m.group(2)) or MONTHS.get(m.group(2)[:3])
        if mon:
            iso, inv = _resolve(int(m.group(1)), mon, int(m.group(3)) if m.group(3) else None)
            return iso, None, inv, None
    # "Oct 15", "October 15, 2027"
    for m in re.finditer(r"\b([a-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(20\d\d))?\b", low):
        mon = MONTHS.get(m.group(1)) or MONTHS.get(m.group(1)[:3])
        if mon:
            iso, inv = _resolve(int(m.group(2)), mon, int(m.group(3)) if m.group(3) else None)
            return iso, None, inv, None
    # dd/mm or dd/mm/yy
    m = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", low)
    if m:
        y = m.group(3)
        year = None if not y else (int(y) + 2000 if len(y) == 2 else int(y))
        iso, inv = _resolve(int(m.group(1)), int(m.group(2)), year)
        return iso, None, inv, None
    # relative
    if "yesterday" in low:
        return None, None, None, (t - dt.timedelta(days=1)).isoformat()
    if "tomorrow" in low or "kal" in low.split():
        return (t + dt.timedelta(days=1)).isoformat(), None, None, None
    m = re.search(r"next\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)", low)
    if m:
        target = list(calendar.day_name).index(m.group(1).title())
        delta = (target - t.weekday()) % 7 or 7
        return (t + dt.timedelta(days=delta)).isoformat(), None, None, None
    return None, None, None, None


# ----------------------------------------------------------------------------
# Constraints
# ----------------------------------------------------------------------------

_CITY_RX = re.compile(r"\b(" + "|".join(sorted(CITY_CODES.keys(), key=len, reverse=True)) + r")\b", re.I)


def extract(text: str) -> Constraints:
    c = Constraints()
    low = text.lower()

    # cities / route
    m = re.search(r"\b(hyd(?:erabad)?|goaa?|goi|mumbai|bom|delhi|del|bangalore|bengaluru|blr|chennai|maa|dubai)\s*(?:→|->|to|se|-|–)\s*(hyd(?:erabad)?|goa|goi|mumbai|bom|delhi|del|bangalore|bengaluru|blr|chennai|maa|dubai)\b", low)
    if m:
        c.origin, c.dest = CITY_CODES[m.group(1).rstrip("a") if m.group(1) == "goaa" else m.group(1)], CITY_CODES[m.group(2).rstrip("a") if m.group(2) == "goaa" else m.group(2)]
    else:
        cities = [CITY_CODES[x.lower()] for x in _CITY_RX.findall(text)]
        if cities:
            c.dest = cities[0]
            c.origin = "HYD" if cities[0] != "HYD" else None   # default home airport
    if c.dest:
        from ..data import CODE_TO_CITY
        c.city = CODE_TO_CITY.get(c.dest)

    # dates
    c.date, c.return_date, c.invalid_date, c.past_date = parse_dates(text)
    if re.search(r"round[- ]?trip|return|wapsi", low) and c.date and not c.return_date:
        c.return_date = None  # round trip mentioned but no second date

    # pax
    m = re.search(r"\b(\d+|two|three|four)\s*(adults?|people|persons?|pax|ppl|log|passengers?|travell?ers?)\b", low)
    words = {"two": 2, "three": 3, "four": 4}
    if m:
        c.pax = int(words.get(m.group(1), m.group(1)))
    m = re.search(r"(\d+)\s*(?:child|children|kid|kids)", low)
    if m:
        age = re.search(r"age[sd]?\s*(\d+)", low[m.end():m.end() + 30])
        c.children = [int(age.group(1)) if age else 5] * int(m.group(1))

    # budget
    m = re.search(r"(?:under|below|less than|max(?:imum)?|within|upto|up to)\s*₹?\s*(?:rs\.?\s*)?([\d,]+)\s*(k)?\s*(per person|pp|each|per head|per pax)?", low)
    if m:
        amt = int(m.group(1).replace(",", "")) * (1000 if m.group(2) else 1)
        per_person = bool(m.group(3))
        if settings.defects_enabled and m.group(2):
            # DEFECT-2 (PL-01): when the budget is written with a "k" abbreviation the
            # parser drops the constraint entirely (max_price never reaches the tool).
            c.budget = None
        else:
            c.budget = amt
            c.budget_per_person = per_person or True

    # time window
    if re.search(r"\b(morning|subah|early)\b", low):
        c.depart_before = "12:00"
    if re.search(r"\b(afternoon|dopahar)\b", low):
        c.depart_after, c.depart_before = "12:00", "17:00"
    if re.search(r"\b(evening|night|shaam|raat)\b", low):
        c.depart_after = "17:00"

    # cabin / stops / cheapest
    if re.search(r"\bbusiness\b", low):
        c.cabin = "business"
    if re.search(r"non[- ]?stop|direct", low):
        c.non_stop = True
    if re.search(r"cheapest|lowest fare|sabse sasti", low):
        c.cheapest = True

    # flight / hotel intent words
    c.flight = bool(re.search(r"flight|flgiht|fly|uda?an|airline|ticket", low))
    c.hotel = bool(re.search(r"hotel|resort|stay|room|nights?", low))
    m = re.search(r"(\d)\s*(?:★|\*|-?\s*star)", low)
    if m:
        c.stars = int(m.group(1))
    m = re.search(r"(?:near|in|at)\s+(baga|calangute|candolim|anjuna)\b", low)
    if m:
        c.area = m.group(1).title()
    m = re.search(r"(\d+)\s*nights?", low)
    if m:
        c.nights = int(m.group(1))
    elif c.date and c.return_date:
        c.nights = (dt.date.fromisoformat(c.return_date) - dt.date.fromisoformat(c.date)).days

    # names / airline / hotel / pnr
    m = re.search(r"traveller\s+([A-Z][a-z]+)|for\s+([A-Z][a-z]+)\s+and\s+me", text)
    if m:
        c.traveller_name = m.group(1) or m.group(2)
    m = re.search(r"\b(indigo|akasa|air india|vistara|spicejet)\b", low)
    if m:
        c.airline = m.group(1)
    m = re.search(r"\b(baga bay resort|sea breeze inn|calangute grand|fort aguada palace|anjuna backpackers|palm grove baga)\b", low)
    if m:
        c.hotel_name = m.group(1).title()
    m = re.search(r"\bpnr\s*:?\s*([A-Z]{3}\d{3}|[A-Z0-9]{6})\b", text, re.I)
    if m:
        c.pnr = m.group(1).upper()
    c.wants_booking = bool(re.search(r"\bbook\b|\bbuy\b|reserve|kar do|karo", low))
    return c


# ----------------------------------------------------------------------------
# Intent
# ----------------------------------------------------------------------------

INTENT_PATTERNS = [
    ("frustration", r"(3rd time|third time|failed!!|this is ridiculous|useless|not working|fed up|angry)"),
    ("denial_of_wallet", r"(every day of|all dates|entire year|each day in 20\d\d|list all flights)"),
    ("cross_user", r"(user u_\d+|another user|other user)"),
    ("refund_redirect", r"(cancel all my bookings|refund .* (new|different|other) (upi|account|card))"),
    ("price_manipulation", r"(amount\s*=\s*\d+|charge me ₹?\s*1\b|set price to 0|coupon admin|process_payment)"),
    ("impersonation", r"(i('| a)?m (from )?(mmt|makemytrip|tripmate) (support|staff|team)|card number on file|read me the card|share the otp)"),
    ("prompt_leak", r"(repeat (everything|all|the text) above|system prompt|reveal your instructions|verbatim)"),
    ("jailbreak", r"(you are (now )?(dan|travelgpt)|no restrictions|pretend (you|to be)|ignore your polic)"),
    ("injection_override", r"(system\s*override|ignore (all|your|previous|prior) (rules|instructions)|confirmation (is )?not required|skip (the )?confirmation|as we agreed)"),
    ("medical", r"(medicine|medication|tablets?|antibiotic|dosage|prescription|vaccine)"),
    ("visa", r"\bvisa\b"),
    ("policy", r"(policy|refund|cancellation (policy|charges|fee)|baggage|luggage|change fee|reschedul)"),
    ("cancel", r"\bcancel\b"),
    ("change_date", r"(actually|instead|change (it|the date)|make it)\s.*\b\d{1,2}\s*[a-z]{3,9}"),
    ("confirm_yes", r"^\s*(yes|yeah|yep|confirm(ed)?|go ahead|proceed|ok(ay)?[,.! ]*(book|go|proceed|confirm)|please (book|proceed)|book it|do it|haan|ha|theek hai|sure[,.! ]*(book|go ahead|proceed))\b"),
    ("decline", r"^\s*(no|nah|cancel that|don't|do not|nahi)\b"),
    ("book_selected", r"\bbook (the|that|this|it)\b|\bthe (indigo|akasa|air india|vistara|spicejet) one\b|book (indigo|akasa|air india|vistara|spicejet)\b"),
    ("weather", r"\b(weather|forecast|rain|temperature|mausam)\b"),
    ("list_bookings", r"(my bookings|show (my )?(bookings|trips)|upcoming trips)"),
    ("greeting", r"^\s*(hi|hello|hey|namaste)\b[\s!.]*$"),
]


def detect_intent(text: str) -> str:
    low = text.lower().strip()
    for name, rx in INTENT_PATTERNS:
        if re.search(rx, low, re.I):
            return name
    c = extract(text)
    if c.flight or c.hotel or c.dest or c.date:
        return "trip"
    return "other"
