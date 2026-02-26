import os
import math
import json
import operator
from typing import Annotated, List, Literal, TypedDict, Any, Dict
from datetime import date

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.utilities import SerpAPIWrapper
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage, AnyMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from amadeus import Client as AmadeusClient, ResponseError

load_dotenv()

# ─────────────────────────────────────────────
# 1. Clients
# ─────────────────────────────────────────────
amadeus = AmadeusClient(
    client_id=os.getenv("AMADEUS_CLIENT_ID"),
    client_secret=os.getenv("AMADEUS_CLIENT_SECRET"),
)
search = SerpAPIWrapper()


# ─────────────────────────────────────────────
# 2. Haversine helper
# ─────────────────────────────────────────────
def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ─────────────────────────────────────────────
# 3. Tools
# ─────────────────────────────────────────────

@tool
def google_search(query: str) -> str:
    """
    Search the web for:
    1. Top tourist attractions / places to visit at a destination.
    2. Opening hours, entry prices of specific attractions.
    3. Neighborhood / area context for a place.
    Always include the city name in the query.
    """
    return search.run(query)


@tool
def amadeus_flight_search(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str = "",
    adults: int = 1,
    cabin_class: str = "ECONOMY",
) -> str:
    """
    Search for available flights using the Amadeus Flight Offers Search API.

    Args:
        origin:         IATA airport code of the departure city (e.g. 'DEL').
        destination:    IATA airport code of the arrival city (e.g. 'CDG').
        departure_date: Departure date in YYYY-MM-DD format.
        return_date:    Return date in YYYY-MM-DD format (leave empty for one-way).
        adults:         Number of adult passengers.
        cabin_class:    One of ECONOMY | PREMIUM_ECONOMY | BUSINESS | FIRST.

    Returns a JSON string containing flight offers with total_found count.
    """
    print(f"[FLIGHT TOOL] Searching: {origin} -> {destination} on {departure_date}")

    try:
        kwargs = dict(
            originLocationCode=origin,
            destinationLocationCode=destination,
            departureDate=departure_date,
            adults=adults,
            max=10,
            currencyCode="USD",
            travelClass=cabin_class,
        )
        if return_date:
            kwargs["returnDate"] = return_date

        offers = amadeus.shopping.flight_offers_search.get(**kwargs).data

        if not offers:
            return json.dumps({"error": "No flight offers found.", "total_found": 0})

        print(f"[FLIGHT TOOL] Found {len(offers)} flights")
        return json.dumps({"flights": offers, "total_found": len(offers)}, indent=2)

    except ResponseError as e:
        error_body = str(e)
        if "410" in error_body:
            return json.dumps({
                "error": "410 - No flight data in Amadeus TEST env for this route. Switch to production keys.",
                "total_found": 0
            })
        return json.dumps({"error": error_body, "total_found": 0})


