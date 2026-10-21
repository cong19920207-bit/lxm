"""BGM asset ownership, catalog, recoverable operations and bounded admission.

Frozen DDL; application startup must not create these tables implicitly.
"""
from alembic import op

revision = 'v9h_bgm_001'
down_revision = 'v9g_memory_diagnostic_001'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE TABLE bgm_asset (\n\tid VARCHAR(36) NOT NULL, \n\ttrack_id VARCHAR(36) NOT NULL, \n\toperation_id VARCHAR(36) NOT NULL, \n\tattempt INTEGER NOT NULL, \n\tkind VARCHAR(8) NOT NULL, \n\tbucket VARCHAR(128) NOT NULL, \n\tobject_key VARCHAR(255) NOT NULL, \n\tversion VARCHAR(36) NOT NULL, \n\tsha256 VARCHAR(64), \n\tmime_type VARCHAR(64), \n\tsize_bytes BIGINT, \n\tpublic_url VARCHAR(2048), \n\tstate VARCHAR(24) NOT NULL, \n\tcleanup_state VARCHAR(24) NOT NULL, \n\tfailure_category VARCHAR(64), \n\tretired_at DATETIME(6), \n\tnot_before DATETIME(6), \n\tcreated_at DATETIME(6) NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT ck_bgm_asset_kind CHECK (kind IN ('audio','cover')), \n\tUNIQUE (object_key)\n) ENGINE=InnoDB")
    op.execute('CREATE INDEX ix_bgm_asset_owner ON bgm_asset (track_id, state)')
    op.execute('CREATE TABLE bgm_catalog (\n\tid INTEGER NOT NULL, \n\tcatalog_version BIGINT NOT NULL, \n\tdefault_track_id VARCHAR(36), \n\tPRIMARY KEY (id), \n\tCONSTRAINT ck_bgm_catalog_singleton CHECK (id = 1), \n\tCONSTRAINT ck_bgm_catalog_version CHECK (catalog_version >= 0)\n) ENGINE=InnoDB')
    op.execute('CREATE TABLE bgm_operation (\n\tid VARCHAR(36) NOT NULL, \n\tadmin_id INTEGER NOT NULL, \n\taction VARCHAR(24) NOT NULL, \n\ttrack_id VARCHAR(36), \n\trequest_digest VARCHAR(64) NOT NULL, \n\trequest_snapshot JSON NOT NULL, \n\tsource_sha256 VARCHAR(64), \n\tsource_size BIGINT, \n\tattempt INTEGER NOT NULL, \n\towner_id VARCHAR(64), \n\tstate VARCHAR(24) NOT NULL, \n\tdeadline_at DATETIME(6), \n\treceive_deadline_at DATETIME(6), \n\tresult JSON, \n\tfailure_category VARCHAR(64), \n\tcreated_at DATETIME(6) NOT NULL, \n\tfinished_at DATETIME(6), \n\tPRIMARY KEY (id)\n) ENGINE=InnoDB')
    op.execute('CREATE INDEX ix_bgm_operation_recovery ON bgm_operation (state, deadline_at)')
    op.execute('CREATE INDEX ix_bgm_operation_track_id ON bgm_operation (track_id)')
    op.execute('CREATE TABLE bgm_processing_slot (\n\tid INTEGER NOT NULL AUTO_INCREMENT, \n\toperation_id VARCHAR(36), \n\towner_id VARCHAR(64), \n\tattempt INTEGER NOT NULL, \n\tstate VARCHAR(24) NOT NULL, \n\tlease_until DATETIME(6), \n\tdeadline_at DATETIME(6), \n\tPRIMARY KEY (id), \n\tUNIQUE (operation_id)\n) ENGINE=InnoDB')
    op.execute("CREATE TABLE bgm_track (\n\tid VARCHAR(36) NOT NULL, \n\tname VARCHAR(240) NOT NULL, \n\trecord_version BIGINT NOT NULL, \n\taudio_state VARCHAR(24) NOT NULL, \n\tenabled BOOL NOT NULL, \n\tsort_position INTEGER, \n\tever_published BOOL NOT NULL, \n\thidden_at DATETIME(6), \n\taudio_asset_id VARCHAR(36), \n\tcover_asset_id VARCHAR(36), \n\tmedia_version VARCHAR(36), \n\tcover_version VARCHAR(36), \n\tduration_seconds FLOAT, \n\tsize_bytes BIGINT, \n\tattempt INTEGER NOT NULL, \n\tactive_operation_id VARCHAR(36), \n\tfailure_category VARCHAR(64), \n\tcreated_at DATETIME(6) NOT NULL, \n\tupdated_at DATETIME(6) NOT NULL, \n\tPRIMARY KEY (id), \n\tCONSTRAINT ck_bgm_track_revision CHECK (record_version >= 1), \n\tCONSTRAINT ck_bgm_track_state CHECK (audio_state IN ('receiving','processing','ready','failed','deleting','delete_failed','deleted')), \n\tCONSTRAINT ck_bgm_enabled_ready CHECK (enabled = 0 OR audio_state = 'ready')\n) ENGINE=InnoDB")
    op.execute('CREATE INDEX ix_bgm_track_listing ON bgm_track (audio_state, created_at, id)')
    op.execute("INSERT INTO bgm_catalog (id, catalog_version) VALUES (1, 0)")
    op.execute("INSERT INTO bgm_processing_slot (id, attempt, state) VALUES (1, 0, 'free')")


def downgrade():
    op.drop_table('bgm_track')
    op.drop_table('bgm_processing_slot')
    op.drop_table('bgm_operation')
    op.drop_table('bgm_catalog')
    op.drop_table('bgm_asset')
