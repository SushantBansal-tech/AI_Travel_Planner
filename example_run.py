"""
Run this script to see a full mocked booking flow:
 - create BookingItems
 - create BookingRequest
 - reserve_all() -> some items become 'held' or 'failed' (if provider missing)
 - simulate payment_auth and call confirm_all()
 - print final results
"""

from booking_schemas import BookingItem, BookingRequest
from booking_tools import MockFlightProvider, MockHotelProvider, MockCabProvider
from txn_manager import TransactionManager
import uuid

def main():
    # Build items (flight, hotel, cab)
    item1 = BookingItem(
        item_id="flight-1",
        item_type="flight",
        description="NYC -> PAR, Economy, non-stop",
        provider="mock_flight",
        price=420.0,
        currency="USD",
        taxes=30.0,
        total=450.0
    )

    item2 = BookingItem(
        item_id="hotel-1",
        item_type="hotel",
        description="Budget hotel, 4 nights - shared bathroom",
        provider="mock_hotel",
        price=240.0,
        currency="USD",
        taxes=20.0,
        total=260.0
    )

    item3 = BookingItem(
        item_id="cab-1",
        item_type="cab",
        description="Airport pickup to hotel",
        provider="mock_cab",
        price=35.0,
        currency="USD",
        taxes=0.0,
        total=35.0
    )

    booking_req = BookingRequest(
        user_id="user_123",
        itinerary_id="itn_demo_001",
        items=[item1, item2, item3],
        total_amount=item1.total + item2.total + item3.total,
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

    print("=== Reserve phase ===")
    booking_after_reserve = tm.reserve_all()
    for it in booking_after_reserve.items:
        print(f"- {it.item_id}: status={it.status}, hold_id={it.hold_id}, meta={it.meta}")

    # Simulate getting payment authorization (in real app: hosted checkout)
    payment_auth = {"type": "mock_payment", "id": "paytok_abc123"}

    print("\n=== Confirm phase ===")
    booking_after_confirm = tm.confirm_all(payment_auth)

    print("\n=== Final booking result ===")
    print("Booking status:", booking_after_confirm.status)
    for it in booking_after_confirm.items:
        print(f"- {it.item_id}: status={it.status}, hold_id={it.hold_id}, confirmed_id={it.confirmed_id}, meta={it.meta}")


if __name__ == "__main__":
    main()