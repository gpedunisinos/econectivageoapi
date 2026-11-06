TRUNCATE ibge_biomes RESTART IDENTITY;
INSERT INTO ibge_biomes (name, source_version, geom)
SELECT
    COALESCE(NULLIF(nm_bioma, ''), NULLIF(cd_bioma, ''), 'Não identificado'),
    'IBGE 2025 1:250.000',
    ST_Multi(ST_CollectionExtract(ST_MakeValid(geom), 3))
FROM ibge_biomes_stage
WHERE geom IS NOT NULL;
ANALYZE ibge_biomes;
