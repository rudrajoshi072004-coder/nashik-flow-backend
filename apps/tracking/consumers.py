from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth.models import AnonymousUser
from asgiref.sync import sync_to_async

from apps.tracking.services import update_driver_location
from apps.bookings.models import Booking
from apps.drivers.models import DriverProfile
from apps.trip_events.services import record_trip_event, broadcast_event


class RealtimeConsumer(AsyncJsonWebsocketConsumer):
    async def _get_or_create_driver_profile(self):
        return await sync_to_async(DriverProfile.objects.get_or_create)(user=self.user)

    async def connect(self):
        user = self.scope.get("user")
        if not user or isinstance(user, AnonymousUser) or not getattr(user, "is_authenticated", False):
            await self.close(code=4001)
            return

        self.user = user
        self.joined_booking_groups = set()
        self.driver_group_name: str | None = None
        self.admin_city_group_name: str | None = None
        await self.accept()
        await self.channel_layer.group_add(f"user_{self.user.id}", self.channel_name)

        profile = await sync_to_async(
            lambda: DriverProfile.objects.filter(user=self.user, is_deleted=False).first()
        )()
        if profile is None and self.user.role in {"driver", "fleet_driver"}:
            profile, _ = await self._get_or_create_driver_profile()
        if profile is not None:
            self.driver_group_name = f"driver_{profile.id}"
            await self.channel_layer.group_add(self.driver_group_name, self.channel_name)
        if self.user.role in {"super_admin", "city_manager", "support_agent", "finance_admin"}:
            self.admin_city_group_name = f"admin_city_{self.user.city.lower()}"
            await self.channel_layer.group_add(self.admin_city_group_name, self.channel_name)

        await self.send_json({"event": "connected", "payload": {"user_id": str(self.user.id), "role": self.user.role}})

    async def disconnect(self, close_code):
        if hasattr(self, "user") and getattr(self.user, "is_authenticated", False):
            await self.channel_layer.group_discard(f"user_{self.user.id}", self.channel_name)
            if getattr(self, "driver_group_name", None):
                await self.channel_layer.group_discard(self.driver_group_name, self.channel_name)
            if getattr(self, "admin_city_group_name", None):
                await self.channel_layer.group_discard(self.admin_city_group_name, self.channel_name)
            for group in self.joined_booking_groups:
                await self.channel_layer.group_discard(group, self.channel_name)

    async def receive_json(self, content, **kwargs):
        event = content.get("event")
        payload = content.get("payload", {})

        if event == "subscribe_booking":
            booking_id = payload.get("booking_id")
            if booking_id:
                group = f"booking_{booking_id}"
                await self.channel_layer.group_add(group, self.channel_name)
                self.joined_booking_groups.add(group)
                await self.send_json({"event": "subscribed", "payload": {"booking_id": booking_id}})
            return

        if event == "ping":
            await self.send_json({"event": "pong", "payload": {}})
            return

        if event == "driver_offer_ack":
            booking_id = payload.get("booking_id")
            profile = await sync_to_async(
                lambda: DriverProfile.objects.filter(user=self.user, is_deleted=False).first()
            )()
            if booking_id and profile:
                from apps.dispatch.offer_delivery import record_driver_ack

                await sync_to_async(record_driver_ack)(str(booking_id), str(profile.id))
            return

        if event == "driver_location_update":
            profile = await sync_to_async(
                lambda: DriverProfile.objects.filter(user=self.user, is_deleted=False).first()
            )()
            if not profile:
                await self.send_json({"event": "driver_location_ack", "payload": {"ok": False}})
                return
            await sync_to_async(update_driver_location)(
                driver_profile=profile,
                lat=float(payload["lat"]),
                lng=float(payload["lng"]),
                heading=float(payload.get("heading", 0)),
                speed_kmph=float(payload.get("speed_kmph", 0)),
                accuracy_m=float(payload.get("accuracy_m", 0)),
                booking_id=payload.get("booking_id"),
            )
            await self.send_json({"event": "driver_location_ack", "payload": {"ok": True}})
            return

        if event == "booking_status_update":
            booking_id = payload.get("booking_id")
            new_state = payload.get("state")
            if booking_id and new_state:
                await sync_to_async(self._update_booking_status)(booking_id, new_state, payload)
            return

    def _update_booking_status(self, booking_id: str, new_state: str, payload: dict):
        booking = Booking.objects.filter(id=booking_id).first()
        if not booking:
            return
        old_state = booking.state
        booking.state = new_state
        booking.save(update_fields=["state", "updated_at"])
        record_trip_event(
            booking=booking,
            actor_user=self.user,
            actor_driver=getattr(self.user, "driver_profile", None),
            event_type=self._state_to_event_name(new_state),
            from_state=old_state,
            to_state=new_state,
            payload=payload,
        )
        event_payload = {"booking_id": str(booking.id), "state": new_state, "previous_state": old_state}
        broadcast_event(f"booking_{booking.id}", "booking_status_update", event_payload)
        broadcast_event(f"user_{booking.customer_id}", "booking_status_update", event_payload)
        if booking.driver_id:
            broadcast_event(f"driver_{booking.driver_id}", "booking_status_update", event_payload)

    def _state_to_event_name(self, state: str) -> str:
        mapper = {
            Booking.BookingState.DRIVER_ARRIVED: "driver_arrived",
            Booking.BookingState.TRIP_STARTED: "trip_started",
            Booking.BookingState.COMPLETED: "trip_completed",
            Booking.BookingState.CANCELLED_BY_CUSTOMER: "booking_cancelled",
            Booking.BookingState.CANCELLED_BY_DRIVER: "booking_cancelled",
            Booking.BookingState.CANCELLED_BY_ADMIN: "booking_cancelled",
        }
        return mapper.get(state, "booking_status_update")

    async def realtime_event(self, event):
        await self.send_json({"event": event["event_name"], "payload": event["payload"]})
