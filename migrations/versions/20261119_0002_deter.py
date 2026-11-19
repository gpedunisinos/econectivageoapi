"""Bounded, replaceable DETER Amazônia snapshot."""

from alembic import op

revision = "20261119_0002"
down_revision = "20260829_0001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE deter_import_state (
            singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),
            fetched_at timestamptz NOT NULL, period_start date NOT NULL,
            period_end date NOT NULL, records integer NOT NULL, rejected integer NOT NULL
        );
        CREATE TABLE deter_alerts (
            id text PRIMARY KEY, source_id text NOT NULL, class_name text NOT NULL,
            observed_on date NOT NULL, municipality text, state text,
            geom geometry(MultiPolygon,4326) NOT NULL CHECK(NOT ST_IsEmpty(geom))
        );
        CREATE INDEX deter_alerts_geom_gix ON deter_alerts USING gist(geom);
        CREATE INDEX deter_alerts_date_idx ON deter_alerts(observed_on);
    """)


def downgrade():
    op.execute("DROP TABLE deter_alerts; DROP TABLE deter_import_state")
