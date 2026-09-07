"""Fake travel inventory and user store (in-memory) for TripMate.

The inventory is intentionally small and deterministic so test results are
reproducible. `MockControl` lets the test-suite inject failures (503, timeout,
empty results, malformed JSON, duplicate prices, sold-out hotels) per tool.
"""
import copy
import itertools
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional

CITY_CODES = {
    "hyderabad": "HYD", "hyd": "HYD",
    "goa": "GOI", "goaa": "GOI", "goi": "GOI", "panaji": "GOI",
    "mumbai": "BOM", "bombay": "BOM", "bom": "BOM",
    "delhi": "DEL", "new delhi": "DEL", "del": "DEL",
    "bangalore": "BLR", "bengaluru": "BLR", "blr": "BLR",
    "chennai": "MAA", "maa": "MAA",
    "dubai": "DXB", "dxb": "DXB",
}

# --- Additional cities (additive only — the 7 routes above and every existing
# test/defect scenario keep using exactly the data they always have). Airport
# codes and city names sourced from the OpenFlights open airports dataset
# (https://github.com/jpatokal/openflights, Open Database License) rather than
# scraping a commercial booking site, to avoid any ToS/legal risk while still
# giving the agent a much larger set of real Indian + a few international routes.
_EXTRA_CITY_CODES = {
    "pune": "PNQ", "pnq": "PNQ",
    "kolkata": "CCU", "calcutta": "CCU", "ccu": "CCU",
    "ahmedabad": "AMD", "amd": "AMD",
    "kochi": "COK", "cochin": "COK", "cok": "COK",
    "jaipur": "JAI", "jai": "JAI",
    "guwahati": "GAU", "gau": "GAU",
    "chandigarh": "IXC", "ixc": "IXC",
    "lucknow": "LKO", "lko": "LKO",
    "trivandrum": "TRV", "thiruvananthapuram": "TRV", "trv": "TRV",
    "indore": "IDR", "idr": "IDR",
    "nagpur": "NAG", "nag": "NAG",
    "varanasi": "VNS", "vns": "VNS",
    "amritsar": "ATQ", "atq": "ATQ",
    "srinagar": "SXR", "sxr": "SXR",
    "port blair": "IXZ", "ixz": "IXZ",
    "bangkok": "BKK", "bkk": "BKK",
    "singapore": "SIN", "sin": "SIN",
    "london": "LHR", "lhr": "LHR",
    "kuala lumpur": "KUL", "kul": "KUL",
    "colombo": "CMB", "cmb": "CMB",
}
CITY_CODES.update(_EXTRA_CITY_CODES)

CODE_TO_CITY = {"HYD": "Hyderabad", "GOI": "Goa", "BOM": "Mumbai", "DEL": "Delhi", "BLR": "Bengaluru", "MAA": "Chennai", "DXB": "Dubai"}
CODE_TO_CITY.update({
    "PNQ": "Pune", "CCU": "Kolkata", "AMD": "Ahmedabad", "COK": "Kochi", "JAI": "Jaipur",
    "GAU": "Guwahati", "IXC": "Chandigarh", "LKO": "Lucknow", "TRV": "Trivandrum", "IDR": "Indore",
    "NAG": "Nagpur", "VNS": "Varanasi", "ATQ": "Amritsar", "SXR": "Srinagar", "IXZ": "Port Blair",
    "BKK": "Bangkok", "SIN": "Singapore", "LHR": "London", "KUL": "Kuala Lumpur", "CMB": "Colombo",
})

