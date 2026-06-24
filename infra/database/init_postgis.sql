-- ─────────────────────────────────────────────────────────────
--  PostGIS — Inicialização: Aves Brasil
-- ─────────────────────────────────────────────────────────────

-- extensões
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;
CREATE EXTENSION IF NOT EXISTS unaccent;

-- ── tabela de ocorrências espaciais ──────────────────────────
CREATE TABLE IF NOT EXISTS ocorrencias (
    id                BIGSERIAL PRIMARY KEY,
    nome_cientifico   TEXT NOT NULL,
    fonte             TEXT NOT NULL,           -- gbif | sibbr | ebird
    fonte_id          TEXT,                    -- id original na fonte
    data_observacao   DATE,
    municipio         TEXT,
    estado            CHAR(2),
    pais              CHAR(2) DEFAULT 'BR',
    altitude_m        NUMERIC(7,1),
    instituicao       TEXT,
    geom              GEOMETRY(Point, 4326),   -- coordenada WGS84
    inserido_em       TIMESTAMPTZ DEFAULT NOW()
);

-- índices espaciais e de busca
CREATE INDEX IF NOT EXISTS idx_ocorr_geom
    ON ocorrencias USING GIST (geom);

CREATE INDEX IF NOT EXISTS idx_ocorr_especie
    ON ocorrencias (nome_cientifico);

CREATE INDEX IF NOT EXISTS idx_ocorr_estado
    ON ocorrencias (estado);

CREATE INDEX IF NOT EXISTS idx_ocorr_fonte
    ON ocorrencias (fonte);

-- ── biomas do Brasil (polígonos para filtro espacial) ─────────
CREATE TABLE IF NOT EXISTS biomas (
    id     SERIAL PRIMARY KEY,
    nome   TEXT NOT NULL,
    geom   GEOMETRY(MultiPolygon, 4326)
);

CREATE INDEX IF NOT EXISTS idx_biomas_geom
    ON biomas USING GIST (geom);

-- ── view: ocorrências enriquecidas com bioma ─────────────────
CREATE OR REPLACE VIEW ocorrencias_por_bioma AS
SELECT
    o.id,
    o.nome_cientifico,
    o.fonte,
    o.data_observacao,
    o.estado,
    o.municipio,
    b.nome AS bioma,
    ST_X(o.geom) AS longitude,
    ST_Y(o.geom) AS latitude,
    o.altitude_m
FROM ocorrencias o
LEFT JOIN biomas b ON ST_Within(o.geom, b.geom);

-- ── view: densidade de ocorrências por espécie e estado ──────
CREATE OR REPLACE VIEW densidade_por_estado AS
SELECT
    nome_cientifico,
    estado,
    COUNT(*)                          AS total_registros,
    MIN(data_observacao)              AS primeira_observacao,
    MAX(data_observacao)              AS ultima_observacao,
    ST_ConvexHull(ST_Collect(geom))  AS area_ocorrencia
FROM ocorrencias
WHERE geom IS NOT NULL
GROUP BY nome_cientifico, estado;

-- ── função: espécies em raio de uma coordenada ───────────────
CREATE OR REPLACE FUNCTION especies_proximas(
    p_lon   FLOAT,
    p_lat   FLOAT,
    p_raio_km FLOAT DEFAULT 50
)
RETURNS TABLE (
    nome_cientifico TEXT,
    total_registros BIGINT,
    distancia_km    FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        o.nome_cientifico,
        COUNT(*)::BIGINT,
        ROUND(
            ST_Distance(
                ST_SetSRID(ST_MakePoint(p_lon, p_lat), 4326)::geography,
                o.geom::geography
            ) / 1000.0
        , 1)::FLOAT AS distancia_km
    FROM ocorrencias o
    WHERE ST_DWithin(
        o.geom::geography,
        ST_SetSRID(ST_MakePoint(p_lon, p_lat), 4326)::geography,
        p_raio_km * 1000
    )
    GROUP BY o.nome_cientifico, distancia_km
    ORDER BY distancia_km;
END;
$$ LANGUAGE plpgsql;
