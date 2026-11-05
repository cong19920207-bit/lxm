"""Server-owned participation sessions and stable absence intervals."""
from datetime import datetime
from sqlalchemy import ForeignKey,String,Float,Integer,Boolean,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from backend.database import Base
from backend.models.pet import UTC_TIME,TABLE_OPTIONS,new_id
PET_ACTIVITY_TABLE_NAMES=frozenset({'pet_activity','pet_absence','pet_view_session'})

class PetActivity(Base):
 __tablename__='pet_activity'
 __table_args__=(TABLE_OPTIONS,)
 pet_id:Mapped[str]=mapped_column(ForeignKey('pet_profile.id',ondelete='RESTRICT'),primary_key=True)
 last_active_at:Mapped[datetime]=mapped_column(UTC_TIME,nullable=False)
 session_until:Mapped[datetime]=mapped_column(UTC_TIME,nullable=False)
 previous_absence_id:Mapped[str|None]=mapped_column(String(36))

class PetAbsence(Base):
 __tablename__='pet_absence'
 __table_args__=(UniqueConstraint('pet_id','started_at',name='uq_pet_absence_anchor'),TABLE_OPTIONS)
 id:Mapped[str]=mapped_column(String(36),primary_key=True)
 pet_id:Mapped[str]=mapped_column(ForeignKey('pet_profile.id',ondelete='RESTRICT'),nullable=False)
 started_at:Mapped[datetime]=mapped_column(UTC_TIME,nullable=False)
 ended_at:Mapped[datetime|None]=mapped_column(UTC_TIME)
 last_narrative_at:Mapped[datetime|None]=mapped_column(UTC_TIME)

class PetViewSession(Base):
 __tablename__='pet_view_session'
 __table_args__=(TABLE_OPTIONS,)
 id:Mapped[str]=mapped_column(String(36),primary_key=True,default=new_id)
 pet_id:Mapped[str]=mapped_column(ForeignKey('pet_profile.id',ondelete='RESTRICT'),nullable=False)
 started_at:Mapped[datetime]=mapped_column(UTC_TIME,nullable=False)
 heartbeat_at:Mapped[datetime]=mapped_column(UTC_TIME,nullable=False)
 sequence:Mapped[int]=mapped_column(Integer,default=0,nullable=False)
 seconds:Mapped[float]=mapped_column(Float,default=0,nullable=False)
 foreground:Mapped[bool]=mapped_column(Boolean,default=True,nullable=False)
 qualified_at:Mapped[datetime|None]=mapped_column(UTC_TIME)
 absence_id:Mapped[str|None]=mapped_column(ForeignKey('pet_absence.id',ondelete='RESTRICT'))
