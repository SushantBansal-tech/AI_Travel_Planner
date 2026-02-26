# [Keep everything the same until LLM section, then replace with this:]

from langchain_core.messages import AIMessage  # Add this import

# ─────────────────────────────────────────────
# 6.  FIXED LLM - Mock mode for quota issues
# ─────────────────────────────────────────────
class MockLLM:
    def invoke(self, messages):
        last_content = messages[-1].content if messages else ""
        
        print(f"MockLLM simulating: {last_content[:50]}...")
        
        if "Paris" in last_content and not any("flight" in str(m.content) for m in messages):
            return AIMessage(tool_calls=[{
                "name": "google_search",
                "args": {"query": "top places to visit in Paris Eiffel Tower Louvre Montmartre Versailles"}
            }])
        
        elif "google_search" in last_content:
            return AIMessage(tool_calls=[{
                "name": "amadeus_flight_search",
                "args": {
                    "origin": "DEL", "destination": "CDG", 
                    "departure_date": "2026-04-10", "return_date": "2026-04-13",
                    "adults": 1, "cabin_class": "ECONOMY"
                }
            }])
        
        elif "flight_offers_search" in last_content:
            places_json = json.dumps([
                {"name":"Eiffel Tower","lat":48.8584,"lng":2.2945},
                {"name":"Louvre","lat":48.8606,"lng":2.3376},
                {"name":"Montmartre","lat":48.8967,"lng":2.3490},
                {"name":"Versailles","lat":48.8049,"lng":2.1204}
            ])
            return AIMessage(tool_calls=[{
                "name": "amadeus_hotels_near_places",
                "args": {
                    "places_with_coords": places_json,
                    "check_in_date": "2026-04-10",
                    "check_out_date": "2026-04-13",
                    "adults": 1
                }
            }])
        
        else:
            return AIMessage(content=json.dumps({
                "tldr": "Budget 3-day Paris: Iconic sights + cheap flights/hotels",
                "destination": "Paris",
                "trip_purpose": "LEISURE",
                "provenance": ["google_search", "amadeus_flight_search", "amadeus_hotels_near_places"],
                "itinerary_centroid": {"latitude": 48.87, "longitude": 2.32, "note": "Central Paris"},
                "flights": {
                    "source": "amadeus_flight_offers_search",
                    "trip_purpose": "LEISURE",
                    "price_deal_label": "GOOD DEAL",
                    "price_metrics": {"first_quartile": "$450 USD", "third_quartile": "$750 USD"},
                    "cheapest_offer": {
                        "amadeus_offer_id": "mock-123",
                        "price": {"grand_total": "520", "currency": "USD"},
                        "itineraries": [{"duration": "P12H"}]
                    }
                },
                "hotels": [
                    {
                        "hotel_id": "mock-budget",
                        "name": "Paris Budget Inn",
                        "price": {"total": "250", "currency": "USD", "per_night": "83"},
                        "tier": "budget",
                        "confidence": 0.95
                    }
                ],
                "logistics": {
                    "visa_required": "Check Schengen visa",
                    "currency": "EUR",
                    "local_transport": "Paris Metro Navigo pass €30/week",
                    "estimated_daily_budget_excl_hotel": "$50-70"
                },
                "daily_itinerary": [
                    {
                        "day_number": 1,
                        "date": "2026-04-10",
                        "theme": "Iconic Paris",
                        "geographic_cluster": "Central Paris",
                        "schedule": [{"activity_name": "Eiffel Tower", "latitude": 48.8584, "longitude": 2.2945}]
                    }
                ],
                "travel_tips": ["Paris Metro pass saves money", "Book Versailles tickets online"]
            }))

# USE MOCK (no API needed) - swap back to Gemini when quota resets
research_llm = MockLLM()
llm_with_tools = research_llm