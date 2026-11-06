TRUNCATE ibge_census_sectors RESTART IDENTITY;
WITH sectors AS (
    SELECT
        cd_setor,
        max(area_km2) AS area_km2,
        ST_Multi(ST_CollectionExtract(ST_UnaryUnion(ST_Collect(geom)), 3)) AS geom
    FROM ibge_census_sectors_stage
    WHERE geom IS NOT NULL
    GROUP BY cd_setor
)
INSERT INTO ibge_census_sectors (
    sector_code, population, area_km2, density_km2, source_version, geom
)
SELECT
    geometry.cd_setor,
    CASE WHEN statistics.v0001 ~ '^[0-9]+$' THEN statistics.v0001::integer END,
    geometry.area_km2,
    CASE WHEN statistics.v0001 ~ '^[0-9]+$'
        THEN statistics.v0001::double precision / NULLIF(geometry.area_km2, 0)
    END,
    'Censo 2022, agregados 2026-05-20',
    geometry.geom
FROM sectors geometry
LEFT JOIN ibge_census_stats_stage statistics USING (cd_setor);
ANALYZE ibge_census_sectors;
