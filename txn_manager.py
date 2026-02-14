import uuid
from typing import Dict

from booking_schemas import BookingRequest, BookingItem


class TransactionManager:
    """
    Simple two-phase booking transaction manager (reserve -> confirm -> compensate).
    Providers mapping should be like: {"flight": provider_client, "hotel": provider_client, ...}
    Each provider must implement .reserve(item), .confirm(item, payment_auth), .cancel_hold(hold_id)
    """

    def __init__(self, booking_request: BookingRequest, providers: Dict[str, object]):
        self.request = booking_request
        self.providers = providers

    def reserve_all(self) -> BookingRequest:
        """
        Attempt to place holds for each booking item.
        Updates item.status to 'held' or 'failed'.
        Returns the updated BookingRequest.
        """
        for item in self.request.items:
            provider = self.providers.get(item.item_type)
            if not provider:
                item.status = "failed"
                item.meta = {"error": "no_provider"}
                continue
            resp = provider.reserve(item)
            if getattr(resp, "success", False):
                item.hold_id = resp.hold_id
                item.status = "held"
                item.meta = resp.raw
            else:
                item.status = "failed"
                item.meta = getattr(resp, "raw", {"error": "reserve_failed"})
        return self.request

    def confirm_all(self, payment_auth) -> BookingRequest:
        """
        Confirm held items after payment authorization.
        If any confirm fails, run compensate() and set request.status = 'failed'.
        Otherwise set request.status = 'confirmed'.
        """
        for item in self.request.items:
            if item.status != "held":
                continue
            provider = self.providers.get(item.item_type)
            resp = provider.confirm(item, payment_auth)
            if getattr(resp, "success", False):
                item.confirmed_id = resp.confirmed_id
                item.status = "confirmed"
                # merge raw response into meta
                item.meta.update(getattr(resp, "raw", {}))
            else:
                item.status = "failed"
                item.meta.update(getattr(resp, "raw", {"error": "confirm_failed"}))
        if any(i.status == "failed" for i in self.request.items):
            # on failure, try to cleanup holds to avoid partial bookings
            self.compensate()
            self.request.status = "failed"
            return self.request
        self.request.status = "confirmed"
        return self.request

    def compensate(self):
        """
        Cancel any holds for items that had hold_id set.
        """
        for item in self.request.items:
            if item.hold_id:
                provider = self.providers.get(item.item_type)
                try:
                    provider.cancel_hold(item.hold_id)
                    # mark cancelled if it was held and now cancelled
                    if item.status not in ("confirmed",):
                        item.status = "cancelled"
                except Exception:
                    # In production: log and schedule retry
                    pass