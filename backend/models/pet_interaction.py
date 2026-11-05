"""Durable action attempts. Pending/cancelled attempts are not completed facts."""
from sqlalchemy import String, Integer, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from backend.database import Base
from backend.models.pet import UTC_TIME, TABLE_OPTIONS, new_id
from datetime import datetime

PET_INTERACTION_TABLE_NAMES=frozenset({'pet_interaction'})
class PetInteraction(Base):
    __tablename__='pet_interaction'
    __table_args__=(UniqueConstraint('pet_id','request_key',name='uq_pet_interaction_request'),TABLE_OPTIONS)
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=new_id)
    pet_id:Mapped[str]=mapped_column(ForeignKey('pet_profile.id',ondelete='RESTRICT'),nullable=False)
    request_key:Mapped[str]=mapped_column(String(96),nullable=False)
    kind:Mapped[str]=mapped_column(String(32),nullable=False)
    state:Mapped[str]=mapped_column(String(24),nullable=False,default='pending')
    config_id:Mapped[str]=mapped_column(ForeignKey('pet_config_version.id',ondelete='RESTRICT'),nullable=False)
    pet_data_version:Mapped[int]=mapped_column(Integer,nullable=False)
    started_at:Mapped[datetime]=mapped_column(UTC_TIME,nullable=False)
    expires_at:Mapped[datetime]=mapped_column(UTC_TIME,nullable=False)
    payload:Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)
    result:Mapped[dict|None]=mapped_column(JSON,nullable=True)
    event_id:Mapped[str|None]=mapped_column(ForeignKey('pet_fact_event.id',ondelete='RESTRICT'))
