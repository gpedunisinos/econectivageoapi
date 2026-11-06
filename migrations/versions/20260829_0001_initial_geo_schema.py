"""Create the initial geospatial schema.

Revision ID: 20260829_0001
Revises:
Create Date: 2026-08-29
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260829_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute(
        """
        CREATE TABLE dataset_imports (
            id bigserial PRIMARY KEY,
            dataset varchar(100) NOT NULL,
            version varchar(100) NOT NULL,
            source_url text NOT NULL,
            checksum_sha256 varchar(64),
            imported_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (dataset, version)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE ibge_biomes (
            id bigserial PRIMARY KEY,
            name varchar(100) NOT NULL,
            source_version varchar(100) NOT NULL DEFAULT 'IBGE 1:250.000',
            geom geometry(MultiPolygon, 4326) NOT NULL
        )
        """
    )
    op.execute("CREATE INDEX ibge_biomes_geom_gix ON ibge_biomes USING gist (geom)")
    op.execute(
        """
        CREATE TABLE ana_hydrography (
            id bigserial PRIMARY KEY,
            source_id varchar(100),
            name varchar(255),
            source_version varchar(100) NOT NULL DEFAULT 'ANA BHO6',
            geom geometry(MultiLineString, 4326) NOT NULL
        )
        """
    )
    op.execute("CREATE INDEX ana_hydrography_geom_gix ON ana_hydrography USING gist (geom)")
    op.execute(
        """
        CREATE TABLE ibge_census_sectors (
            id bigserial PRIMARY KEY,
            sector_code varchar(20) NOT NULL UNIQUE,
            population integer,
            area_km2 double precision NOT NULL,
            density_km2 double precision,
            source_version varchar(100) NOT NULL DEFAULT 'Censo 2022',
            geom geometry(MultiPolygon, 4326) NOT NULL
        )
        """
    )
    op.execute(
        "CREATE INDEX ibge_census_sectors_geom_gix "
        "ON ibge_census_sectors USING gist (geom)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ibge_census_sectors")
    op.execute("DROP TABLE IF EXISTS ana_hydrography")
    op.execute("DROP TABLE IF EXISTS ibge_biomes")
    op.execute("DROP TABLE IF EXISTS dataset_imports")
