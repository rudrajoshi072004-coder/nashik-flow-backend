from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import TripEvent


def record_trip_event(
    *,
    booking,
    event_type: str,
    actor_user=None,
    actor_driver=None,
    from_state: str = "",
    to_state: str = "",
    payload: dict | None = None,
) -> TripEvent:
    payload = payload or {}
    current_seq = (
        TripEvent.objects.filter(booking=booking).order_by("-sequence").values_list("sequence", flat=True).first() or 0
    )
    return TripEvent.objects.create(
        booking=booking,
        actor_user=actor_user,
        actor_driver=actor_driver,
        event_type=event_type,
        from_state=from_state,
        to_state=to_state,
        payload=payload,
        sequence=current_seq + 1,
    )


def broadcast_event(group: str, event_name: str, payload: dict):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        group,
        {
            "type": "realtime.event",
            "event_name": event_name,
            "payload": payload,
        },
    )
