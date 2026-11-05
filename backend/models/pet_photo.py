"""Photo bytes live in OSS; these rows own object references and cleanup responsibility."""
from datetime import datetime
from sqlalchemy import String,Integer,JSON,ForeignKey,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from backend.database import Base
from backend.models.pet import UTC_TIME,TABLE_OPTIONS,utcnow

class PetPhotoAsset(Base):
    __tablename__='pet_photo_asset';__table_args__=(UniqueConstraint('object_key',name='uq_pet_photo_object'),TABLE_OPTIONS)
    id:Mapped[str]=mapped_column(String(36),primary_key=True)
    pet_id:Mapped[str]=mapped_column(ForeignKey('pet_profile.id',ondelete='RESTRICT'),nullable=False)
    bucket:Mapped[str]=mapped_column(String(128),nullable=False)
    namespace:Mapped[str]=mapped_column(String(40),nullable=False)
    object_key:Mapped[str]=mapped_column(String(512),nullable=False)
    sha256:Mapped[str]=mapped_column(String(64),nullable=False)
    mime_type:Mapped[str]=mapped_column(String(32),nullable=False)
    size_bytes:Mapped[int]=mapped_column(Integer,nullable=False)
    width:Mapped[int]=mapped_column(Integer,nullable=False)
    height:Mapped[int]=mapped_column(Integer,nullable=False)
    state:Mapped[str]=mapped_column(String(24),nullable=False,default='uploading')
    generation:Mapped[int]=mapped_column(Integer,nullable=False,default=1)
    expires_at:Mapped[datetime]=mapped_column(UTC_TIME,nullable=False)
    lease_until:Mapped[datetime]=mapped_column(UTC_TIME,nullable=False)
    upload_finished_at:Mapped[datetime|None]=mapped_column(UTC_TIME)
    created_at:Mapped[datetime]=mapped_column(UTC_TIME,default=utcnow,nullable=False)
    archived_at:Mapped[datetime|None]=mapped_column(UTC_TIME)

class PetPhotoDeleteJob(Base):
    # Deliberately has no pet_id or FK: account purge must retain this outbox.
    __tablename__='pet_photo_delete_job';__table_args__=TABLE_OPTIONS
    id:Mapped[str]=mapped_column(String(36),primary_key=True)
    bucket:Mapped[str]=mapped_column(String(128),nullable=False)
    namespace:Mapped[str]=mapped_column(String(40),nullable=False)
    object_key:Mapped[str]=mapped_column(String(512),nullable=False)
    state:Mapped[str]=mapped_column(String(24),default='pending',nullable=False)
    reason:Mapped[str]=mapped_column(String(48),nullable=False)
    attempts:Mapped[int]=mapped_column(Integer,default=0,nullable=False)
    generation:Mapped[int]=mapped_column(Integer,default=1,nullable=False)
    next_check_at:Mapped[datetime]=mapped_column(UTC_TIME,default=utcnow,nullable=False)
    confirmed_at:Mapped[datetime|None]=mapped_column(UTC_TIME)