@tool
def amadeus_hotels_near_places(
    places_with_coords: str,
    check_in_date: str,
    check_out_date: str,
    adults: int = 1,
    radius_km: int = 10,
) -> str:
    """
    Find the cheapest hotels closest to a set of visiting places using Amadeus.

    Args:
        places_with_coords: JSON string — list of dicts with keys: name, lat, lng.
                            Example:
                            '[{"name":"Eiffel Tower","lat":48.8584,"lng":2.2945},
                              {"name":"Louvre","lat":48.8606,"lng":2.3376}]'
                            Build this from google_search results using your knowledge
                            of the coordinates of the places.
        check_in_date:  YYYY-MM-DD
        check_out_date: YYYY-MM-DD
        adults:         Number of guests.
        radius_km:      Search radius around centroid in km (default 10).

    Returns a JSON string with total_hotels_found and recommended budget/mid-range hotels.
    """
    print(f"[HOTEL TOOL] check_in={check_in_date}, check_out={check_out_date}")
    print(f"[HOTEL TOOL] places={places_with_coords[:200]}")

    try:
        places = json.loads(places_with_coords)
        if not places:
            return json.dumps({"error": "No places provided."})

        # Step A: Compute centroid of all visiting places
        centroid_lat = sum(p["lat"] for p in places) / len(places)
        centroid_lng = sum(p["lng"] for p in places) / len(places)
        print(f"[HOTEL TOOL] Centroid: {centroid_lat:.4f}, {centroid_lng:.4f}")

        # Step B: Get hotel IDs near centroid
        hotel_list_resp = amadeus.reference_data.locations.hotels.by_geocode.get(
            latitude=centroid_lat,
            longitude=centroid_lng,
            radius=radius_km,
            radiusUnit="KM",
            hotelSource="ALL",
        ).data

        if not hotel_list_resp:
            return json.dumps({
                "error": f"No hotels found within {radius_km} km of centroid.",
                "centroid": {"lat": centroid_lat, "lng": centroid_lng},
                "total_hotels_found": 0,
            })

        hotel_ids = [h["hotelId"] for h in hotel_list_resp[:20]]
        print(f"[HOTEL TOOL] Found {len(hotel_ids)} hotel IDs: {hotel_ids}")

        # Step C: Try live offers first
        offers_resp = None
        try:
            offers_resp = amadeus.shopping.hotel_offers_search.get(
                hotelIds=hotel_ids,
                adults=adults,
                checkInDate=check_in_date,
                checkOutDate=check_out_date,
                currencyCode="USD",
                bestRateOnly=True,
            ).data
        except ResponseError as offer_err:
            print(f"[HOTEL TOOL] Offers search failed: {offer_err}")

        # ── FALLBACK: offers unavailable (test env) → use by_hotels for names ──
        if not offers_resp:
            print("[HOTEL TOOL] Offers returned None. Falling back to by_hotels for names...")
            fallback_results = []

            for hotel_id in hotel_ids[:10]:
                try:
                    detail = amadeus.reference_data.locations.hotels.by_hotels.get(
                        hotelIds=[hotel_id]
                    ).data

                    if detail:
                        h = detail[0]
                        h_lat = h.get("geoCode", {}).get("latitude")
                        h_lng = h.get("geoCode", {}).get("longitude")

                        dist_centroid = (
                            haversine_km(h_lat, h_lng, centroid_lat, centroid_lng)
                            if h_lat and h_lng else None
                        )

                        closest = []
                        if h_lat and h_lng:
                            dists = [
                                (haversine_km(h_lat, h_lng, p["lat"], p["lng"]), p["name"])
                                for p in places
                            ]
                            dists.sort()
                            closest = [f"{name} (~{d:.1f} km)" for d, name in dists[:2]]

                        fallback_results.append({
                            "hotel_id":                hotel_id,
                            "name":                    h.get("name", "UNVERIFIED"),
                            "chain_code":              h.get("chainCode"),
                            "latitude":                h_lat,
                            "longitude":               h_lng,
                            "distance_to_centroid_km": round(dist_centroid, 2) if dist_centroid else "UNVERIFIED",
                            "closest_activities":      closest,
                            "offer_id":                "UNVERIFIED: not available in test env",
                            "check_in":                check_in_date,
                            "check_out":               check_out_date,
                            "nights":                  max(1, (date.fromisoformat(check_out_date) - date.fromisoformat(check_in_date)).days),
                            "room_type":               "UNVERIFIED",
                            "bed_type":                "UNVERIFIED",
                            "board_type":              "UNVERIFIED",
                            "price": {
                                "currency":      "USD",
                                "base":          "UNVERIFIED",
                                "total":         "UNVERIFIED",
                                "selling_total": "UNVERIFIED",
                                "per_night":     "UNVERIFIED",
                            },
                            "cancellation_policy": "UNVERIFIED",
                            "payment_type":        "UNVERIFIED",
                            "why_recommended":     (
                                f"{h.get('name','Hotel')} is ~{dist_centroid:.1f} km from activity centroid"
                                + (f", closest to: {', '.join(closest)}" if closest else "")
                                if dist_centroid else "UNVERIFIED: distance not available"
                            ),
                            "sources":    ["amadeus_by_hotels_fallback"],
                            "confidence": 0.5,
                        })

                except ResponseError as e:
                    print(f"[HOTEL TOOL] Skipping {hotel_id}: {e}")
                    continue

            print(f"[HOTEL TOOL] Fallback returned {len(fallback_results)} hotels.")

            return json.dumps({
                "source":             "amadeus_by_hotels_fallback (offers unavailable in test env)",
                "centroid": {
                    "latitude":  centroid_lat,
                    "longitude": centroid_lng,
                    "note":      f"Centroid of {len(places)} visiting places",
                },
                "radius_km":          radius_km,
                "total_hotels_found": len(fallback_results),
                "recommended": {
                    "budget":    fallback_results[0] if fallback_results else None,
                    "mid_range": fallback_results[1] if len(fallback_results) > 1 else None,
                },
            }, indent=2)

        # ── HAPPY PATH: offers available ──
        nights = max(
            1,
            (date.fromisoformat(check_out_date) - date.fromisoformat(check_in_date)).days,
        )

        enriched = []
        for entry in offers_resp:
            hotel = entry.get("hotel", {})
            offer = entry.get("offers", [{}])[0]
            price_total = float(offer.get("price", {}).get("total", 0) or 0)
            h_lat = hotel.get("latitude")
            h_lng = hotel.get("longitude")

            dist_centroid = (
                haversine_km(h_lat, h_lng, centroid_lat, centroid_lng)
                if h_lat and h_lng else None
            )

            closest = []
            if h_lat and h_lng:
                dists = [
                    (haversine_km(h_lat, h_lng, p["lat"], p["lng"]), p["name"])
                    for p in places
                ]
                dists.sort()
                closest = [f"{name} (~{d:.1f} km)" for d, name in dists[:2]]

            enriched.append({
                "hotel_id":                hotel.get("hotelId", "UNVERIFIED"),
                "name":                    hotel.get("name", "UNVERIFIED"),
                "chain_code":              hotel.get("chainCode"),
                "latitude":                h_lat,
                "longitude":               h_lng,
                "distance_to_centroid_km": round(dist_centroid, 2) if dist_centroid else "UNVERIFIED",
                "closest_activities":      closest,
                "offer_id":                offer.get("id", "UNVERIFIED"),
                "check_in":                offer.get("checkInDate", check_in_date),
                "check_out":               offer.get("checkOutDate", check_out_date),
                "nights":                  nights,
                "room_type":               offer.get("room", {}).get("typeEstimated", {}).get("category", "UNVERIFIED"),
                "bed_type":                offer.get("room", {}).get("typeEstimated", {}).get("bedType", "UNVERIFIED"),
                "board_type":              offer.get("boardType", "ROOM_ONLY"),
                "price": {
                    "currency":      offer.get("price", {}).get("currency", "USD"),
                    "base":          offer.get("price", {}).get("base", "UNVERIFIED"),
                    "total":         str(price_total),
                    "selling_total": offer.get("price", {}).get("sellingTotal", "UNVERIFIED"),
                    "per_night":     str(round(price_total / nights, 2)),
                },
                "cancellation_policy": (
                    offer.get("policies", {})
                    .get("cancellations", [{}])[0]
                    .get("description", {})
                    .get("text", "UNVERIFIED")
                    if offer.get("policies", {}).get("cancellations")
                    else "UNVERIFIED"
                ),
                "payment_type":  offer.get("policies", {}).get("paymentType", "UNVERIFIED"),
                "why_recommended": (
                    f"{hotel.get('name','Hotel')} is ~{dist_centroid:.1f} km from activity centroid"
                    + (f", closest to: {', '.join(closest)}" if closest else "")
                    if dist_centroid
                    else "UNVERIFIED: distance not returned by API"
                ),
                "sources":    ["amadeus_hotels_by_geocode", "amadeus_hotel_offers_search"],
                "confidence": 0.95,
            })

        enriched.sort(key=lambda h: float(h["price"]["total"] or 0))
        budget_pick   = enriched[0] if enriched else None
        mid_idx       = len(enriched) // 2
        midrange_pick = enriched[mid_idx] if len(enriched) > 1 else None

        print(f"[HOTEL TOOL] Returning {len(enriched)} hotels. Budget: {budget_pick['name'] if budget_pick else 'None'}")

        return json.dumps({
            "source": "amadeus_hotels_by_geocode + amadeus_hotel_offers_search",
            "centroid": {
                "latitude":  centroid_lat,
                "longitude": centroid_lng,
                "note":      f"Centroid of {len(places)} visiting places",
            },
            "radius_km":          radius_km,
            "total_hotels_found": len(enriched),
            "recommended": {
                "budget":    budget_pick,
                "mid_range": midrange_pick,
            },
        }, indent=2)

    except ResponseError as e:
        return json.dumps({"error": str(e), "total_hotels_found": 0, "source": "amadeus_hotels_by_geocode"})
    except Exception as e:
        print(f"[HOTEL TOOL] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return json.dumps({"error": f"Unexpected error: {str(e)}", "total_hotels_found": 0})


# All 3 tools active now
tools = [google_search, amadeus_flight_search, amadeus_hotels_near_places]


# ─────────────────────────────────────────────
# 4. Pydantic Schemas
# ─────────────────────────────────────────────

class Activity(BaseModel):
    time_slot: str
    activity_name: str
    description: str
    location_zone: str
    latitude: float
    longitude: float
    price_estimate: str
    sources: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class DayPlan(BaseModel):
    day_number: int
    date: str
    theme: str
    geographic_cluster: str
    schedule: List[Activity]


class TripLogistics(BaseModel):
    visa_required: str
    currency: str
    local_transport: str
    estimated_daily_budget_excl_hotel: str


class ItineraryCentroid(BaseModel):
    latitude: float
    longitude: float
    note: str


class FlightData(BaseModel):
    flights: List[Dict[str, Any]]
    total_found: int


class HotelPrice(BaseModel):
    currency: str
    base: str
    total: str
    selling_total: str
    per_night: str


class HotelOption(BaseModel):
    hotel_id: str
    name: str
    chain_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    distance_to_centroid_km: Any
    closest_activities: List[str] = Field(default_factory=list)
    offer_id: str
    check_in: str
    check_out: str
    nights: int
    room_type: str
    bed_type: str
    board_type: str
    price: HotelPrice
    cancellation_policy: str
    payment_type: str
    why_recommended: str
    sources: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.95)


