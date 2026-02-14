import random
import time


class ProviderResponse:
    def __init__(self, success: bool, hold_id: str = None, confirmed_id: str = None, raw: dict = None):
        self.success = success
        self.hold_id = hold_id
        self.confirmed_id = confirmed_id
        self.raw = raw or {}


class MockFlightProvider:
    """
    Mock flight provider: deterministic simple responses for demo / testing.
    """

    def reserve(self, item):
        # Simulate some latency
        time.sleep(0.05)
        hold_id = f"hold-flight-{item.item_id}"
        return ProviderResponse(success=True, hold_id=hold_id, raw={"price": item.price, "provider": "mock_flight"})

    def confirm(self, item, payment_auth):
        time.sleep(0.05)
        confirmed_id = f"CONF-FLT-{item.item_id}"
        return ProviderResponse(success=True, confirmed_id=confirmed_id, raw={"ticket_id": "TICKET-" + item.item_id})

    def cancel_hold(self, hold_id):
        time.sleep(0.02)
        return True


class MockHotelProvider:
    def reserve(self, item):
        time.sleep(0.05)
        hold_id = f"hold-hotel-{item.item_id}"
        return ProviderResponse(success=True, hold_id=hold_id, raw={"price": item.price, "provider": "mock_hotel"})

    def confirm(self, item, payment_auth):
        time.sleep(0.05)
        confirmed_id = f"CONF-HOT-{item.item_id}"
        return ProviderResponse(success=True, confirmed_id=confirmed_id, raw={"booking_reference": "BOOK-" + item.item_id})

    def cancel_hold(self, hold_id):
        time.sleep(0.02)
        return True


class MockCabProvider:
    def reserve(self, item):
        time.sleep(0.02)
        hold_id = f"hold-cab-{item.item_id}"
        return ProviderResponse(success=True, hold_id=hold_id, raw={"price": item.price, "provider": "mock_cab"})

    def confirm(self, item, payment_auth):
        time.sleep(0.02)
        confirmed_id = f"CONF-CAB-{item.item_id}"
        return ProviderResponse(success=True, confirmed_id=confirmed_id, raw={"ride_id": "RIDE-" + item.item_id})

    def cancel_hold(self, hold_id):
        return True