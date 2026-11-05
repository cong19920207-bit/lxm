"""Durable health of the actual pet scheduler producers, not inferred from empty queues."""
from sqlalchemy import String,JSON
from sqlalchemy.orm import Mapped,mapped_column
from datetime import datetime
from backend.database import Base
from backend.models.pet import UTC_TIME,TABLE_OPTIONS
class PetJobHealth(Base):
 __tablename__='pet_job_health'
 __table_args__=(TABLE_OPTIONS,)
 producer:Mapped[str]=mapped_column(String(64),primary_key=True)
 last_run_at:Mapped[datetime]=mapped_column(UTC_TIME,nullable=False)
 last_success_at:Mapped[datetime|None]=mapped_column(UTC_TIME)
 last_error_at:Mapped[datetime|None]=mapped_column(UTC_TIME)
 last_error:Mapped[str|None]=mapped_column(String(96))
 summary:Mapped[dict]=mapped_column(JSON,default=dict,nullable=False)