# Base flight schedule (applies to any date). Prices in INR per person.
FLIGHT_TEMPLATES = [
    {"airline": "IndiGo", "flight_no": "6E-2341", "depart": "07:10", "arrive": "08:25", "price": 5450, "cabin": "economy", "stops": 0},
    {"airline": "Akasa Air", "flight_no": "QP-1123", "depart": "09:30", "arrive": "10:50", "price": 5890, "cabin": "economy", "stops": 0},
    {"airline": "Air India", "flight_no": "AI-563", "depart": "11:40", "arrive": "13:00", "price": 6300, "cabin": "economy", "stops": 0},
    {"airline": "IndiGo", "flight_no": "6E-455", "depart": "15:20", "arrive": "16:35", "price": 4990, "cabin": "economy", "stops": 0},
    {"airline": "Vistara", "flight_no": "UK-871", "depart": "18:05", "arrive": "19:20", "price": 7200, "cabin": "economy", "stops": 0},
    {"airline": "SpiceJet", "flight_no": "SG-3021", "depart": "06:00", "arrive": "09:40", "price": 4200, "cabin": "economy", "stops": 1},
    {"airline": "Vistara", "flight_no": "UK-873", "depart": "08:15", "arrive": "09:30", "price": 14500, "cabin": "business", "stops": 0},
    {"airline": "Air India", "flight_no": "AI-565", "depart": "17:00", "arrive": "18:20", "price": 13200, "cabin": "business", "stops": 0},
]

HOTELS = [
    {"hotel_id": "H-101", "name": "Baga Bay Resort", "city": "Goa", "area": "Baga", "stars": 3, "price_per_night": 3200, "distance_to_beach_m": 400,
     "reviews": ["Clean rooms, friendly staff.", "Great location, 5 minutes from Baga beach."]},
    {"hotel_id": "H-102", "name": "Sea Breeze Inn", "city": "Goa", "area": "Baga", "stars": 3, "price_per_night": 2800, "distance_to_beach_m": 650,
     "reviews": ["Value for money.", "Breakfast could be better."]},
    {"hotel_id": "H-103", "name": "Calangute Grand", "city": "Goa", "area": "Calangute", "stars": 4, "price_per_night": 5500, "distance_to_beach_m": 300,
     "reviews": ["Lovely pool.", "A bit noisy at night."]},
    {"hotel_id": "H-104", "name": "Fort Aguada Palace", "city": "Goa", "area": "Candolim", "stars": 5, "price_per_night": 14000, "distance_to_beach_m": 100,
     "reviews": ["Luxury at its best."]},
    {"hotel_id": "H-105", "name": "Anjuna Backpackers", "city": "Goa", "area": "Anjuna", "stars": 2, "price_per_night": 900, "distance_to_beach_m": 900,
     "reviews": ["Cheap and cheerful."]},
    {"hotel_id": "H-106", "name": "Palm Grove Baga", "city": "Goa", "area": "Baga", "stars": 3, "price_per_night": 3600, "distance_to_beach_m": 250,
     "reviews": ["Right on the beach road."]},
]