class FinalItinerary(BaseModel):
    tldr: str = Field(description="One-line summary, max 20 words")
    destination: str
    trip_purpose: str = Field(description="LEISURE | BUSINESS | UNKNOWN")
    provenance: List[str] = Field(default_factory=list)
    itinerary_centroid: ItineraryCentroid
    flights: FlightData
    hotels: List[HotelOption] = Field(default_factory=list)
    logistics: TripLogistics
    daily_itinerary: List[DayPlan]
    travel_tips: List[str]


# ─────────────────────────────────────────────
# 5. System Prompt
# ─────────────────────────────────────────────
SYSTEM_PROMPT_TEXT = """
You are "Voyage", a professional AI travel planner. You have three tools:
  - google_search              — find visiting places, hours, prices
  - amadeus_flight_search      — get real flights from Amadeus API
  - amadeus_hotels_near_places — get real hotels near visiting places from Amadeus API

REQUIRED SLOTS (ask if any are missing):
  origin (IATA), destination (IATA), departure_date (YYYY-MM-DD),
  adults (int), return_date (optional), cabin_class (default ECONOMY)

MANDATORY TOOL CALL SEQUENCE — always in this exact order:

STEP 1 — google_search
  Query: "top places to visit in <destination>"
  Extract: place names, prices, ratings.

STEP 2 — amadeus_flight_search
  Use: origin, destination, departure_date, return_date, adults, cabin_class.
  Copy ALL fields from tool output into flights section.

STEP 3 — amadeus_hotels_near_places
  After google_search, build places_with_coords using top 5 places from Step 1.
  Use YOUR OWN KNOWLEDGE to fill in lat/lng for each place name.
  Build this exact JSON string format:
  '[{"name":"Eiffel Tower","lat":48.8584,"lng":2.2945},
    {"name":"Louvre Museum","lat":48.8606,"lng":2.3376},
    {"name":"Notre-Dame","lat":48.8530,"lng":2.3499},
    {"name":"Sacre-Coeur","lat":48.8867,"lng":2.3431},
    {"name":"Arc de Triomphe","lat":48.8738,"lng":2.2950}]'

  Then call amadeus_hotels_near_places with:
    places_with_coords = <above JSON string>
    check_in_date      = departure_date
    check_out_date     = return_date (or departure_date + 3 days if one-way)
    adults             = adults

STEP 4 — Build daily_itinerary
  Use places from Step 1. Group by geographic_cluster per day.
  Each activity MUST include lat/lng (confidence <= 0.70 for estimated).

OUTPUT RULES:
- Pure JSON matching FinalItinerary schema exactly.
- flights: copy ENTIRE amadeus_flight_search output (flights list + total_found).
- hotels: extract recommended.budget and recommended.mid_range from hotel tool output.
- itinerary_centroid: copy from amadeus_hotels_near_places centroid field.
- All flight/hotel data MUST come from Amadeus tool outputs — never invent.
- If field missing: "UNVERIFIED: <field> not returned by API"
- Never output partial JSON.
"""


