import os
import stripe
from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import JSONResponse
from persistence.db import init_db, SessionLocal
from persistence import crud
from payments.stripe_checkout import handle_stripe_checkout_completed

app = FastAPI()

# initialize DB (creates tables)
init_db()

stripe.api_key = os.getenv("STRIPE_API_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

@app.post("/webhook/stripe")
async def stripe_webhook(request: Request, stripe_signature: str = Header(None)):
    payload = await request.body()
    sig_header = stripe_signature or request.headers.get("stripe-signature")
    if not STRIPE_WEBHOOK_SECRET:
        # If not set, attempt to parse without verification (only for local dev; NOT for prod)
        event = stripe.Event.construct_from(request.json(), stripe.api_key)  # type: ignore
    else:
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
        except stripe.error.SignatureVerificationError:
            raise HTTPException(status_code=400, detail="Invalid Stripe signature")

    # Handle the event types we care about
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        result = handle_stripe_checkout_completed(session)
        return JSONResponse(content={"received": True, "result": result})

    # Other events can be handled as needed
    return JSONResponse(content={"received": True})

@app.post("/webhook/provider")
async def provider_webhook(request: Request):
    """
    Example provider webhook receiver. Providers (flight/hotel APIs) often
    send asynchronous updates (confirmation, cancellations). This endpoint
    expects JSON with {"booking_db_id": ..., "item_id": ..., "status": "...", ...}
    """
    payload = await request.json()
    booking_db_id = payload.get("booking_db_id")
    item_id = payload.get("item_id")
    status = payload.get("status")
    meta = payload.get("meta", {})

    if not booking_db_id or not item_id:
        raise HTTPException(status_code=400, detail="Missing booking_db_id or item_id")

    db = SessionLocal()
    db_req = crud.get_booking_by_id(db, int(booking_db_id))
    if not db_req:
        raise HTTPException(status_code=404, detail="Booking not found")

    # find the item and update
    item_model = None
    for it in db_req.items:
        if it.item_id == item_id:
            item_model = it
            break

    if not item_model:
        raise HTTPException(status_code=404, detail="Item not found")

    # update fields
    item_model.status = status
    # merge incoming meta
    existing_meta = item_model.meta or {}
    existing_meta.update(meta)
    item_model.meta = existing_meta
    db.add(item_model)
    db.commit()
    return JSONResponse(content={"ok": True})