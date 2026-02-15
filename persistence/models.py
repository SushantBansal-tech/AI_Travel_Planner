from sqlalchemy import Column, Integer, String, Float, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from .db import Base

class BookingRequestModel(Base):
    __tablename__ = "booking_requests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    itinerary_id = Column(String, index=True)
    total_amount = Column(Float)
    currency = Column(String(8))
    idempotency_key = Column(String, unique=True, index=True, nullable=True)
    status = Column(String(32), default="created")

    # JSON field for quick access to additional metadata
    meta = Column(JSON, default={})

    items = relationship("BookingItemModel", back_populates="booking", cascade="all, delete-orphan")

class BookingItemModel(Base):
    __tablename__ = "booking_items"

    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("booking_requests.id", ondelete="CASCADE"), index=True)
    item_id = Column(String, index=True)
    item_type = Column(String(32))
    description = Column(Text)
    provider = Column(String(128))
    price = Column(Float)
    currency = Column(String(8))
    taxes = Column(Float, default=0.0)
    total = Column(Float)
    hold_id = Column(String, nullable=True)
    confirmed_id = Column(String, nullable=True)
    status = Column(String(32), default="pending")
    meta = Column(JSON, default={})

    booking = relationship("BookingRequestModel", back_populates="items")