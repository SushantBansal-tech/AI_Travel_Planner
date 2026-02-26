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