import os
from dotenv import load_dotenv
from typing import Annotated, List, Literal, TypedDict, Any
import operator
from pydantic import BaseModel, Field, ValidationError

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.utilities import SerpAPIWrapper
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage, AnyMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
import re
import uuid

# Booking demo imports (requires the files you added: booking_schemas.py, booking_tools.py, txn_manager.py)
from booking_schemas import BookingItem, BookingRequest
from booking_tools import MockFlightProvider, MockHotelProvider, MockCabProvider
from txn_manager import TransactionManager

# --- 1. Load Environment ---
load_dotenv()

# --- 2. Tools ---
search = SerpAPIWrapper()

@tool
def google_search(query: str):
    """
    Use this tool to find:
    1. Flight & Hotel prices.
    2. OPENING HOURS of attractions.
    3. LOCATIONS (e.g. 'Is Senso-ji near Tokyo Skytree?').
    """
    return search.run(query)

tools = [google_search]

# --- 3. Schema (with provenance & confidence) ---
class Activity(BaseModel):
    time_slot: str = Field(description="e.g., '09:00 AM - 11:30 AM'")
    activity_name: str = Field(description="Name of the place or activity")
    description: str = Field(description="What to do there")
    location_zone: str = Field(description="Neighborhood name (e.g., 'Shibuya', 'Downtown')")
    price_estimate: str = Field(description="Cost of ticket/entry if any")
    sources: List[str] = Field(default_factory=list, description="URLs or tool identifiers used to verify this activity")
    confidence: float = Field(default=0.0, description="Confidence score 0.0-1.0")

class DayPlan(BaseModel):
    day_number: int
    theme: str = Field(description="Theme of the day")
    schedule: List[Activity] = Field(description="Chronological list of activities")

class TripLogistics(BaseModel):
    flight_details: str = Field(description="Cheapest flight found with price and airline")
    hotel_details: str = Field(description="Budget hotel found with price and location")
    total_trip_cost: str = Field(description="Total estimated cost")
    sources: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0)

class FinalItinerary(BaseModel):
    destination: str
    logistics: TripLogistics
    daily_itinerary: List[DayPlan]
    provenance: List[str] = Field(default_factory=list, description="Top-level provenance sources")
    travel_tips: str = Field(description="Tips for saving money")

# --- 4. The Brain / LLMs ---
SYSTEM_PROMPT_TEXT = """
You are "Voyage", a professional AI travel planner. Follow these rules exactly:

1) Format:
   - At the top include a 1-line TL;DR summary (<= 20 words).
   - After that provide a structured JSON object that conforms exactly to the FinalItinerary schema (fields: destination, logistics, daily_itinerary, travel_tips). Each Activity must include a "sources" list and a "confidence" score (0.0-1.0).
   - If you cannot verify a fact (price, opening hour, address), say exactly: "UNVERIFIED: <field> — I couldn't verify this." Do not invent values.

2) Factuality:
   - Use tool outputs and retrieved documents only. Do not hallucinate. Every factual claim must cite at least one source; prefer 2+ corroborating sources when available.
   - For price/currency, use numeric values with currency codes (e.g., "120.00 USD").
   - For dates/times use ISO-like format e.g., "2026-02-14" or "09:00".

3) Behavior:
   - If the user request lacks a required slot (dates, travelers, budget), ask exactly one short clarifying question.
   - Keep the assistant concise and point-to-point. No long marketing copy.
   - For creative suggestions (ideas for romantic activities), use creative LLM instance.

4) Output hygiene:
   - Provide "sources" as absolute URLs (or tool identifiers) and a "confidence" float.
   - Include a "provenance" top-level list in the FinalItinerary summarizing the key sources used.

Failure to follow the rules means reject and ask to re-run verification.
"""

research_llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0, system_instruction=SYSTEM_PROMPT_TEXT)
creative_llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.7)  # for creative suggestions

llm_with_tools = research_llm.bind_tools(tools)

# --- 5. FIXED State ---
class AgentState(TypedDict):
    messages: Annotated[List[AnyMessage], operator.add]  # Proper accumulation
    final_output: Any  # will set to FinalItinerary instance later

# NODE 1: Planner (unchanged except using research_llm bound tools)
def planner_node(state: AgentState):
    response = llm_with_tools.invoke(state['messages'])
    return {"messages": [response]}

