from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.test import TestCase

from apps.bookings.models import Booking
from apps.bookings.services import transition_booking_state
from apps.vehicle_categories.models import VehicleCategory


class BookingStateMachineTestCase(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.customer = user_model.objects.create(phone="+919100000010", role=user_model.Role.CUSTOMER)
        self.driver = user_model.objects.create(phone="+919100000011", role=user_model.Role.DRIVER)
        self.category = VehicleCategory.objects.create(
            name="2-wheeler",
            payload_type="parcel",
            max_weight_kg=20,
            max_volume_m3=1,
            base_fare=40,
            per_km_rate=10,
            waiting_per_min=2,
            minimum_fare=40,
        )
        self.booking = Booking.objects.create(
            customer=self.customer,
            driver=self.driver,
            vehicle_category=self.category,
            pickup_location=Point(73.79, 19.99, srid=4326),
            drop_location=Point(73.75, 20.01, srid=4326),
        )

    def test_valid_transition(self):
        transition_booking_state(booking=self.booking, to_state=Booking.BookingState.PENDING_QUOTE, actor=self.customer)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.state, Booking.BookingState.PENDING_QUOTE)

    def test_invalid_transition_raises(self):
        with self.assertRaises(ValueError):
            transition_booking_state(booking=self.booking, to_state=Booking.BookingState.COMPLETED, actor=self.customer)