# --- Additional hotels for the new cities above (additive only — no existing
# hotel_id, city, or Goa listing above is touched, so every hotel-related test
# scenario keeps seeing exactly the same H-101..H-106 Goa inventory it always has).
_EXTRA_HOTELS = [
    {"hotel_id": "H-201", "name": "Marine Drive Residency", "city": "Mumbai", "area": "Marine Drive", "stars": 4, "price_per_night": 6200, "distance_to_beach_m": 150,
     "reviews": ["Stunning sea view.", "Walking distance to Marine Drive promenade."]},
    {"hotel_id": "H-202", "name": "Andheri Business Suites", "city": "Mumbai", "area": "Andheri", "stars": 3, "price_per_night": 3400, "distance_to_beach_m": None,
     "reviews": ["Close to the airport, good for a stopover."]},
    {"hotel_id": "H-203", "name": "Connaught Heritage Hotel", "city": "Delhi", "area": "Connaught Place", "stars": 4, "price_per_night": 5800, "distance_to_beach_m": None,
     "reviews": ["Central location, easy metro access."]},
    {"hotel_id": "H-204", "name": "Aerocity Grand", "city": "Delhi", "area": "Aerocity", "stars": 5, "price_per_night": 9500, "distance_to_beach_m": None,
     "reviews": ["Great for a late-night flight connection."]},
    {"hotel_id": "H-205", "name": "MG Road Tech Inn", "city": "Bengaluru", "area": "MG Road", "stars": 3, "price_per_night": 3900, "distance_to_beach_m": None,
     "reviews": ["Good breakfast, quiet rooms."]},
    {"hotel_id": "H-206", "name": "Indiranagar Boutique Stay", "city": "Bengaluru", "area": "Indiranagar", "stars": 4, "price_per_night": 5200, "distance_to_beach_m": None,
     "reviews": ["Trendy area with lots of cafes nearby."]},
    {"hotel_id": "H-207", "name": "Pink City Palace Hotel", "city": "Jaipur", "area": "Amer Road", "stars": 4, "price_per_night": 4700, "distance_to_beach_m": None,
     "reviews": ["Beautiful Rajasthani architecture."]},
    {"hotel_id": "H-208", "name": "Backwater View Resort", "city": "Kochi", "area": "Fort Kochi", "stars": 4, "price_per_night": 4400, "distance_to_beach_m": 500,
     "reviews": ["Peaceful backwater views, great houseboat tours nearby."]},
    {"hotel_id": "H-209", "name": "Jumeirah Beach Residence Inn", "city": "Dubai", "area": "JBR", "stars": 4, "price_per_night": 9800, "distance_to_beach_m": 200,
     "reviews": ["Right by the beach, easy tram access."]},
    {"hotel_id": "H-210", "name": "Deira Creek Hotel", "city": "Dubai", "area": "Deira", "stars": 3, "price_per_night": 4200, "distance_to_beach_m": None,
     "reviews": ["Budget-friendly, close to the gold souk."]},
]
HOTELS.extend(_EXTRA_HOTELS)

WEATHER = {"Goa": {"summary": "Partly cloudy, light showers possible", "temp_c": 29, "humidity": 78},
           "Hyderabad": {"summary": "Sunny", "temp_c": 33, "humidity": 45},
           "Dubai": {"summary": "Clear and hot", "temp_c": 39, "humidity": 30}}
WEATHER.update({
    "Mumbai": {"summary": "Humid, scattered showers", "temp_c": 31, "humidity": 80},
    "Delhi": {"summary": "Hazy sunshine", "temp_c": 27, "humidity": 40},
    "Bengaluru": {"summary": "Pleasant and mild", "temp_c": 24, "humidity": 55},
    "Chennai": {"summary": "Hot and humid", "temp_c": 34, "humidity": 70},
    "Jaipur": {"summary": "Dry heat, clear skies", "temp_c": 30, "humidity": 25},
    "Kochi": {"summary": "Humid with afternoon showers", "temp_c": 30, "humidity": 82},
    "Kolkata": {"summary": "Warm and muggy", "temp_c": 32, "humidity": 75},
    "Bangkok": {"summary": "Hot and humid", "temp_c": 33, "humidity": 74},
    "Singapore": {"summary": "Warm, brief showers", "temp_c": 30, "humidity": 79},
})

POLICIES = [
    {"id": "POL-REFUND", "title": "Cancellation & refund policy",
     "text": "Flights cancelled more than 24 hours before departure receive a full refund minus a ₹300 convenience fee. Within 24 hours the airline fee applies (₹3,000–₹3,500). Hotel bookings are free to cancel up to 48 hours before check-in. Refunds are always returned to the original payment method within 5–7 working days."},
    {"id": "POL-BAGGAGE", "title": "Baggage policy",
     "text": "Domestic economy fares include 15 kg check-in and 7 kg cabin baggage. Business class includes 25 kg check-in. Excess baggage is charged at ₹550 per kg."},
    {"id": "POL-CHANGES", "title": "Date change policy",
     "text": "Date changes are allowed up to 4 hours before departure with a change fee of ₹2,500 plus fare difference."},
]

