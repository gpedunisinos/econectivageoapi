CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS dataset_imports (
    id bigserial PRIMARY KEY,
    dataset varchar(100) NOT NULL,
    version varchar(100) NOT NULL,
    source_url text NOT NULL,
    checksum_sha256 varchar(64),
    imported_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (dataset, version)
);

CREATE TABLE IF NOT EXISTS ibge_biomes (
    id bigserial PRIMARY KEY,
    name varchar(100) NOT NULL,
    source_version varchar(100) NOT NULL DEFAULT 'IBGE 1:250.000',
    geom geometry(MultiPolygon, 4326) NOT NULL
);
CREATE INDEX IF NOT EXISTS ibge_biomes_geom_gix ON ibge_biomes USING gist (geom);

CREATE TABLE IF NOT EXISTS ana_hydrography (
    id bigserial PRIMARY KEY,
    source_id varchar(100),
    name varchar(255),
    source_version varchar(100) NOT NULL DEFAULT 'ANA BHO6',
    geom geometry(MultiLineString, 4326) NOT NULL
);
CREATE INDEX IF NOT EXISTS ana_hydrography_geom_gix ON ana_hydrography USING gist (geom);

CREATE TABLE IF NOT EXISTS ibge_census_sectors (
    id bigserial PRIMARY KEY,
    sector_code varchar(20) NOT NULL UNIQUE,
    population integer,
    area_km2 double precision NOT NULL,
    density_km2 double precision,
    source_version varchar(100) NOT NULL DEFAULT 'Censo 2022',
    geom geometry(MultiPolygon, 4326) NOT NULL
);
CREATE INDEX IF NOT EXISTS ibge_census_sectors_geom_gix
    ON ibge_census_sectors USING gist (geom);

