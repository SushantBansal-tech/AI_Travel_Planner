# 🚀 AI Travel Planner & Automated Booking Agent

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-Agentic%20Workflow-orange.svg)](https://langchain-ai.github.io/langgraph/)
[![Amadeus](https://img.shields.io/badge/Amadeus-API%20Integration-green.svg)](https://developers.amadeus.com/)

**End-to-End AI Agent** that **plans personalized trips**, **searches real flights/hotels**, and **auto-books** via Amadeus APIs. Production-grade with retries, fallbacks, and strict JSON outputs.

**Recruiter Takeaway**: Demonstrates **agentic AI**, **API orchestration**, **error-resilient automation**, and **travel domain expertise**.

## 🎯 Project Intention
Build a **\"Voyage\" AI agent** that:
1. Parses trip request → generates optimized itinerary
2. Calls **real APIs** (Amadeus + Google Search)
3. **Auto-books** cheapest options w/ retry logic
4. Returns **structured JSON** for downstream systems (txn_manager.py, persistence/)

**Production Patterns Used:**
```
LangGraph State Machine → Tool-Enforced Sequence → Verifier Loop → Pydantic Output
planner → (tools|verifier)* → formatter → FinalItinerary JSON
```

## 🛠 Tech Stack
```
Core: LangGraph + Gemini 2.5 Flash + Pydantic v2
APIs: Amadeus (flights/hotels/booking), SerpAPI (search)
Error Handling: 3x Retry + Fallbacks + Geo-Filtering
Schemas: Strict FinalItinerary (FlightData, HotelBooking, CabTransfers)
```

## 🚀 Quick Demo (1 Command)
```bash
pip install -r requirements.txt
python phase3_agent.py
```

**Input** (embedded example):
```
Plan 3-day Paris trip: DEL→CDG, 2026-04-10→13, 1 adult, budget/economy, John Doe
```

## 📊 **Sample Output: FinalItinerary JSON** 

```json
{
  "tldr": "3-day Paris budget trip: Eiffel→Louvre→Versailles w/ auto-booked hotel & cabs",
  "destination": "Paris (CDG)",
  "trip_purpose": "LEISURE",
  "itinerary_centroid": {
    "latitude": 48.8566,
    "longitude": 2.3522,
    "note": "Centroid of 12 visiting places"
  },
  "flights": {
    "flights": [
      {
        "type": "flight-offer",
        "id": "1",
        "itineraries": [...],
        "price": {"total": "650.00", "currency": "USD"},
        ...
      }
    ],
    "total_found": 10
  },
  "hotels": [
    {
      "hotel_id": "12345",
      "name": "Ibis Budget Paris Centre",
      "offer_id": "ABC123-DEF456",
      "latitude": 48.8670,
      "longitude": 2.3260,
      "distance_to_centroid_km": 1.2,
      "closest_activities": ["Eiffel Tower (~2.1 km)", "Louvre (~1.8 km)"],
      "price": {
        "currency": "USD",
        "total": "285.60",
        "per_night": "95.20"
      },
      "why_recommended": "Budget hotel 1.2km from activities",
      "confidence": 0.95
    }
  ],
  "hotel_booking": {
    "status": "CONFIRMED",
    "attempts_made": 1,
    "hotel_booking_id": "BOOK-789XYZ",
    "confirmation_number": "CONF-123456",
    "guest_name": "John Doe",
    "total_price": "285.60 USD",
    "source": "amadeus_hotel_orders"
  },
  "cab_transfers": {
    "total_legs": 12,
    "total_estimated_cost_eur": 78.50,
    "bookings": [
      {
        "day": 1,
        "leg": "CDG → Ibis Budget",
        "distance_km": 28.4,
        "vehicle_type": "Private Transfer",
        "price": "~€45.60",
        "status": "PRICE_ESTIMATE_ONLY",
        "booking_action": "Book via Uber/G7 Taxi"
      }
    ]
  },
  "daily_itinerary": [
    {
      "day_number": 1,
      "date": "2026-04-10",
      "theme": "Iconic Landmarks",
      "schedule": [
        {
          "time_slot": "09:00-11:00",
          "activity_name": "Eiffel Tower",
          "location_zone": "7th Arrondissement",
          "latitude": 48.8584,
          "longitude": 2.2945,
          "price_estimate": "€29.40/adult"
        }
      ]
    }
  ],
  "logistics": {
    "visa_required": "Schengen visa for Indian nationals",
    "currency": "EUR (€1=₹89)",
    "local_transport": "Paris Metro + Uber",
    "estimated_daily_budget_excl_hotel": "$60-90 USD"
  }
}
```

## 🔍 **Agent Workflow** (5-Tool Sequence)
```
1. google_search("top places Paris") → Eiffel, Louvre...
2. amadeus_flight_search(DEL→CDG) → 10 offers
3. amadeus_hotels_near_places(places_coords) → geo-centroid hotels
4. amadeus_book_hotel(best_offer_id) → CONFIRMED (3x retry)
5. book_cab_transfers(all_legs_json) → 12 rides w/ prices
↓
FinalItinerary JSON (verifier ensures all tools called)
```

**Key Innovations:**
- **Verifier Node**: Rejects incomplete tool calls
- **Geo-Filter**: Drops junk hotels outside city bbox
- **Fallback Chain**: API fail → distance-estimate → alternatives
- **Hardcoded Guards**: Skips unbookable TEST env offers

## 🧪 Run Full System
```bash
# Phase 1: RAG Knowledge Base
python phase1_brain.py

# Phase 2: Query Engine  
python phase2_rag.py

# Phase 3: Production Agent (auto-books)
python phase3_agent.py
```

## 📈 **Production Extensions** (Implemented)
- `txn_manager.py`: 2PC booking transactions
- `persistence/`: SQLite CRUD for bookings
- `payments/checkout.py`: Stripe integration ready
- `webhooks/`: Provider confirmations

## 🔧 Setup
```bash
pip install -r requirements.txt
cp .env.example .env  # Add API keys
python phase3_agent.py
```

## 🎯 Recruiter Highlights
| Feature | Value |
|---------|-------|
| **Real APIs** | Amadeus + SerpAPI (live data) |
| **Auto-Retry** | 3x exponential backoff |
| **JSON Output** | Strict Pydantic schemas |
| **Error-Resilient** | Fallbacks + geo-validation |
| **Scalable** | LangGraph state machine |

**Live Demo**: `python phase3_agent.py` → instant Paris trip w/ booking confirmation.

---

⭐ **Built for Production. Agentic AI at Scale.**

