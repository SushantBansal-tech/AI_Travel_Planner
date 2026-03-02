import os
import json
from dotenv import load_dotenv
from amadeus import Client, ResponseError

# ─────────────────────────────────────────────
# Init & Auth
# ─────────────────────────────────────────────
load_dotenv()

CLIENT_ID = os.getenv("AMADEUS_CLIENT_ID")
CLIENT_SECRET = os.getenv("AMADEUS_CLIENT_SECRET")

if not CLIENT_ID or not CLIENT_SECRET:
    raise RuntimeError("❌ Amadeus API keys not found in .env")

amadeus = Client(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    hostname="test"  # FORCE test environment
)

print("✅ Amadeus client initialized (TEST)")

# ─────────────────────────────────────────────
# 1. Compute centroid
# ─────────────────────────────────────────────
def compute_centroid(places):
    lat = sum(p["latitude"] for p in places) / len(places)
    lon = sum(p["longitude"] for p in places) / len(places)
    return lat, lon

# ─────────────────────────────────────────────
# 2. Hotel list by geocode
# ─────────────────────────────────────────────
def get_hotel_ids_near_places(places, radius_km=10, limit=15):
    lat, lon = compute_centroid(places)

    print(f"\n📍 Searching hotels near ({lat:.4f}, {lon:.4f})")

    response = amadeus.reference_data.locations.hotels.by_geocode.get(
        latitude=lat,
        longitude=lon,
        radius=radius_km,
        radiusUnit="KM"
    )

    hotel_ids = [h["hotelId"] for h in response.data[:limit]]
    print(f"🏨 Found {len(hotel_ids)} hotels")
    return hotel_ids

# ─────────────────────────────────────────────
# 3. Fetch hotel metadata
# ─────────────────────────────────────────────
def fetch_hotel_details(hotel_ids):
    hotels = []

    for idx, hotel_id in enumerate(hotel_ids, start=1):
        try:
            res = amadeus.reference_data.locations.hotels.by_hotels.get(
                hotelIds=[hotel_id]
            )
        except ResponseError:
            continue

        h = res.data[0]
        hotels.append({
            "index": idx,
            "hotel_id": h["hotelId"],
            "name": h.get("name", "N/A"),
            "city": h.get("address", {}).get("cityName", "N/A"),
            "country": h.get("address", {}).get("countryCode", "N/A"),
            "rating": h.get("rating", "N/A")
        })

    return hotels

# ─────────────────────────────────────────────
# 4. Automatic retry + fallback
# ─────────────────────────────────────────────
def resolve_first_bookable_offer(
    hotels,
    check_in,
    check_out,
    adults,
    max_attempts=10
):
    print("\n🔎 Resolving bookable hotel offers...\n")

    attempts = 0

    for hotel in hotels:
        if attempts >= max_attempts:
            break

        print(f"→ Checking: {hotel['name']}")

        try:
            response = amadeus.shopping.hotel_offers_search.get(
                hotelIds=[hotel["hotel_id"]],
                adults=adults,
                checkInDate=check_in,
                checkOutDate=check_out
            )
        except ResponseError:
            print("   ❌ Offers API not supported\n")
            attempts += 1
            continue

        offers = response.data[0].get("offers", [])

        if not offers:
            print("   ❌ No offers available\n")
            attempts += 1
            continue

        offer = offers[0]
        print(f"   ✅ Offer found | {offer['price']['total']} {offer['price']['currency']}\n")

        return {
            "hotel": hotel,
            "offer_id": offer["id"],
            "price": offer["price"]
        }

    return None

# ─────────────────────────────────────────────
# 5. Guest input
# ─────────────────────────────────────────────
def get_guest():
    return {
        "first": input("First name: ") or "TEST",
        "last": input("Last name: ") or "USER",
        "email": input("Email: ") or "test@example.com",
        "phone": input("Phone: ") or "+911234567890",
    }

# ─────────────────────────────────────────────
# 6. Book hotel (FINAL)
# ─────────────────────────────────────────────
def book_hotel(offer_id, guest):
    guests = [
        {
            "id": 1,
            "name": {
                "title": "MR",
                "firstName": guest["first"].upper(),
                "lastName": guest["last"].upper()
            },
            "contact": {
                "email": guest["email"],
                "phone": guest["phone"]
            }
        }
    ]

    payments = [
        {
            "id": 1,
            "method": "creditCard",
            "card": {
                "vendorCode": "VI",
                "cardNumber": "4111111111111111",
                "expiryDate": "2026-01"
            }
        }
    ]

    response = amadeus.booking.hotel_bookings.post(
        offer_id,
        guests,
        payments
    )

    print("\n✅ BOOKING CONFIRMED")
    print(json.dumps(response.data, indent=2))

# ─────────────────────────────────────────────
# 7. Run pipeline
# ─────────────────────────────────────────────
if __name__ == "__main__":

    places = [
        {"name": "Eiffel Tower", "latitude": 48.8584, "longitude": 2.2945},
        {"name": "Louvre Museum", "latitude": 48.8606, "longitude": 2.3376},
        {"name": "Notre Dame", "latitude": 48.8530, "longitude": 2.3499}
    ]

    check_in = "2026-04-10"
    check_out = "2026-04-13"
    adults = 1

    hotel_ids = get_hotel_ids_near_places(places)
    hotels = fetch_hotel_details(hotel_ids)

    if not hotels:
        raise RuntimeError("❌ No hotels found")

    result = resolve_first_bookable_offer(
        hotels,
        check_in,
        check_out,
        adults
    )

    if not result:
        raise RuntimeError("❌ No bookable hotels found in this area")

    selected = result["hotel"]
    offer_id = result["offer_id"]

    print(f"\n🏨 Selected Hotel: {selected['name']}")
    print(f"💰 Price: {result['price']['total']} {result['price']['currency']}")

    guest = get_guest()
    confirm = input("\nConfirm booking? (yes/no): ").lower()

    if confirm == "yes":
        book_hotel(offer_id, guest)
    else:
        print("❌ Booking cancelled")
