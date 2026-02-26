import os
from dotenv import load_dotenv
from amadeus import Client, ResponseError

load_dotenv()

amadeus = Client(
    client_id=os.getenv("AMADEUS_CLIENT_ID"),
    client_secret=os.getenv("AMADEUS_CLIENT_SECRET")
)


def compute_centroid(places: list[dict]) -> tuple[float, float]:
    avg_lat = sum(p["latitude"] for p in places) / len(places)
    avg_lon = sum(p["longitude"] for p in places) / len(places)
    return avg_lat, avg_lon


def search_hotels_near_visited_places(
    visited_places: list[dict],
    check_in_date: str,
    check_out_date: str,
    adults: int = 1,
    radius_km: int = 10
) -> list[dict]:

    if not visited_places:
        print("No places provided.")
        return []

    try:
        # STEP 1: Compute centroid
        centroid_lat, centroid_lon = compute_centroid(visited_places)
        place_names = ", ".join(p["name"] for p in visited_places)
        print(f"Places to visit : {place_names}")
        print(f"Centroid        : {centroid_lat:.4f}, {centroid_lon:.4f}")
        print(f"Searching hotels within {radius_km}km...\n")

        # STEP 2: Get hotel IDs from geocode
        hotels_near_centroid = amadeus.reference_data.locations.hotels.by_geocode.get(
            latitude=centroid_lat,
            longitude=centroid_lon,
            radius=radius_km,
            radiusUnit="KM"
        )

        hotel_ids = [hotel['hotelId'] for hotel in hotels_near_centroid.data[:20]]

        if not hotel_ids:
            print("No hotels found near your visited places.")
            return []

        print(f"Found {len(hotel_ids)} hotel IDs. Fetching hotel details...\n")

        # STEP 3: Loop through each hotel ID and fetch details via by_hotels
        results = []

        for hotel_id in hotel_ids:
            try:
                response = amadeus.reference_data.locations.hotels.by_hotels.get(
                    hotelIds=[hotel_id]
                )

                if response.data:
                    hotel = response.data[0]
                    name    = hotel.get('name', 'N/A')
                    address = hotel.get('address', {})
                    city    = address.get('cityName', 'N/A')
                    country = address.get('countryCode', 'N/A')

                    print(f"🏨 {name} | {city}, {country} | ID: {hotel_id}")

                    results.append({
                        "hotel_id":   hotel_id,
                        "hotel_name": name,
                        "city":       city,
                        "country":    country
                    })

            except ResponseError as e:
                print(f"Skipping {hotel_id}: {e}")
                continue

        return results

    except ResponseError as e:
        print(f"API Error: {e}")
        return []


# ── Example Usage ──
if __name__ == "__main__":
    paris_places = [
        {"name": "Eiffel Tower",  "latitude": 48.8584, "longitude": 2.2945},
        {"name": "Louvre Museum", "latitude": 48.8606, "longitude": 2.3376},
        {"name": "Notre Dame",    "latitude": 48.8530, "longitude": 2.3499},
    ]

    hotels = search_hotels_near_visited_places(
        visited_places=paris_places,
        check_in_date="2026-04-10",
        check_out_date="2026-04-13",
        adults=1,
        radius_km=10
    )