# helper: robust price/currency extraction (case-insensitive)
def _extract_price_and_currency(s: str):
    if not s:
        return None, None
    # Try explicit ISO currency codes first (case-insensitive)
    m = re.search(r'([0-9]+(?:\.[0-9]{1,2})?)\s*([A-Z]{3})', s, flags=re.I)
    if m:
        try:
            return float(m.group(1)), m.group(2).upper()
        except:
            return None, None
    # Try common currency symbols
    m2 = re.search(r'([$€£])\s*([0-9]+(?:\.[0-9]{1,2})?)', s)
    if m2:
        symbol = m2.group(1)
        cur_map = {'$':'USD', '€':'EUR', '£':'GBP'}
        try:
            return float(m2.group(2)), cur_map.get(symbol, None)
        except:
            return None, None
    return None, None

# Verifier node: returns messages requesting recheck if problems found.
def verifier_node(state: AgentState):
    messages = state.get('messages', [])
    problems = []
    for msg in messages:
        text = ""
        if hasattr(msg, "content"):
            text = msg.content if isinstance(msg.content, str) else str(msg.content)
        text_lower = text.lower()
        # tokens to look for (lowercased)
        tokens = ["usd", "eur", "$", "€", "price", "cost"]
        if any(t in text_lower for t in tokens):
            price, currency = _extract_price_and_currency(text)
            if price is None:
                problems.append({"field":"price_format", "msg":"Could not parse price", "example_text": text[:200]})
            else:
                if price < 0 or price > 100000:
                    problems.append({"field":"price_range", "msg":"Price out of plausible range", "value": price})
    # If problems found, create a recheck prompt message that planner can handle
    if problems:
        recheck_prompt = HumanMessage(content=f"VERIFIER: Found issues: {problems}. Please re-run the necessary tools with clearer queries and include URL sources. Return the tool call plan as JSON.")
        # return messages that the graph will feed back to planner
        return {"messages": [recheck_prompt]}
    # No issues: return empty messages so router can move to formatter
    return {"messages": []}

# Router used after planner_node to decide tools vs formatter
def router(state: AgentState) -> Literal["tools", "formatter"]:
    last_message = state['messages'][-1]
    if getattr(last_message, "tool_calls", None):
        return "tools"
    return "formatter"

# Router for verifier -> decide to re-run planner or continue to formatter
def verifier_router(state: AgentState) -> Literal["planner", "formatter"]:
    # if verifier appended a HumanMessage that contains "VERIFIER: Found issues", go back to planner
    msgs = state.get('messages', [])
    for m in msgs:
        if isinstance(m, HumanMessage) and isinstance(m.content, str) and m.content.startswith("VERIFIER:"):
            return "planner"
    return "formatter"

# Formatter node: strong structured output + validation
def formatter_node(state: AgentState):
    structured_llm = research_llm.with_structured_output(FinalItinerary)
    synthesis_prompt = HumanMessage(content="""Based on ALL the research (tool outputs, retrieved docs):
Generate the complete FinalItinerary JSON, include per-field 'sources' and 'confidence' between 0.0 and 1.0.
If you cannot verify a fact, set the field value to 'UNVERIFIED: <field>' and explain in travel_tips.
Return only valid JSON matching the schema.""")
    final_json = structured_llm.invoke(state['messages'] + [synthesis_prompt])

    # Validate Pydantic (extra guard)
    try:
        if isinstance(final_json, FinalItinerary):
            validated = final_json
        else:
            validated = FinalItinerary.model_validate(final_json)
    except ValidationError as e:
        retry_prompt = HumanMessage(content=f"Output failed validation: {e}\nPlease re-output only the FinalItinerary JSON exactly matching the schema.")
        final_json = structured_llm.invoke(state['messages'] + [retry_prompt])
        validated = FinalItinerary.model_validate(final_json)

    return {"final_output": validated}