# ─────────────────────────────────────────────
# 6. LLMs
# ─────────────────────────────────────────────
research_llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0,
)
llm_with_tools = research_llm.bind_tools(tools)


# ─────────────────────────────────────────────
# 7. State
# ─────────────────────────────────────────────
class AgentState(TypedDict):
    messages: Annotated[List[AnyMessage], operator.add]
    final_output: Any


# ─────────────────────────────────────────────
# 8. Nodes
# ─────────────────────────────────────────────

def planner_node(state: AgentState):
    system_msg = SystemMessage(content=SYSTEM_PROMPT_TEXT)
    messages = [system_msg] + state["messages"]
    response = llm_with_tools.invoke(messages)
    print("[PLANNER] Ran successfully.")
    return {"messages": [response]}


def router(state: AgentState) -> Literal["tools", "formatter"]:
    last = state["messages"][-1]
    if getattr(last, "tool_calls", None):
        return "tools"
    return "formatter"


def verifier_node(state: AgentState):
    messages = state.get("messages", [])
    tool_outputs = [
        m.content for m in messages
        if isinstance(m, ToolMessage) and isinstance(m.content, str)
    ]

    print(f"[VERIFIER] Checking {len(tool_outputs)} tool outputs")
    problems = []

    flight_done = any("total_found" in t for t in tool_outputs)
    if not flight_done:
        problems.append("amadeus_flight_search has not been called yet. Call it now.")

    hotel_done = any("total_hotels_found" in t for t in tool_outputs)
    if not hotel_done:
        problems.append(
            "amadeus_hotels_near_places has not been called yet. "
            "Take the top 5 places from google_search, add lat/lng from your knowledge, "
            "build the places_with_coords JSON string, then call amadeus_hotels_near_places."
        )

    if problems:
        print(f"[VERIFIER] Issues found: {problems}")
        recheck = HumanMessage(
            content="VERIFIER ISSUES:\n" + "\n".join(f"- {p}" for p in problems)
            + "\nPlease call the missing tools to fix the issues."
        )
        return {"messages": [recheck]}

    print("[VERIFIER] All tools called successfully.")
    return {"messages": []}


