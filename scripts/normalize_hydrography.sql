TRUNCATE ana_hydrography RESTART IDENTITY;
INSERT INTO ana_hydrography (source_id, name, source_version, geom)
SELECT
    cotrecho::text,
    COALESCE(NULLIF(noriocomp, ''), NULLIF(nooriginal, ''), NULLIF(nogenerico, '')),
    COALESCE(NULLIF(dsversao, ''), 'ANA BHO 6.2.4'),
    ST_Multi(ST_CollectionExtract(ST_MakeValid(geom), 2))
FROM ana_hydrography_stage
WHERE geom IS NOT NULL;
ANALYZE ana_hydrography;
