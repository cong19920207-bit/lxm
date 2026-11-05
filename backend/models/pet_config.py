"""Pet configuration revisions, immutable publications and trusted resource registry."""
from datetime import datetime
from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from backend.database import Base
from backend.models.pet import TABLE_OPTIONS,UTC_TIME,utcnow,new_id

PET_CONFIG_TABLE_NAMES=frozenset({'pet_config_head','pet_config_version','pet_config_draft_revision','pet_resource'})

class PetConfigHead(Base):
    __tablename__='pet_config_head';__table_args__=TABLE_OPTIONS
    domain:Mapped[str]=mapped_column(String(24),primary_key=True)
    active_version:Mapped[int]=mapped_column(BigInteger,default=0,nullable=False)
    draft_revision:Mapped[int]=mapped_column(BigInteger,default=0,nullable=False)
    draft_base_version:Mapped[int]=mapped_column(BigInteger,default=0,nullable=False)
    draft:Mapped[dict|None]=mapped_column(JSON,nullable=True)
    validated_digest:Mapped[str|None]=mapped_column(String(64))
    validated_revision:Mapped[int|None]=mapped_column(BigInteger)
    validation_error:Mapped[str|None]=mapped_column(String(512))
    updated_by:Mapped[int|None]=mapped_column(Integer)
    updated_at:Mapped[datetime]=mapped_column(UTC_TIME,default=utcnow,nullable=False)

class PetConfigDraftRevision(Base):
    __tablename__='pet_config_draft_revision'
    __table_args__=(UniqueConstraint('domain','revision',name='uq_pet_config_draft_revision'),TABLE_OPTIONS)
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=new_id)
    domain:Mapped[str]=mapped_column(String(24),nullable=False,index=True)
    revision:Mapped[int]=mapped_column(BigInteger,nullable=False)
    base_version:Mapped[int]=mapped_column(BigInteger,nullable=False)
    content:Mapped[dict]=mapped_column(JSON,nullable=False)
    content_digest:Mapped[str]=mapped_column(String(64),nullable=False)
    source:Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)
    saved_by:Mapped[int|None]=mapped_column(Integer)
    saved_at:Mapped[datetime]=mapped_column(UTC_TIME,default=utcnow,nullable=False)
    deleted_by:Mapped[int|None]=mapped_column(Integer)
    deleted_at:Mapped[datetime|None]=mapped_column(UTC_TIME)

class PetConfigVersion(Base):
    __tablename__='pet_config_version'
    __table_args__=(UniqueConstraint('domain','version',name='uq_pet_config_version'),TABLE_OPTIONS)
    id:Mapped[str]=mapped_column(String(36),primary_key=True,default=new_id)
    domain:Mapped[str]=mapped_column(String(24),nullable=False)
    version:Mapped[int]=mapped_column(BigInteger,nullable=False)
    content:Mapped[dict]=mapped_column(JSON,nullable=False)
    content_digest:Mapped[str]=mapped_column(String(64),nullable=False)
    diff:Mapped[dict]=mapped_column(JSON,nullable=False)
    effective_at:Mapped[datetime]=mapped_column(UTC_TIME,nullable=False)
    action:Mapped[str]=mapped_column(String(24),nullable=False)
    operation_id:Mapped[str]=mapped_column(ForeignKey('pet_admin_operation.id',ondelete='RESTRICT'),unique=True,nullable=False)
    snapshot_id:Mapped[str]=mapped_column(ForeignKey('pet_rule_snapshot.id',ondelete='RESTRICT'),nullable=False)
    growth_snapshot_id:Mapped[str|None]=mapped_column(ForeignKey('pet_rule_snapshot.id',ondelete='RESTRICT'))
    state_snapshot_id:Mapped[str|None]=mapped_column(ForeignKey('pet_rule_snapshot.id',ondelete='RESTRICT'))
    recorded_at:Mapped[datetime]=mapped_column(UTC_TIME,default=utcnow,nullable=False)

class PetResource(Base):
    """Only server-side asset registration may set availability/capabilities."""
    __tablename__='pet_resource';__table_args__=TABLE_OPTIONS
    id:Mapped[str]=mapped_column(String(128),primary_key=True)
    version:Mapped[str]=mapped_column(String(64),nullable=False)
    uri:Mapped[str]=mapped_column(String(512),nullable=False)
    identity_key:Mapped[str]=mapped_column(String(64),nullable=False)
    stages:Mapped[list]=mapped_column(JSON,nullable=False)
    actions:Mapped[list]=mapped_column(JSON,nullable=False)
    available:Mapped[bool]=mapped_column(Boolean,default=True,nullable=False)
    sha256:Mapped[str|None]=mapped_column(String(64))
    capabilities:Mapped[dict]=mapped_column(JSON,nullable=False,default=dict)
