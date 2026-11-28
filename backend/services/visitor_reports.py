"""Read-side retention applies at query time, independently of scheduled deletion."""
from calendar import monthrange
from datetime import date, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import delete, func, select, update

from backend.models.visitor import VisitorActivation, VisitorDay, VisitorDevice, VisitorEvent, VisitorVisit
from backend.services.visitor_events import beijing_day, DEVICE_TTL, lock_activation

DETAIL_TTL = timedelta(days=30)


def year_shift(day, years):
    year = day.year + years
    return date(year, day.month, min(day.day, monthrange(year, day.month)[1]))


def aggregate_floor(today):
    candidate = year_shift(today, -1) + timedelta(days=1)
    if year_shift(candidate, 1) <= today:  # Feb 28 following a leap year
        candidate += timedelta(days=1)
    return candidate


def clean(db, now):
    lock_activation(db)
    cutoff = now - DETAIL_TTL
    db.execute(delete(VisitorEvent).where(VisitorEvent.occurred_at <= cutoff))
    db.execute(delete(VisitorVisit).where(VisitorVisit.started_at <= cutoff))
    db.execute(update(VisitorDevice).where(VisitorDevice.last_at <= cutoff,
               VisitorDevice.network.is_not(None)).values(network=None))
    db.execute(delete(VisitorDevice).where(VisitorDevice.last_at <= now - DEVICE_TTL))
    db.execute(delete(VisitorDay).where(VisitorDay.day < aggregate_floor(beijing_day(now))))


def iso(at):
    return at.replace(tzinfo=timezone.utc).isoformat() if at is not None else None


def period(db, requested, now):
    today = beijing_day(now)
    first = max(beijing_day(db.get(VisitorActivation, 1).enabled_at), aggregate_floor(today))
    day = requested or today
    if not first <= day <= today:
        raise HTTPException(400, "日期超出可查范围")
    return day, first, today


def serialize_event(event):
    return {"id": event.event_id, "event_id": event.event_id, "visit_id": event.visit_id, "visitor_id": event.visitor_id,
            "kind": event.kind, "entry": event.entry, "occurred_at": iso(event.occurred_at),
            "received_at": iso(event.received_at), "identity": event.identity,
            "network": event.network, "delayed": event.delayed}


def daily_summary(db, requested, now):
    day, first, today = period(db, requested, now)
    daily = db.get(VisitorDay, day)
    counts = {key: getattr(daily, key) if daily else 0 for key in ("visitors", "visits", "opens", "unidentified_opens")}
    return {"day": day, "first_day": first, "today": today, **counts}


def report(db, requested, now, direction, page, size):
    summary = daily_summary(db, requested, now)
    day = summary["day"]
    cutoff = now - DETAIL_TTL
    # Group retained events, including visits consisting of a foreground return.
    # The first event owns the visit id. Its start time expires independently of later opens.
    scope = (VisitorEvent.day == day, VisitorEvent.occurred_at > cutoff,
             VisitorEvent.visitor_id.is_not(None), VisitorEvent.visit_id.is_not(None))
    from sqlalchemy import case
    started = case((VisitorEvent.event_id == VisitorEvent.visit_id, VisitorEvent.occurred_at))
    grouped = select(VisitorEvent.visitor_id.label("visitor_id"),
                     func.count(func.distinct(VisitorEvent.visit_id)).label("visits"),
                     func.sum(case((VisitorEvent.kind == "open", 1), else_=0)).label("opens"),
                     func.min(started).label("first_at"), func.max(started).label("last_at")).where(
                         *scope).group_by(VisitorEvent.visitor_id).subquery()
    total = db.scalar(select(func.count()).select_from(grouped))
    order = grouped.c.visits.desc() if direction == "desc" else grouped.c.visits.asc()
    query = (select(grouped, VisitorDevice)
             .outerjoin(VisitorDevice, (VisitorDevice.visitor_id == grouped.c.visitor_id) &
                        (VisitorDevice.last_at > now - DEVICE_TTL))
             .order_by(order, grouped.c.visitor_id).offset((page - 1) * size).limit(size))
    rows = []
    for row in db.execute(query):
        rows.append({"id": row.visitor_id, "visitor_id": row.visitor_id, "visits": row.visits,
                     "opens": int(row.opens), "first_at": iso(row.first_at), "last_at": iso(row.last_at),
                     "device": device_row(row.VisitorDevice, now) if row.VisitorDevice else None})
    state = "empty" if not (summary["opens"] or summary["visits"]) else "available"
    if state == "available" and day <= beijing_day(cutoff):
        retained = db.scalar(select(VisitorEvent.event_id).where(VisitorEvent.day == day,
                             VisitorEvent.occurred_at > cutoff).limit(1))
        if retained is None:
            state = "expired"
    return {**summary, "state": state, "list": rows,
            "total": total, "page": page, "page_size": size}