def verifier_router(state: AgentState) -> Literal["planner", "formatter"]:
    msgs = state.get("messages", [])
    for m in reversed(msgs):
        if isinstance(m, HumanMessage) and isinstance(m.content, str) and m.content.startswith("VERIFIER"):
            print("[VERIFIER ROUTER] Issues found, routing back to planner.")
            return "planner"
    print("[VERIFIER ROUTER] All good, routing to formatter.")
    return "formatter"


def formatter_node(state: AgentState):
    print(f"[FORMATTER] Received {len(state['messages'])} messages.")
    structured_llm = research_llm.with_structured_output(FinalItinerary)

    synthesis_prompt = HumanMessage(content="""
Using ALL tool outputs in this conversation, generate the complete FinalItinerary JSON.

MAPPING RULES:
- flights:            Copy ENTIRE amadeus_flight_search output (flights list + total_found)
- hotels:             Extract recommended.budget and recommended.mid_range from
                      amadeus_hotels_near_places output as a list of 2 HotelOption objects
- itinerary_centroid: Copy latitude/longitude/note from amadeus_hotels_near_places centroid field
- daily_itinerary:    Build from google_search results with lat/lng per activity
- trip_purpose:       Set based on trip context (LEISURE for tourist trips)

If any field is missing from tool output use: "UNVERIFIED: <field> not returned by API"
Confidence: 0.95 for Amadeus data, 0.70 for LLM-estimated values.
Return ONLY valid JSON matching FinalItinerary schema exactly.
""")

    for attempt in range(2):
        try:
            result = structured_llm.invoke(state["messages"] + [synthesis_prompt])
            validated = FinalItinerary.model_validate(result)
            print("[FORMATTER] Success.")
            return {"final_output": validated}
        except ValidationError as e:
            print(f"[FORMATTER] Validation error attempt {attempt + 1}: {e}")
            if attempt == 1:
                return {"final_output": {"error": "Schema validation failed", "details": str(e)}}
            synthesis_prompt = HumanMessage(
                content=f"PREVIOUS JSON FAILED VALIDATION:\n{e}\nFix ALL errors and output valid JSON."
            )
        except Exception as e:
            print(f"[FORMATTER] Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            return {"final_output": {"error": str(e)}}


# ─────────────────────────────────────────────
# 9. Graph
# ─────────────────────────────────────────────
workflow = StateGraph(AgentState)

workflow.add_node("planner",   planner_node)
workflow.add_node("tools",     ToolNode(tools))
workflow.add_node("verifier",  verifier_node)
workflow.add_node("formatter", formatter_node)

workflow.set_entry_point("planner")
workflow.add_conditional_edges("planner",  router,          {"tools": "tools", "formatter": "formatter"})
workflow.add_edge("tools", "verifier")
workflow.add_conditional_edges("verifier", verifier_router, {"planner": "planner", "formatter": "formatter"})
workflow.add_edge("formatter", END)

app = workflow.compile()


# ─────────────────────────────────────────────
# 10. Run
# ─────────────────────────────────────────────
if __name__ == "__main__":
    user_request = """
    Plan a 3-day trip to Paris for 1 adult student.
    Origin: DEL (New Delhi)
    Destination: CDG (Paris)
    Departure: 2026-04-10
    Return: 2026-04-13
    Budget tier: budget
    Cabin class: ECONOMY
    """

    print("User Request:", user_request)
    print("\n--- Voyage Agent Thinking... ---\n")

    inputs = {"messages": [HumanMessage(content=user_request)]}

    try:
        result = app.invoke(inputs)
        final = result["final_output"]

        print("\n--- FINAL ITINERARY ---")
        if isinstance(final, dict) and "error" in final:
            print("ERROR:", json.dumps(final, indent=2))
        else:
            print(final.model_dump_json(indent=2))

    except Exception as e:
        print(f"\nCRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()