"""First receipt and event-time visit attribution share one database transaction."""
from datetime import datetime, timedelta, timezone
import hmac

import jwt
from sqlalchemy import select

from backend.config import get_jwt_secret
from backend.models.visitor import VisitorActivation, VisitorDay, VisitorDevice, VisitorEvent, VisitorVisit

BEIJING = timezone(timedelta(hours=8))
OPEN_WINDOW = timedelta(hours=24)
LIVE_WINDOW = timedelta(minutes=1)
IDLE = timedelta(minutes=30)
DEVICE_TTL = timedelta(days=90)


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def beijing_day(at):
    return at.replace(tzinfo=timezone.utc).astimezone(BEIJING).date()


def _witness_key():
    return hmac.digest(get_jwt_secret().encode(), b"lxm/h5/open-witness/v1", "sha256")


def _binding(body):
    return {"event": str(body.event_id), "visitor": str(body.visitor_id or ""),
            "at": body.occurred_at.isoformat(), "entry": body.entry}


def issue_witness(body, identity, now):
    if abs(now - body.occurred_at) > LIVE_WINDOW:
        return None
    return jwt.encode({**_binding(body), "identity": identity, "issued": now.isoformat()},
                      _witness_key(), algorithm="HS256")


def original_identity(body, current_identity, delayed):
    if body.witness:
        try:
            claims = jwt.decode(body.witness, _witness_key(), algorithms=["HS256"])
            if all(claims.get(k) == v for k, v in _binding(body).items()):
                return claims["identity"], "open_witness"
        except jwt.PyJWTError:
            pass
    return ("unknown", "missing") if delayed else (current_identity, "request")


def lock_activation(db):
    # Ingestion and retention acquire the same first lock. No network I/O is done
    # while held. Readers use consistent snapshots without taking this write lock.
    return db.execute(select(VisitorActivation).where(VisitorActivation.id == 1).with_for_update()).scalar_one()


def _place(db, event, current, visits):
    if event.kind != "identity":
        if current is None or (event.kind in ("open", "return") and
                               event.occurred_at - current.last_activity >= IDLE):
            current = visits.get(event.event_id)
            if current is None:
                current = VisitorVisit(visit_id=event.event_id, visitor_id=event.visitor_id,
                                       day=event.day, started_at=event.occurred_at)
                db.add(current)
            current.opens = 0
        current.last_activity = event.occurred_at
        if event.kind == "open":
            current.opens += 1
    event.visit_id = current.visit_id if current else None
    return current


def _attribution(db, event):
    scope = (VisitorVisit.day == event.day, VisitorVisit.visitor_id == event.visitor_id)
    previous = db.scalar(select(VisitorVisit).where(*scope).order_by(VisitorVisit.started_at.desc()).limit(1))
    later = db.scalar(select(VisitorEvent.event_id).where(
        VisitorEvent.visitor_id == event.visitor_id, VisitorEvent.day == event.day,
        VisitorEvent.event_id != event.event_id, VisitorEvent.occurred_at >= event.occurred_at).limit(1))
    if later is None:
        current = _place(db, event, previous, {})
        return int(current is not previous), int(previous is None and current is not None)
    # A late open may bridge two previously separate visits. Rebuild only this
    # device's Beijing day, retaining unaffected visit ids and immutable snapshots.
    old = {v.visit_id: v for v in db.scalars(select(VisitorVisit).where(*scope))}
    events = db.scalars(select(VisitorEvent).where(VisitorEvent.day == event.day,
                        VisitorEvent.visitor_id == event.visitor_id).order_by(
                            VisitorEvent.occurred_at, VisitorEvent.kind == "identity", VisitorEvent.event_id))
    current, used = None, set()
    for row in events:
        current = _place(db, row, current, old)
        if current:
            used.add(current.visit_id)
    for key in old.keys() - used:
        db.delete(old[key])
    return len(used) - len(old), int(bool(used)) - int(bool(old))


def _device_snapshot(db, event, profile):
    device = db.get(VisitorDevice, event.visitor_id)
    if device and event.occurred_at - device.last_at >= DEVICE_TTL:
        db.delete(device)
        db.flush()
        device = None
    if device is None:
        if event.kind == "identity":
            return None
        latest = db.scalar(select(VisitorEvent).where(VisitorEvent.visitor_id == event.visitor_id,
                           VisitorEvent.occurred_at >= event.occurred_at).order_by(
                               VisitorEvent.occurred_at.desc(), (VisitorEvent.kind == "identity").desc(),
                               VisitorEvent.event_id.desc()).limit(1))
        device = VisitorDevice(visitor_id=event.visitor_id, first_at=event.occurred_at, last_at=latest.occurred_at,
                               last_event_id=latest.event_id, identity=latest.identity, network=latest.network, visits=0, opens=0)
        db.add(device)
    if event.kind != "identity":
        device.first_at = min(device.first_at, event.occurred_at)
    newer = event.occurred_at > device.last_at
    if event.occurred_at == device.last_at and event.event_id != device.last_event_id:
        previous = db.get(VisitorEvent, device.last_event_id)
        newer = previous is None or (event.kind == "identity", event.event_id) > (previous.kind == "identity", previous.event_id)
    if newer:
        device.last_at, device.last_event_id = event.occurred_at, event.event_id
        device.identity, device.network = event.identity, event.network
    if profile is not None and (device.profile_at is None or event.occurred_at >= device.profile_at):
        device.profile, device.profile_at = profile.model_dump(exclude_none=True), event.occurred_at
    return device


def record(db, body, current_identity, network, now):
    activation = lock_activation(db)
    key, at = str(body.event_id), body.occurred_at
    if db.get(VisitorEvent, key) is not None:
        return
    age = now - at
    if at < activation.enabled_at or age > (OPEN_WINDOW if body.kind == "open" else LIVE_WINDOW):
        return
    if age < -LIVE_WINDOW or (body.visitor_id is None and body.kind != "open"):
        return
    delayed = body.kind == "open" and (body.replay or age > LIVE_WINDOW)
    identity, evidence = (original_identity(body, current_identity, delayed) if body.kind == "open"
                          else (current_identity, "request"))
    event = VisitorEvent(event_id=key, visitor_id=str(body.visitor_id) if body.visitor_id else None,
                         day=beijing_day(at), kind=body.kind, entry=body.entry, occurred_at=at,
                         received_at=now, identity=identity, identity_source=evidence, network=network,
                         delayed=delayed)
    db.add(event)
    db.flush()
    device = _device_snapshot(db, event, body.profile) if event.visitor_id else None
    new_visits, new_visitors = _attribution(db, event) if event.visitor_id else (0, 0)
    opens = int(event.kind == "open")
    if device:
        device.visits += new_visits
        device.opens += opens
    if new_visits or new_visitors or opens:
        daily = db.get(VisitorDay, event.day)
        if daily is None:
            daily = VisitorDay(day=event.day, visitors=0, visits=0, opens=0, unidentified_opens=0)
            db.add(daily)
        daily.visitors += new_visitors
        daily.visits += new_visits
        daily.opens += opens
        daily.unidentified_opens += int(event.visitor_id is None and opens)
    db.flush()