def visit_details(db, day, visitor_id, now):
    period(db, day, now)
    events = db.scalars(select(VisitorEvent).where(VisitorEvent.day == day,
                       VisitorEvent.visitor_id == visitor_id, VisitorEvent.visit_id.is_not(None),
                       VisitorEvent.occurred_at > now - DETAIL_TTL).order_by(
                           VisitorEvent.occurred_at, VisitorEvent.kind == "identity", VisitorEvent.event_id))
    visits = {}
    for event in events:
        visit = visits.setdefault(event.visit_id, {"visit_id": event.visit_id, "start": None, "opens": [], "changes": []})
        if event.event_id == event.visit_id:
            visit["start"] = serialize_event(event)
        if event.kind == "open":
            visit["opens"].append(serialize_event(event))
        elif event.kind == "identity":
            visit["changes"].append(serialize_event(event))
    return {"visitor_id": visitor_id, "day": day, "visits": list(visits.values())}


def device_row(device, now):
    return {"id": device.visitor_id, "visitor_id": device.visitor_id, "first_at": iso(device.first_at), "last_at": iso(device.last_at),
            "identity": device.identity, "network": device.network if device.last_at > now - DETAIL_TTL else None,
            "profile": device.profile or {}, "visits": device.visits, "opens": device.opens}


def devices(db, now, page, size):
    live = VisitorDevice.last_at > now - DEVICE_TTL
    total = db.scalar(select(func.count()).select_from(VisitorDevice).where(live))
    rows = db.scalars(select(VisitorDevice).where(live).order_by(VisitorDevice.last_at.desc(),
                      VisitorDevice.visitor_id).offset((page-1)*size).limit(size))
    return {"page": page, "page_size": size, "total": total, "list": [device_row(row, now) for row in rows]}


def device_details(db, visitor_id, now, page, size):
    device = db.get(VisitorDevice, visitor_id)
    if device is None or device.last_at <= now - DEVICE_TTL:
        raise HTTPException(404, "设备记录不存在或已过期")
    scope = (VisitorEvent.visitor_id == visitor_id, VisitorEvent.occurred_at >= device.first_at,
             VisitorEvent.occurred_at > now - DETAIL_TTL)
    opens = select(VisitorEvent).where(*scope, VisitorEvent.kind == "open")
    total = db.scalar(select(func.count()).select_from(opens.subquery()))
    order = (VisitorEvent.occurred_at.desc(), VisitorEvent.event_id.desc())
    rows = db.scalars(opens.order_by(*order).offset((page-1)*size).limit(size))
    changes = db.scalars(select(VisitorEvent).where(*scope, VisitorEvent.kind == "identity").order_by(
        VisitorEvent.occurred_at, VisitorEvent.event_id))
    return {**device_row(device, now), "list": [serialize_event(r) for r in rows],
            "changes": [serialize_event(r) for r in changes], "total": total, "page": page, "page_size": size}
