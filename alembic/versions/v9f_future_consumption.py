"""Frozen STEP015 Future consumption schema."""
from alembic import op
revision = 'v9f_future_consumption_001'
down_revision = 'v9e_chat_lifecycle_001'
branch_labels = None
depends_on = None

def upgrade():
    op.execute("ALTER TABLE relationship ADD COLUMN future_slot_version BIGINT UNSIGNED NOT NULL DEFAULT 0")
    op.create_unique_constraint('uq_agent_message_user_id','agent_message',['user_id','id'])
    op.execute("\nCREATE TABLE future_consumption (\n\tconsume_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL, \n\tuser_id INTEGER NOT NULL, \n\tslot_version BIGINT UNSIGNED NOT NULL, \n\tslot_timestamp INTEGER NOT NULL, \n\tslot_action VARCHAR(200) NOT NULL, \n\ttiming_config_version VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL, \n\taccepted_at DATETIME(6) NOT NULL, \n\tdeadline_at DATETIME(6) NOT NULL, \n\tstate VARCHAR(16) CHARACTER SET ascii COLLATE ascii_bin NOT NULL, \n\tphase VARCHAR(24) CHARACTER SET ascii COLLATE ascii_bin NOT NULL, \n\tstate_revision BIGINT UNSIGNED NOT NULL, \n\treason VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin, \n\tsuccess_kind VARCHAR(8) CHARACTER SET ascii COLLATE ascii_bin, \n\tagent_message_id INTEGER, \n\tround_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin, \n\tcommit_marker CHAR(36) CHARACTER SET ascii COLLATE ascii_bin, \n\tdecision_at DATETIME(6), \n\tcommit_observed_at DATETIME(6), \n\tcommit_evidence_kind VARCHAR(24) CHARACTER SET ascii COLLATE ascii_bin, \n\tlease_owner CHAR(36) CHARACTER SET ascii COLLATE ascii_bin, \n\tlease_epoch BIGINT UNSIGNED NOT NULL DEFAULT '0', \n\tlease_until DATETIME(6), \n\tremote_started_at DATETIME(6), \n\treconcile_until DATETIME(6) NOT NULL, \n\tterminal_at DATETIME(6), \n\tcreated_at DATETIME(6) NOT NULL, \n\tupdated_at DATETIME(6) NOT NULL, \n\tPRIMARY KEY (consume_id), \n\tCONSTRAINT uq_future_slot UNIQUE (user_id, slot_version), \n\tCONSTRAINT fk_future_message FOREIGN KEY(user_id, agent_message_id) REFERENCES agent_message (user_id, id), \n\tCONSTRAINT ck_future_state CHECK (state IN ('pending','success','failed','superseded')), \n\tCONSTRAINT ck_future_phase CHECK (phase IN ('admitted','running','commit_prepared','commit_unknown','reconcile_exhausted','terminal')), \n\tCONSTRAINT ck_future_kind CHECK (success_kind IS NULL OR success_kind IN ('normal','fallback')), \n\tCONSTRAINT ck_future_evidence CHECK (commit_evidence_kind IS NULL OR commit_evidence_kind='atomic_decision'), \n\tCONSTRAINT ck_future_success CHECK (state != 'success' OR (round_id IS NOT NULL AND commit_marker IS NOT NULL AND decision_at IS NOT NULL AND decision_at < deadline_at AND commit_evidence_kind='atomic_decision')), \n\tCONSTRAINT ck_future_reason CHECK (reason IS NULL OR reason IN ('llm_failed','content_blocked','prompt_budget_exceeded','prompt_budget_unverified','deadline_exceeded','generation_superseded','execution_lost','commit_unknown','deadline_unverified','storage_unavailable','legacy_record','legacy_pending','id_conflict','expired')), \n\tFOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, \n\tUNIQUE (agent_message_id), \n\tUNIQUE (commit_marker)\n)\n\n ENGINE=InnoDB")
    op.execute('CREATE INDEX ix_future_deadline ON future_consumption (state, deadline_at)')
    op.execute('CREATE INDEX ix_future_reconcile ON future_consumption (phase, reconcile_until)')

def downgrade():
    op.drop_table('future_consumption')
    op.drop_constraint('uq_agent_message_user_id','agent_message',type_='unique')
    op.drop_column('relationship','future_slot_version')