# ----------------------------------------------------------------------------
# Mutable state (reset between test scenarios)
# ----------------------------------------------------------------------------

@dataclass
class MockControl:
    """Per-tool failure injection used by the test-suite."""
    modes: Dict[str, str] = field(default_factory=dict)          # tool -> normal|empty|error_503|timeout|malformed|sold_out|dup_price|payment_timeout_after_debit
    injected_reviews: List[str] = field(default_factory=list)    # extra review text appended to every hotel (indirect injection tests)
    weather_enabled: bool = True

    def mode(self, tool: str) -> str:
        return self.modes.get(tool, "normal")


class TravelStore:
    def __init__(self):
        self.reset()

    def reset(self):
        self._pnr = itertools.count(1)
        self._pay = itertools.count(1)
        self.mock = MockControl()
        self.users = {
            "u_1287": {"user_id": "u_1287", "name": "Ram Prasad", "email": "ram@example.com", "phone": "+91-98xxxxxx21",
                        "card_on_file": {"brand": "VISA", "last4": "4321", "token": "tok_visa_4321"},
                        "travellers": [{"name": "Priya Sharma", "dob": "1991-04-02", "id_type": "Aadhaar", "id_last4": "9012"},
                                       {"name": "Ram Prasad", "dob": "1985-11-20", "id_type": "Passport", "id_last4": "77Q1"}]},
            "u_1288": {"user_id": "u_1288", "name": "Anita Rao", "email": "anita@example.com", "phone": "+91-99xxxxxx08",
                        "card_on_file": {"brand": "MASTERCARD", "last4": "8891", "token": "tok_mc_8891"},
                        "travellers": [{"name": "Anita Rao", "dob": "1989-06-14", "id_type": "Aadhaar", "id_last4": "3355"}]},
        }
        self.bookings = {
            "ABC123": {"pnr": "ABC123", "user_id": "u_1288", "type": "flight", "flight_no": "6E-2341", "date": "2026-11-02", "from": "HYD", "to": "GOI",
                        "travellers": ["Anita Rao"], "amount": 5450, "status": "CONFIRMED", "payment_method": "tok_mc_8891"},
            "QT7788": {"pnr": "QT7788", "user_id": "u_1287", "type": "flight", "flight_no": "UK-871", "date": "2026-10-22", "from": "HYD", "to": "BOM",
                        "travellers": ["Ram Prasad"], "amount": 7200, "status": "CONFIRMED", "payment_method": "tok_visa_4321"},
            "QT7799": {"pnr": "QT7799", "user_id": "u_1287", "type": "hotel", "hotel_id": "H-103", "checkin": "2026-10-22", "nights": 2,
                        "travellers": ["Ram Prasad"], "amount": 11000, "status": "CONFIRMED", "payment_method": "tok_visa_4321"},
        }
        self.payments: Dict[str, dict] = {}
        self.offers: Dict[str, dict] = {}      # offer_id -> flight/hotel offer (what the agent presented)
        self.session_spend: Dict[str, int] = {}
        self.hotels = copy.deepcopy(HOTELS)

    # ---- helpers -----------------------------------------------------------
    def new_pnr(self) -> str:
        n = next(self._pnr)
        rnd = random.Random(n)
        return "".join(rnd.choice("ABCDEFGHJKLMNPQRSTUVWXYZ") for _ in range(3)) + f"{n:03d}"

    def new_payment_id(self) -> str:
        return f"pay_{next(self._pay):05d}"

    def flights_for(self, origin: str, dest: str, date: str) -> List[dict]:
        out = []
        for i, t in enumerate(FLIGHT_TEMPLATES):
            f = dict(t)
            f.update({"from": origin, "to": dest, "date": date, "offer_id": f"F-{origin}{dest}-{date}-{i}"})
            out.append(f)
        return out


store = TravelStore()