# ---- Mock booking flow integration (demo helper) ----
def run_mock_booking_for_itinerary(final_itinerary: FinalItinerary, user_id: str = "user_demo"):
    """
    Build a simple BookingRequest from FinalItinerary and run the mocked booking flow.
    final_itinerary: the FinalItinerary Pydantic object returned by your formatter_node
    This function is ONLY for demo/testing and should be replaced with a proper booking
    builder that maps itinerary details to concrete providers/options.
    """
    # For demo, create one flight + one hotel + one cab item using simple approximations.
    items = []

    # Flight (parse numeric price if possible)
    flight_price = 0.0
    try:
        flight_text = final_itinerary.logistics.flight_details
        m = re.search(r'([0-9]+(?:\.[0-9]{1,2})?)', str(flight_text))
        if m:
            flight_price = float(m.group(1))
    except Exception:
        flight_text = "UNVERIFIED flight info"

    items.append(BookingItem(
        item_id="flight-" + str(uuid.uuid4())[:8],
        item_type="flight",
        description=str(flight_text),
        provider="mock_flight",
        price=flight_price or 420.0,
        currency="USD",
        taxes=30.0,
        total=(flight_price or 420.0) + 30.0
    ))

    # Hotel (parse numeric price if possible)
    hotel_price = 0.0
    try:
        hotel_text = final_itinerary.logistics.hotel_details
        m2 = re.search(r'([0-9]+(?:\.[0-9]{1,2})?)', str(hotel_text))
        if m2:
            hotel_price = float(m2.group(1))
    except Exception:
        hotel_text = "UNVERIFIED hotel info"

    items.append(BookingItem(
        item_id="hotel-" + str(uuid.uuid4())[:8],
        item_type="hotel",
        description=str(hotel_text),
        provider="mock_hotel",
        price=hotel_price or 60.0,
        currency="USD",
        taxes=10.0,
        total=(hotel_price or 60.0) + 10.0
    ))

    # Cab (estimate)
    items.append(BookingItem(
        item_id="cab-" + str(uuid.uuid4())[:8],
        item_type="cab",
        description="Airport pickup / local transfers (estimate)",
        provider="mock_cab",
        price=35.0,
        currency="USD",
        taxes=0.0,
        total=35.0
    ))

    booking_req = BookingRequest(
        user_id=user_id,
        itinerary_id=getattr(final_itinerary, "destination", "itn_demo"),
        items=items,
        total_amount=sum(i.total for i in items),
        currency="USD",
        idempotency_key=str(uuid.uuid4())
    )

    # Wire mock providers
    providers = {
        "flight": MockFlightProvider(),
        "hotel": MockHotelProvider(),
        "cab": MockCabProvider(),
    }

    tm = TransactionManager(booking_req, providers)

    print("\n--- Starting mocked booking flow (reserve) ---")
    booking_after_reserve = tm.reserve_all()
    for it in booking_after_reserve.items:
        print(f"RESERVE: {it.item_id}: status={it.status}, hold_id={it.hold_id}, meta={it.meta}")

    # Simulate payment authorization (in real app, use hosted checkout and webhooks)
    payment_auth = {"type": "mock", "id": "paytok_demo"}

    print("\n--- Confirming bookings (mock) ---")
    booking_after_confirm = tm.confirm_all(payment_auth)
    print("\n--- Booking result ---")
    print("booking_request.status:", booking_after_confirm.status)
    for it in booking_after_confirm.items:
        print(f"FINAL: {it.item_id}: status={it.status}, confirmed_id={it.confirmed_id}, meta={it.meta}")

    return booking_after_confirm
# ---- end mock booking helper ----

# --- 6. FIXED Graph (wired correctly) ---
workflow = StateGraph(AgentState)

workflow.add_node("planner", planner_node)
workflow.add_node("tools", ToolNode(tools))
workflow.add_node("verifier", verifier_node)
workflow.add_node("formatter", formatter_node)

workflow.set_entry_point("planner")
workflow.add_conditional_edges("planner", router, {"tools": "tools", "formatter": "formatter"})
workflow.add_edge("tools", "verifier")
workflow.add_conditional_edges("verifier", verifier_router, {"planner": "planner", "formatter": "formatter"})
workflow.add_edge("formatter", END)

app = workflow.compile()

# --- 7. Execution (Unchanged, minor robustness) ---
if __name__ == "__main__":
    user_request = """
    Plan a 3-day trip to Paris for a student.
    Budget: Minimal.
    Must Visit: Eiffel Tower, Louvre, Montmartre, and Versailles.
    """

    print(f"User Request: {user_request}")
    print("\n--- 🧠 Agent is Thinking (Checking Locations & Prices)... ---")

    inputs = {"messages": [HumanMessage(content=user_request)]}

    try:
        # Stream progress (app.stream may yield nodes' outputs)
        for output in app.stream(inputs):
            for key, value in output.items():
                print(f"✅ Finished Node: {key}")

        result = app.invoke(inputs)
        print("\n--- ✅ SMART ITINERARY GENERATED ---")
        # result["final_output"] should be a FinalItinerary Pydantic model (formatter_node ensures validation)
        final_itinerary = result.get("final_output")
        print(final_itinerary.model_dump_json(indent=2))

        # DEMO: run mocked booking flow based on the generated itinerary
        # (This is for testing/demo only. Replace with real booking adapters and payment flow later.)
        run_mock_booking_for_itinerary(final_itinerary, user_id="user_demo")

    except Exception as e:
        print(f"\n❌ Error Occurred: {e}")
        import traceback
        traceback.print_exc()