"""Durable, scoped pet administration; independent of general operation-log rights."""
from sqlalchemy import ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from backend.database import Base
from backend.models.pet import UTC_TIME, TABLE_OPTIONS, new_id, utcnow

PET_ADMIN_TABLE_NAMES=frozenset({'pet_admin_operation','pet_admin_audit'})

class PetAdminOperation(Base):
    __tablename__='pet_admin_operation'
    __table_args__=(Index('ix_pet_admin_operation_actor','admin_id','recorded_at'),TABLE_OPTIONS)
    id: Mapped[str]=mapped_column(String(64),primary_key=True)
    admin_id: Mapped[int]=mapped_column(Integer,nullable=False)
    actor_role: Mapped[str]=mapped_column(String(20),nullable=False)
    token_version: Mapped[int]=mapped_column(Integer,nullable=False)
    action: Mapped[str]=mapped_column(String(48),nullable=False)
    domain: Mapped[str]=mapped_column(String(24),nullable=False)
    target: Mapped[str]=mapped_column(String(128),nullable=False)
    reason: Mapped[str]=mapped_column(Text,nullable=False)
    request_digest: Mapped[str]=mapped_column(String(64),nullable=False)
    payload: Mapped[dict]=mapped_column(JSON,nullable=False)
    state: Mapped[str]=mapped_column(String(24),default='prepared',nullable=False)
    stop_reason: Mapped[str|None]=mapped_column(String(64))
    result: Mapped[dict|None]=mapped_column(JSON,nullable=True)
    recorded_at: Mapped[datetime]=mapped_column(UTC_TIME,default=utcnow,nullable=False)
    finished_at: Mapped[datetime|None]=mapped_column(UTC_TIME)

class PetAdminAudit(Base):
    __tablename__='pet_admin_audit'
    __table_args__=(Index('ix_pet_audit_scope','domain','recorded_at'),TABLE_OPTIONS)
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=new_id)
    operation_id: Mapped[str]=mapped_column(ForeignKey('pet_admin_operation.id',ondelete='RESTRICT'),nullable=False)
    admin_id: Mapped[int]=mapped_column(Integer,nullable=False)
    actor_role: Mapped[str]=mapped_column(String(20),nullable=False)
    action: Mapped[str]=mapped_column(String(48),nullable=False)
    domain: Mapped[str]=mapped_column(String(24),nullable=False)
    target: Mapped[str]=mapped_column(String(128),nullable=False)
    reason: Mapped[str]=mapped_column(Text,nullable=False)
    result: Mapped[dict]=mapped_column(JSON,nullable=False)
    recorded_at: Mapped[datetime]=mapped_column(UTC_TIME,default=utcnow,nullable=False)
