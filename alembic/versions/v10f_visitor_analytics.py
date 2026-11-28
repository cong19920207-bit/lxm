"""Independent H5 event, visit, device and daily retention."""
from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import DATETIME

revision = "v10f_visitor_analytics_001"
down_revision = "v10e_feed_video_fields_001"
branch_labels = None
depends_on = None


def upgrade():
    inspector = None if context.is_offline_mode() else sa.inspect(op.get_bind())
    existing = set(inspector.get_table_names()) if inspector else set()
    time = sa.DateTime().with_variant(DATETIME(fsp=6), "mysql")

    def field(name, datatype, **options):
        return sa.Column(name, datatype, nullable=False, **options)

    def count(name):
        return field(name, sa.BigInteger(), server_default="0")

    def table(name, *columns):
        if name not in existing:
            op.create_table(name, *columns)

    table("h5_visitor_activation",
          field("id", sa.Integer(), primary_key=True, autoincrement=False),
          field("enabled_at", time),
          sa.CheckConstraint("id = 1", name="ck_h5_visitor_activation_one"))
    table("h5_visitor_day", field("day", sa.Date(), primary_key=True),
          count("visitors"), count("visits"), count("opens"), count("unidentified_opens"))
    table("h5_visitor_device", field("visitor_id", sa.String(36), primary_key=True),
          field("first_at", time), field("last_at", time), field("last_event_id", sa.String(36)),
          field("identity", sa.String(32)), sa.Column("network", sa.JSON()), sa.Column("profile", sa.JSON()),
          sa.Column("profile_at", time), count("visits"), count("opens"))
    table("h5_visitor_visit", field("visit_id", sa.String(36), primary_key=True),
          field("day", sa.Date()), field("visitor_id", sa.String(36)),
          field("started_at", time), field("last_activity", time), count("opens"))
    table("h5_visitor_event", field("event_id", sa.String(36), primary_key=True),
          sa.Column("visitor_id", sa.String(36)), sa.Column("visit_id", sa.String(36)),
          field("day", sa.Date()), field("kind", sa.String(16)), field("entry", sa.String(32)),
          field("occurred_at", time), field("received_at", time), field("identity", sa.String(32)),
          field("identity_source", sa.String(16)), sa.Column("network", sa.JSON()),
          field("delayed", sa.Boolean(), server_default="0"))
    indexes = {
        "h5_visitor_device": {"ix_h5_device_recent": ["last_at", "visitor_id"]},
        "h5_visitor_visit": {"ix_h5_visit_day_device": ["day", "visitor_id", "started_at"],
                             "ix_h5_visit_expiry": ["last_activity"]},
        "h5_visitor_event": {"ix_h5_event_device_day": ["visitor_id", "day", "occurred_at"],
                             "ix_h5_event_visit": ["visit_id", "occurred_at"],
                             "ix_h5_event_expiry": ["occurred_at"]},
    }
    for name, wanted in indexes.items():
        present = {i["name"] for i in inspector.get_indexes(name)} if inspector else set()
        for index, columns in wanted.items():
            if index not in present:
                op.create_index(index, name, columns)

    # Enable only after every table and index exists. Retrying MySQL DDL preserves this instant.
    now = "UTC_TIMESTAMP(6)" if op.get_context().dialect.name == "mysql" else "CURRENT_TIMESTAMP"
    op.execute(f"INSERT INTO h5_visitor_activation (id, enabled_at) SELECT 1, {now} "
               "WHERE NOT EXISTS (SELECT 1 FROM h5_visitor_activation WHERE id=1)")


def downgrade():
    for suffix in ("event", "visit", "device", "day", "activation"):
        op.drop_table("h5_visitor_" + suffix)
