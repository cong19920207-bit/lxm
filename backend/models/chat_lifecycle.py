"""STEP014 SQL authority for admissions, ownership and terminal arbitration."""
from datetime import datetime
from sqlalchemy import Boolean, CheckConstraint, ForeignKey, ForeignKeyConstraint, Index, Integer, UniqueConstraint, LargeBinary, Date
from sqlalchemy.dialects.mysql import VARBINARY
from sqlalchemy.orm import Mapped, mapped_column
from backend.database import Base
from backend.models.memory_control import U64, UUID, DIGEST, INSTANT, ascii_string

CHAT_LIFECYCLE_TABLE_NAMES = frozenset({'chat_user_state','chat_generation','chat_submission',
    'chat_submission_message','chat_message_state','chat_generation_message','chat_resend_quota','chat_lifecycle_effect'})

class Dates:
    created_at: Mapped[datetime] = mapped_column(INSTANT, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(INSTANT, default=datetime.utcnow, onupdate=datetime.utcnow)

class ChatUserState(Dates, Base):
    __tablename__='chat_user_state'
    __table_args__=(ForeignKeyConstraint(['user_id','current_generation_id'],['chat_generation.user_id','chat_generation.generation_id'],name='fk_chat_current_generation',use_alter=True),)
    user_id: Mapped[int] = mapped_column(Integer,ForeignKey('users.id',ondelete='CASCADE'),primary_key=True)
    current_generation_id: Mapped[str|None] = mapped_column(UUID)
    state_revision: Mapped[int] = mapped_column(U64,default=0,server_default='0')

class ChatGeneration(Dates, Base):
    __tablename__='chat_generation'
    __table_args__=(UniqueConstraint('user_id','generation_id',name='uq_chat_generation_user'),
        CheckConstraint("state IN ('pending','success','failed','superseded')",name='ck_chat_generation_state'),
        CheckConstraint("phase IN ('admitted','running','commit_prepared','commit_unknown','reconcile_exhausted','terminal')",name='ck_chat_generation_phase'),
        CheckConstraint("dispatch_state IN ('pending','claimed','done')",name='ck_chat_dispatch_state'),
        CheckConstraint("commit_evidence_kind IS NULL OR commit_evidence_kind = 'atomic_decision'",name='ck_chat_evidence'),
        CheckConstraint("state != 'success' OR (round_id IS NOT NULL AND commit_marker IS NOT NULL AND decision_at IS NOT NULL AND decision_at < deadline_at AND commit_evidence_kind = 'atomic_decision')",name='ck_chat_success'),
        CheckConstraint("reason IS NULL OR reason IN ('llm_failed','content_blocked','prompt_budget_exceeded','prompt_budget_unverified','deadline_exceeded','generation_superseded','execution_lost','commit_unknown','deadline_unverified','storage_unavailable','legacy_record','legacy_pending','id_conflict','expired')",name="ck_chat_generation_reason"),
        Index('ix_chat_deadline','state','deadline_at'),Index('ix_chat_dispatch','dispatch_state','next_dispatch_at'),Index('ix_chat_reconcile','phase','reconcile_until'))
    generation_id: Mapped[str] = mapped_column(UUID,primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer,ForeignKey('users.id',ondelete='CASCADE'))
    timing_config_version: Mapped[str] = mapped_column(ascii_string(64))
    accepted_at: Mapped[datetime] = mapped_column(INSTANT)
    deadline_at: Mapped[datetime] = mapped_column(INSTANT)
    state: Mapped[str] = mapped_column(ascii_string(16),default='pending')
    phase: Mapped[str] = mapped_column(ascii_string(24),default='admitted')
    state_revision: Mapped[int] = mapped_column(U64)
    reason: Mapped[str|None] = mapped_column(ascii_string(64))
    round_id: Mapped[str|None] = mapped_column(UUID,unique=True)
    commit_marker: Mapped[str|None] = mapped_column(UUID,unique=True)
    decision_at: Mapped[datetime|None] = mapped_column(INSTANT)
    commit_observed_at: Mapped[datetime|None] = mapped_column(INSTANT)
    commit_evidence_kind: Mapped[str|None] = mapped_column(ascii_string(24))
    lease_owner: Mapped[str|None] = mapped_column(UUID)
    lease_epoch: Mapped[int] = mapped_column(U64,default=0,server_default='0')
    lease_until: Mapped[datetime|None] = mapped_column(INSTANT)
    dispatch_state: Mapped[str] = mapped_column(ascii_string(16),default='pending')
    next_dispatch_at: Mapped[datetime] = mapped_column(INSTANT)
    remote_started_at: Mapped[datetime|None] = mapped_column(INSTANT)
    reconcile_until: Mapped[datetime] = mapped_column(INSTANT)
    terminal_at: Mapped[datetime|None] = mapped_column(INSTANT)

class ChatSubmission(Dates, Base):
    __tablename__='chat_submission'
    __table_args__=(UniqueConstraint('user_id','operation','request_id',name='uq_chat_submission_key'),
        UniqueConstraint('user_id','id',name='uq_chat_submission_user'),
        ForeignKeyConstraint(['user_id','accepted_generation_id'],['chat_generation.user_id','chat_generation.generation_id'],name='fk_chat_submission_generation'),
        CheckConstraint("operation IN ('send','resend')",name='ck_chat_operation'),
        CheckConstraint("channel IN ('h5','open','internal')",name='ck_chat_channel'),
        CheckConstraint("record_state IN ('active','tombstone')",name='ck_chat_record_state'),
        CheckConstraint("record_state != 'active' OR (fingerprint IS NOT NULL AND fingerprint_version IS NOT NULL AND accepted_generation_id IS NOT NULL)",name='ck_chat_active_submission'),Index('ix_chat_retention','record_state','expires_at'))
    id: Mapped[int] = mapped_column(U64,primary_key=True,autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer,ForeignKey('users.id',ondelete='CASCADE'))
    operation: Mapped[str] = mapped_column(ascii_string(8))
    request_id: Mapped[bytes] = mapped_column(LargeBinary(512).with_variant(VARBINARY(512),'mysql'))
    client_key_present: Mapped[bool] = mapped_column(Boolean)
    fingerprint: Mapped[bytes|None] = mapped_column(DIGEST)
    fingerprint_version: Mapped[int|None] = mapped_column(Integer)
    channel: Mapped[str] = mapped_column(ascii_string(16))
    accepted_generation_id: Mapped[str|None] = mapped_column(UUID)
    accepted_at: Mapped[datetime] = mapped_column(INSTANT)
    expires_at: Mapped[datetime] = mapped_column(INSTANT)
    tombstone_until: Mapped[datetime] = mapped_column(INSTANT)
    record_state: Mapped[str] = mapped_column(ascii_string(12),default='active')

class ChatSubmissionMessage(Dates, Base):
    __tablename__='chat_submission_message'
    __table_args__=(UniqueConstraint('submission_id','ordinal',name='uq_chat_submission_ordinal'),
        ForeignKeyConstraint(['user_id','submission_id'],['chat_submission.user_id','chat_submission.id'],name='fk_chat_sm_submission'),
        ForeignKeyConstraint(['user_id','conversation_id'],['conversation_log.user_id','conversation_log.id'],name='fk_chat_sm_conversation'),Index('ix_chat_sm_message','user_id','conversation_id'))
    submission_id: Mapped[int] = mapped_column(U64,primary_key=True)
    conversation_id: Mapped[int] = mapped_column(Integer,primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer)
    ordinal: Mapped[int] = mapped_column(Integer)

class ChatMessageState(Dates, Base):
    __tablename__='chat_message_state'
    __table_args__=(ForeignKeyConstraint(['user_id','conversation_id'],['conversation_log.user_id','conversation_log.id'],name='fk_chat_ms_conversation'),
        ForeignKeyConstraint(['user_id','effective_generation_id'],['chat_generation.user_id','chat_generation.generation_id'],name='fk_chat_ms_generation'),
        CheckConstraint("processing_state IN ('pending','success','failed','superseded')",name='ck_chat_message_state'),Index('ix_chat_ms_generation','user_id','effective_generation_id'))
    conversation_id: Mapped[int] = mapped_column(Integer,primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer)
    effective_generation_id: Mapped[str] = mapped_column(UUID)
    state_revision: Mapped[int] = mapped_column(U64)
    processing_state: Mapped[str] = mapped_column(ascii_string(16))
    reason: Mapped[str|None] = mapped_column(ascii_string(64))
    status_changed_at: Mapped[datetime] = mapped_column(INSTANT)

class ChatGenerationMessage(Dates, Base):
    __tablename__='chat_generation_message'
    __table_args__=(UniqueConstraint('generation_id','ordinal',name='uq_chat_generation_ordinal'),
        ForeignKeyConstraint(['user_id','generation_id'],['chat_generation.user_id','chat_generation.generation_id'],name='fk_chat_gm_generation'),
        ForeignKeyConstraint(['user_id','conversation_id'],['conversation_log.user_id','conversation_log.id'],name='fk_chat_gm_conversation'))
    generation_id: Mapped[str] = mapped_column(UUID,primary_key=True)
    conversation_id: Mapped[int] = mapped_column(Integer,primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer)
    ordinal: Mapped[int] = mapped_column(Integer)
    in_prompt: Mapped[bool] = mapped_column(Boolean)

class ChatResendQuota(Dates, Base):
    __tablename__='chat_resend_quota'
    __table_args__=(CheckConstraint('accepted_count BETWEEN 0 AND 2',name='ck_chat_resend_count'),Index('ix_chat_resend_expiry','expires_at'))
    user_id: Mapped[int] = mapped_column(Integer,ForeignKey('users.id',ondelete='CASCADE'),primary_key=True)
    batch_sort_seq: Mapped[int] = mapped_column(U64,primary_key=True)
    window_started_at: Mapped[datetime] = mapped_column(INSTANT)
    expires_at: Mapped[datetime] = mapped_column(INSTANT)
    accepted_count: Mapped[int] = mapped_column(Integer,default=0)

class ChatLifecycleEffect(Dates, Base):
    __tablename__='chat_lifecycle_effect'
    __table_args__=(UniqueConstraint('owner_kind','owner_id','effect_kind',name='uq_chat_effect'),
        CheckConstraint("state IN ('pending','running','done','failed','unverified')",name='ck_chat_effect_state'),
        CheckConstraint("owner_kind IN ('chat','future')",name='ck_chat_effect_owner'),Index('ix_chat_effect_pending','state','next_attempt_at'))
    id: Mapped[int] = mapped_column(U64,primary_key=True,autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer,ForeignKey('users.id',ondelete='CASCADE'))
    owner_kind: Mapped[str] = mapped_column(ascii_string(8))
    owner_id: Mapped[str] = mapped_column(UUID)
    effect_kind: Mapped[str] = mapped_column(ascii_string(32))
    state: Mapped[str] = mapped_column(ascii_string(16))
    attempts: Mapped[int] = mapped_column(Integer,default=0)
    next_attempt_at: Mapped[datetime|None] = mapped_column(INSTANT)
    lease_owner: Mapped[str|None] = mapped_column(UUID)
    lease_until: Mapped[datetime|None] = mapped_column(INSTANT)
    last_reason: Mapped[str|None] = mapped_column(ascii_string(64))
    effect_date: Mapped[datetime|None] = mapped_column(Date)
    completed_at: Mapped[datetime|None] = mapped_column(INSTANT)
