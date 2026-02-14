from pydantic import BaseModel, Field
from typing import List, Literal, Optional


class BookingItem(BaseModel):
    item_id: str                 # local id
    item_type: Literal["flight", "hotel", "attraction", "cab"]
    description: str
    provider: str                # provider name (or candidate list)
    price: float
    currency: str
    taxes: float = 0.0
    total: float
    hold_id: Optional[str] = None   # provider hold/reservation id
    confirmed_id: Optional[str] = None
    status: Literal["pending", "held", "confirmed", "failed", "cancelled"] = "pending"
    meta: dict = Field(default_factory=dict)  # raw provider response


class BookingRequest(BaseModel):
    user_id: str
    itinerary_id: str
    items: List[BookingItem]
    total_amount: float
    currency: str
    idempotency_key: Optional[str] = None
    status: Literal["created", "authorized", "confirmed", "failed", "cancelled"] = "created"