"""Day-planner specialist: turns whatever the flight/hotel/weather specialists
found this turn into a simple day-by-day itinerary. Deterministic and
template-based (no LLM call), so it's instant and reproducible like the rest
of the mock-mode building blocks. Runs *after* the other specialists since it
reads their output — the one specialist that can't be dispatched in parallel
with the ones it depends on.
"""
from typing import Optional

from .base import SpecialistResult

_ACTIVITY_BANK = {
    "Goa": ["relax at the beach and try local seafood", "visit a fort or old church nearby", "take a sunset cruise or spice-plantation tour"],
    "Mumbai": ["walk Marine Drive and the Gateway of India", "browse a local market (Colaba Causeway)", "catch a Bollywood studio tour"],
    "Delhi": ["visit India Gate and Humayun's Tomb", "explore Chandni Chowk for street food", "see the Red Fort and Jama Masjid"],
    "Jaipur": ["tour Amer Fort", "walk the Pink City bazaars", "visit Hawa Mahal at sunrise"],
    "Bengaluru": ["walk Cubbon Park and Lalbagh", "explore Indiranagar's cafes", "day trip to Nandi Hills"],
    "Kochi": ["stroll Fort Kochi and the Chinese fishing nets", "take a backwater houseboat tour", "watch a Kathakali performance"],
    "Dubai": ["visit the Burj Khalifa and Dubai Mall", "walk the Jumeirah beach and marina", "explore the old Gold/Spice Souks"],
}
_DEFAULT_ACTIVITIES = ["explore the city center and local markets", "try the regional cuisine", "visit a nearby landmark or museum"]


def plan(city: Optional[str], nights: Optional[int], flight: Optional[SpecialistResult], hotel: Optional[SpecialistResult],
         weather: Optional[SpecialistResult]) -> SpecialistResult:
    if not city:
        return SpecialistResult("planner", False, "Day-planner agent: I need a destination to put together a day plan.")
    nights = nights or 2
    activities = _ACTIVITY_BANK.get(city, _DEFAULT_ACTIVITIES)
    days = []
    for d in range(1, nights + 2):  # arrival day + `nights` full days
        if d == 1 and flight and flight.ok and flight.data.get("options"):
            arrive = flight.data["options"][0].get("arrive", "")
            days.append(f"Day {d}: arrive in {city}" + (f" ({arrive} landing)" if arrive else "") + ", check in and settle in.")
        else:
            act = activities[(d - 2) % len(activities)]
            days.append(f"Day {d}: {act[0].upper()}{act[1:]}.")
    weather_note = ""
    if weather and weather.ok and weather.data.get("summary"):
        weather_note = f" Expect {weather.data['summary'].lower()}, around {weather.data.get('temp_c')}°C."
    summary = f"Day-planner agent: {nights + 1}-day plan for {city} — " + " ".join(days) + weather_note
    return SpecialistResult("planner", True, summary, data={"days": days})
