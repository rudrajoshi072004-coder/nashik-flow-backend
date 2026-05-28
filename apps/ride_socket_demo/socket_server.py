"""
Socket.IO demo server (parity with legacy Node apps/ride-backend/server.js).

Note: Uses in-memory state; multiple Gunicorn workers do not share memory or sockets.
For reliable local/UI testing prefer `runserver` or a single ASGI worker.
"""

from __future__ import annotations

import socketio

from apps.ride_socket_demo import state

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")


@sio.event
async def connect(_sid, _environ):
    return True


@sio.event
async def disconnect(sid):
    await state.unregister_socket(sid)


@sio.on("registerDriver")
async def register_driver(sid, driver_id):
    d = await state.set_driver_socket(str(driver_id), sid, "available")
    if not d:
        return {"ok": False, "message": "Driver not found"}
    await sio.enter_room(sid, f"driver:{d['id']}")
    return {"ok": True, "driverId": d["id"], "name": d["name"]}


@sio.on("bookRide")
async def book_ride(sid, data):
    try:
        ride = await state.create_ride(data or {}, sid)
        pickup = ride["pickup"]
        lng, lat = float(pickup[0]), float(pickup[1])
        nearby = await state.nearby_available_online(lng, lat)

        if not nearby:
            await sio.emit("noDriversAvailable", {"message": "No drivers found nearby."}, room=sid)
            return {"ok": True, "rideId": ride["id"], "notifiedCount": 0}

        ride_payload = {
            "rideId": ride["id"],
            "pickup": ride["pickup"],
            "destination": ride["destination"],
            "pickupAddressText": ride.get("pickupAddressText"),
            "dropAddressText": ride.get("dropAddressText"),
            "fare": ride.get("fare"),
        }
        notified: list[str] = []
        for d in nearby:
            notified.append(d["id"])
            await sio.emit("rideRequest", ride_payload, room=d["socket_id"])

        await state.save_ride_notified(ride["id"], notified)
        return {"ok": True, "rideId": ride["id"], "notifiedCount": len(nearby)}
    except Exception:
        await sio.emit("rideError", {"message": "Failed to request ride."}, room=sid)
        return {"ok": False, "message": "Failed to request ride."}


@sio.on("acceptRide")
async def accept_ride(sid, data):
    payload = data or {}
    ride_id = str(payload.get("rideId", ""))
    driver_id = str(payload.get("driverId", ""))
    ride, _ = await state.try_accept_ride(ride_id, driver_id)
    if not ride:
        await sio.emit(
            "rideUnavailable",
            {"message": "Ride is no longer available."},
            room=sid,
        )
        return {"ok": False, "message": "Ride is no longer available."}

    cust = ride.get("customer_socket_id")
    if cust:
        await sio.emit("rideAccepted", {"driverId": driver_id}, room=cust)

    for nid in state.ride_notified_ids(ride):
        if nid == driver_id:
            continue
        await sio.emit("rideNoLongerAvailable", {"rideId": ride_id}, room=f"driver:{nid}")

    await sio.emit("acceptSuccess", {"rideId": ride_id}, room=sid)
    return {"ok": True, "rideId": ride_id}


@sio.on("rejectRide")
async def reject_ride(_sid, _data):
    return {"ok": True}
