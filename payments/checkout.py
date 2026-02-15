import os
import stripe
from persistence.db import SessionLocal
from persistence import crud
from booking_schemas import BookingRequest
from txn_manager import TransactionManager
from booking_tools import MockFlightProvider, MockHotelProvider, MockCabProvider

stripe.api_key = os.getenv("STRIPE_API_KEY")

SUCCESS_URL = os.getenv("STRIPE_SUCCESS_URL", "https://example.com/success")
CANCEL_URL = os.getenv("STRIPE_CANCEL_URL", "https://example.com/cancel")

# Provider mapping for confirm step. Replace with real provider adapters in production.
PROVIDERS = {
    "flight": MockFlightProvider(),
    "hotel": MockHotelProvider(),
    "cab": MockCabProvider(),
}

def create_checkout_session(db_booking_id: int):
    """
    Create Stripe Checkout Session for a booking stored in DB (by id).
    Returns the session object (client can redirect to session.url).
    """
    db = SessionLocal()
    db_req = crud.get_booking_by_id(db, db_booking_id)
    if not db_req:
        raise ValueError("Booking not found")

    # convert DB model to pydantic to build line items
    pyd_req = crud.model_to_pydantic(db_req)

    line_items = []
    for it in pyd_req.items:
        # Stripe expects unit_amount in cents
        unit_amount = int(round(it.total * 100))
        line_items.append({
            "price_data": {
                "currency": it.currency.lower(),
                "product_data": {"name": it.description[:100]},
                "unit_amount": unit_amount,
            },
            "quantity": 1,
        })

    # embed booking DB id and idempotency key in metadata so webhook can look it up
    metadata = {
        "booking_db_id": str(db_req.id),
        "idempotency_key": db_req.idempotency_key or ""
    }

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=line_items,
        mode="payment",
        success_url=SUCCESS_URL + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=CANCEL_URL,
        metadata=metadata,
    )
    return session

def handle_stripe_checkout_completed(session: dict):
    """
    Called after stripe webhook validates a 'checkout.session.completed' event.
    This will confirm bookings by loading the BookingRequest from DB and calling TransactionManager.confirm_all.
    """
    db = SessionLocal()
    booking_db_id = session.get("metadata", {}).get("booking_db_id")
    if not booking_db_id:
        return {"error": "no booking id in session metadata"}

    db_req = crud.get_booking_by_id(db, int(booking_db_id))
    if not db_req:
        return {"error": "booking not found"}

    # convert to pydantic BookingRequest
    pyd_req = crud.model_to_pydantic(db_req)

    # In a real system, payment_auth would include payment confirmation details; here it's mocked
    payment_auth = {"type": "stripe", "id": session.get("id")}

    # Use TransactionManager to confirm (providers currently mocked)
    tm = TransactionManager(pyd_req, PROVIDERS)
    updated = tm.confirm_all(payment_auth)

    # Persist updates back to DB
    crud.save_updates_from_pydantic(db, db_req, updated)

    return {"status": "confirmed" if updated.status == "confirmed" else "failed"}