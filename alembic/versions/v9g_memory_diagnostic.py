"""STEP017 permanent diagnostic execution and snapshots."""
from alembic import op
revision = 'v9g_memory_diagnostic_001'
down_revision = 'v9f_future_consumption_001'
branch_labels = None
depends_on = None

def upgrade():
    op.execute("\nCREATE TABLE memory_diagnostic_run (\n\trun_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL, \n\tadmin_id INTEGER NOT NULL, \n\tuser_id INTEGER, \n\tenvironment_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL, \n\trequest_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL, \n\trequest_digest BINARY(32) NOT NULL, \n\tsource VARCHAR(8) CHARACTER SET ascii COLLATE ascii_bin, \n\tparent_run_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin, \n\tinput_text TEXT, \n\texecution_state VARCHAR(24) CHARACTER SET ascii COLLATE ascii_bin NOT NULL, \n\thistory_state VARCHAR(16) CHARACTER SET ascii COLLATE ascii_bin NOT NULL, \n\tresult_revision BIGINT UNSIGNED NOT NULL DEFAULT '1', \n\tcreated_at DATETIME(6) NOT NULL, \n\tobserved_at DATETIME(6) NOT NULL, \n\tdeadline_at DATETIME(6) NOT NULL, \n\tpersist_deadline_at DATETIME(6) NOT NULL, \n\tstarted_at DATETIME(6), \n\tfinished_at DATETIME(6), \n\tterminal_at DATETIME(6), \n\tstage VARCHAR(32) CHARACTER SET ascii COLLATE ascii_bin, \n\tcontrolled_reason VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin, \n\tfrozen_versions JSON, \n\tcontext_sources JSON, \n\tcandidate_snapshots JSON, \n\tselection_result JSON, \n\tmetrics JSON, \n\tsnapshot_available BOOL NOT NULL DEFAULT '0', \n\tlease_owner CHAR(36) CHARACTER SET ascii COLLATE ascii_bin, \n\tlease_version BIGINT UNSIGNED NOT NULL DEFAULT '0', \n\tlease_until DATETIME(6), \n\tdeleted_at DATETIME(6), \n\ttombstone_until DATETIME(6), \n\tPRIMARY KEY (run_id), \n\tCONSTRAINT uq_memory_diagnostic_request UNIQUE (admin_id, request_id), \n\tCONSTRAINT ck_memory_diagnostic_source CHECK (source IS NULL OR source IN ('main','openapi','step8')), \n\tCONSTRAINT ck_memory_diagnostic_execution CHECK (execution_state IN ('accepted','running','completed','degraded','failed','budget_blocked','interrupted','manual_required')), \n\tCONSTRAINT ck_memory_diagnostic_history CHECK (history_state IN ('pending','saved','failed','unknown','deleted')), \n\tCONSTRAINT ck_memory_diagnostic_revision CHECK (result_revision >= 1)\n)\n\n ENGINE=InnoDB")
    op.execute('CREATE INDEX ix_memory_diagnostic_active ON memory_diagnostic_run (environment_id, execution_state, deadline_at)')
    op.execute('CREATE INDEX ix_memory_diagnostic_user_created ON memory_diagnostic_run (user_id, created_at, run_id)')

def downgrade():
    op.drop_table("memory_diagnostic_run")
