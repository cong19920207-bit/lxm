"""STEP002 frozen Future consumption authority; no new generation/retry platform."""
from datetime import datetime
from sqlalchemy import Integer, String, ForeignKey, ForeignKeyConstraint, UniqueConstraint, CheckConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from backend.database import Base
from backend.models.chat_lifecycle import Dates
from backend.models.memory_control import U64, UUID, INSTANT, ascii_string

class FutureConsumption(Dates, Base):
    __tablename__ = 'future_consumption'
    __table_args__ = (
        UniqueConstraint('user_id', 'slot_version', name='uq_future_slot'),
        ForeignKeyConstraint(['user_id','agent_message_id'], ['agent_message.user_id','agent_message.id'], name='fk_future_message'),
        CheckConstraint("state IN ('pending','success','failed','superseded')", name='ck_future_state'),
        CheckConstraint("phase IN ('admitted','running','commit_prepared','commit_unknown','reconcile_exhausted','terminal')", name='ck_future_phase'),
        CheckConstraint("success_kind IS NULL OR success_kind IN ('normal','fallback')", name='ck_future_kind'),
        CheckConstraint("commit_evidence_kind IS NULL OR commit_evidence_kind='atomic_decision'", name='ck_future_evidence'),
        CheckConstraint("state != 'success' OR (round_id IS NOT NULL AND commit_marker IS NOT NULL AND decision_at IS NOT NULL AND decision_at < deadline_at AND commit_evidence_kind='atomic_decision')", name='ck_future_success'),
        CheckConstraint("reason IS NULL OR reason IN ('llm_failed','content_blocked','prompt_budget_exceeded','prompt_budget_unverified','deadline_exceeded','generation_superseded','execution_lost','commit_unknown','deadline_unverified','storage_unavailable','legacy_record','legacy_pending','id_conflict','expired')", name='ck_future_reason'),
        Index('ix_future_deadline','state','deadline_at'), Index('ix_future_reconcile','phase','reconcile_until'),
    )
    consume_id: Mapped[str] = mapped_column(UUID, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id',ondelete='CASCADE'))
    slot_version: Mapped[int] = mapped_column(U64)
    slot_timestamp: Mapped[int] = mapped_column(Integer)
    slot_action: Mapped[str] = mapped_column(String(200))
    timing_config_version: Mapped[str] = mapped_column(ascii_string(64))
    accepted_at: Mapped[datetime] = mapped_column(INSTANT)
    deadline_at: Mapped[datetime] = mapped_column(INSTANT)
    state: Mapped[str] = mapped_column(ascii_string(16), default='pending')
    phase: Mapped[str] = mapped_column(ascii_string(24), default='admitted')
    state_revision: Mapped[int] = mapped_column(U64)
    reason: Mapped[str|None] = mapped_column(ascii_string(64))
    success_kind: Mapped[str|None] = mapped_column(ascii_string(8))
    agent_message_id: Mapped[int|None] = mapped_column(Integer, unique=True)
    round_id: Mapped[str|None] = mapped_column(UUID)
    commit_marker: Mapped[str|None] = mapped_column(UUID, unique=True)
    decision_at: Mapped[datetime|None] = mapped_column(INSTANT)
    commit_observed_at: Mapped[datetime|None] = mapped_column(INSTANT)
    commit_evidence_kind: Mapped[str|None] = mapped_column(ascii_string(24))
    lease_owner: Mapped[str|None] = mapped_column(UUID)
    lease_epoch: Mapped[int] = mapped_column(U64, default=0, server_default='0')
    lease_until: Mapped[datetime|None] = mapped_column(INSTANT)
    remote_started_at: Mapped[datetime|None] = mapped_column(INSTANT)
    reconcile_until: Mapped[datetime] = mapped_column(INSTANT)
    terminal_at: Mapped[datetime|None] = mapped_column(INSTANT)
