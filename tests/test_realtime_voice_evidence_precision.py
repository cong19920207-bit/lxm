"""Evidence timestamps must survive MySQL storage without changing report identity."""
from sqlalchemy.dialects import mysql, sqlite
from backend.models.realtime_voice import VoiceCapabilityEvidence


def test_evidence_timestamp_types_keep_microseconds_on_mysql():
    for name in ('tested_at', 'verified_at', 'expires_at'):
        column = VoiceCapabilityEvidence.__table__.c[name]
        assert column.type.compile(dialect=mysql.dialect()) == 'DATETIME(6)'
        assert column.type.compile(dialect=sqlite.dialect()) == 'DATETIME'
