import os
from dotenv import load_dotenv
from amadeus import Client, ResponseError

load_dotenv()

client_id = os.getenv("AMADEUS_CLIENT_ID")
client_secret = os.getenv("AMADEUS_CLIENT_SECRET")

if not client_id or not client_secret:
    raise ValueError("Amadeus credentials not found in environment variables!")

print(f"Client ID loaded: {client_id[:6]}...")

amadeus = Client()

# ── Change these to test different routes/dates ──
origin = 'DEL'
destination = 'CDG'
departure_date = '2026-04-10'
return_date = '2026-04-13'   # set to '' for one-way
# ─────────────────────────────────────────────────

try:
    kwargs = dict(
        originLocationCode=origin,
        destinationLocationCode=destination,
        departureDate=departure_date,
        adults=1,
        max=10
    )
    if return_date:
        kwargs["returnDate"] = return_date

    response = amadeus.shopping.flight_offers_search.get(**kwargs)

    print(f"Trip type   : {'Round Trip' if return_date else 'One Way'}")
    print(f"Route       : {origin} --> {destination}")
    print(f"Departure   : {departure_date}")
    if return_date:
        print(f"Return      : {return_date}")
    print(f"Flights found: {len(response.data)}")
    print("-" * 50)

    for i, flight in enumerate(response.data):
        print(f"\nFlight #{i+1}")
        print(f"  Price    : {flight['price']['grandTotal']} {flight['price']['currency']}")
        print(f"  Airlines : {flight.get('validatingAirlineCodes', [])}")

        for j, itinerary in enumerate(flight['itineraries']):
            leg = "OUTBOUND" if j == 0 else "RETURN"
            print(f"  [{leg}] Duration: {itinerary['duration']}")

            for seg in itinerary['segments']:
                print(f"    {seg['departure']['iataCode']} ({seg['departure']['at']})"
                      f"  -->  "
                      f"{seg['arrival']['iataCode']} ({seg['arrival']['at']})"
                      f"  | Flight: {seg['carrierCode']}{seg['number']}"
                      f"  | Stops: {seg.get('numberOfStops', 0)}")

except ResponseError as e:
    print(f"API Error {e.status_code}: {e.response.result}")