"""H5 analytics. All stored times are naive UTC, all day keys are Beijing dates."""
from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, DateTime, Index, JSON, String
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


TIME = DateTime().with_variant(DATETIME(fsp=6), "mysql")
SNAPSHOT = JSON(none_as_null=True)


class VisitorActivation(Base):
    __tablename__ = "h5_visitor_activation"
    __table_args__ = (CheckConstraint("id = 1", name="ck_h5_visitor_activation_one"),)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    enabled_at: Mapped[datetime] = mapped_column(TIME)


class VisitorDay(Base):
    __tablename__ = "h5_visitor_day"
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    visitors: Mapped[int] = mapped_column(BigInteger, server_default="0")
    visits: Mapped[int] = mapped_column(BigInteger, server_default="0")
    opens: Mapped[int] = mapped_column(BigInteger, server_default="0")
    unidentified_opens: Mapped[int] = mapped_column(BigInteger, server_default="0")


class VisitorDevice(Base):
    __tablename__ = "h5_visitor_device"
    __table_args__ = (Index("ix_h5_device_recent", "last_at", "visitor_id"),)
    visitor_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    first_at: Mapped[datetime] = mapped_column(TIME)
    last_at: Mapped[datetime] = mapped_column(TIME)
    last_event_id: Mapped[str] = mapped_column(String(36))
    identity: Mapped[str] = mapped_column(String(32))
    network: Mapped[dict | None] = mapped_column(SNAPSHOT)
    profile: Mapped[dict | None] = mapped_column(SNAPSHOT)
    profile_at: Mapped[datetime | None] = mapped_column(TIME)
    visits: Mapped[int] = mapped_column(BigInteger, server_default="0")
    opens: Mapped[int] = mapped_column(BigInteger, server_default="0")


class VisitorVisit(Base):
    __tablename__ = "h5_visitor_visit"
    __table_args__ = (Index("ix_h5_visit_day_device", "day", "visitor_id", "started_at"),
                      Index("ix_h5_visit_expiry", "last_activity"),)
    # The first foreground event owns the visit id and its immutable start snapshot.
    visit_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    day: Mapped[date] = mapped_column(Date)
    visitor_id: Mapped[str] = mapped_column(String(36))
    started_at: Mapped[datetime] = mapped_column(TIME)
    last_activity: Mapped[datetime] = mapped_column(TIME)
    opens: Mapped[int] = mapped_column(BigInteger, server_default="0")


class VisitorEvent(Base):
    __tablename__ = "h5_visitor_event"
    __table_args__ = (Index("ix_h5_event_device_day", "visitor_id", "day", "occurred_at"),
                      Index("ix_h5_event_visit", "visit_id", "occurred_at"),
                      Index("ix_h5_event_expiry", "occurred_at"),)
    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    visitor_id: Mapped[str | None] = mapped_column(String(36))
    visit_id: Mapped[str | None] = mapped_column(String(36))
    day: Mapped[date] = mapped_column(Date)
    kind: Mapped[str] = mapped_column(String(16))
    entry: Mapped[str] = mapped_column(String(32))
    occurred_at: Mapped[datetime] = mapped_column(TIME)
    received_at: Mapped[datetime] = mapped_column(TIME)
    identity: Mapped[str] = mapped_column(String(32))
    identity_source: Mapped[str] = mapped_column(String(16))
    network: Mapped[dict | None] = mapped_column(SNAPSHOT)
    delayed: Mapped[bool] = mapped_column(Boolean, server_default="0")


VISITOR_TABLE_NAMES = {model.__tablename__ for model in (
    VisitorActivation, VisitorDay, VisitorDevice, VisitorVisit, VisitorEvent,
)}
