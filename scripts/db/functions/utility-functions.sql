-- ============================================================================
-- Argus Projects — Pack 48-H Round 4 · #120
-- functions/utility-functions.sql
-- ----------------------------------------------------------------------------
-- Helper functions reusables en queries, MVs, exports, etl.
-- Filosofía:
--   - inmutables cuando es posible (cacheables por el planner).
--   - prefijo argus_*
--   - sin side effects (no INSERT/UPDATE/DELETE).
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ---------------------------------------------------------------------------
-- argus_anonymize_ip(inet)
--   Truncar IPv4 a /24 y IPv6 a /48 para analytics sin perder geolocalización.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION argus_anonymize_ip(p_ip inet)
RETURNS inet
LANGUAGE sql
IMMUTABLE PARALLEL SAFE
AS $$
    SELECT CASE
        WHEN family(p_ip) = 4 THEN set_masklen(p_ip, 24)::cidr::inet
        WHEN family(p_ip) = 6 THEN set_masklen(p_ip, 48)::cidr::inet
        ELSE p_ip
    END;
$$;

COMMENT ON FUNCTION argus_anonymize_ip(inet) IS
'Reduces IPv4 to /24 and IPv6 to /48 for analytics. Pack48-H #120.';

-- ---------------------------------------------------------------------------
-- argus_score_to_level(numeric)
--   Mapea risk_score numérico a tier nominal (LOW/MID/HIGH/CRITICAL).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION argus_score_to_level(p_score numeric)
RETURNS varchar(16)
LANGUAGE sql
IMMUTABLE PARALLEL SAFE
AS $$
    SELECT CASE
        WHEN p_score IS NULL  THEN 'UNKNOWN'
        WHEN p_score >= 80    THEN 'CRITICAL'
        WHEN p_score >= 60    THEN 'HIGH'
        WHEN p_score >= 30    THEN 'MID'
        ELSE                       'LOW'
    END::varchar(16);
$$;

-- ---------------------------------------------------------------------------
-- argus_hash_pii(text, salt_key)
--   HMAC SHA-256 para pseudonimización determinística.
--   Uso típico: hash(player_uuid + 'dw') → token estable para DW.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION argus_hash_pii(p_value text, p_salt text DEFAULT 'argus-default-salt')
RETURNS text
LANGUAGE sql
IMMUTABLE PARALLEL SAFE
AS $$
    SELECT encode(hmac(COALESCE(p_value, ''), COALESCE(p_salt, ''), 'sha256'), 'hex');
$$;

COMMENT ON FUNCTION argus_hash_pii(text, text) IS
'HMAC-SHA256 for stable pseudonymization. Use distinct salts for different contexts.';

-- ---------------------------------------------------------------------------
-- argus_truncate_email(text)
--   Convierte "john.doe@example.com" → "j*****@example.com" para logs.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION argus_truncate_email(p_email text)
RETURNS text
LANGUAGE sql
IMMUTABLE PARALLEL SAFE
AS $$
    SELECT CASE
        WHEN p_email IS NULL OR p_email NOT LIKE '%@%' THEN NULL
        ELSE substring(p_email FOR 1) || '*****' || substring(p_email FROM position('@' IN p_email))
    END;
$$;

-- ---------------------------------------------------------------------------
-- argus_age_days(ts)
--   Días enteros entre ts y NOW. Usa NOW() no statement_timestamp(), por
--   tanto NO inmutable.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION argus_age_days(p_ts timestamp with time zone)
RETURNS integer
LANGUAGE sql
STABLE PARALLEL SAFE
AS $$
    SELECT EXTRACT(DAY FROM NOW() - p_ts)::int;
$$;

-- ---------------------------------------------------------------------------
-- argus_safe_json(text)
--   Devuelve text::jsonb o NULL si falla parsing. Útil en ETL.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION argus_safe_json(p_value text)
RETURNS jsonb
LANGUAGE plpgsql
IMMUTABLE PARALLEL SAFE
AS $$
BEGIN
    RETURN p_value::jsonb;
EXCEPTION WHEN OTHERS THEN
    RETURN NULL;
END;
$$;

-- ---------------------------------------------------------------------------
-- argus_normalize_username(text)
--   Lowercase + trim + remove invisibles.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION argus_normalize_username(p_name text)
RETURNS text
LANGUAGE sql
IMMUTABLE PARALLEL SAFE
AS $$
    SELECT lower(regexp_replace(COALESCE(p_name, ''), '[\u200B-\u200D\uFEFF\s]', '', 'g'));
$$;

-- ---------------------------------------------------------------------------
-- argus_risk_color(numeric)
--   Color CSS para dashboards.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION argus_risk_color(p_score numeric)
RETURNS text
LANGUAGE sql
IMMUTABLE PARALLEL SAFE
AS $$
    SELECT CASE argus_score_to_level(p_score)
        WHEN 'CRITICAL' THEN '#c33'
        WHEN 'HIGH'     THEN '#e91'
        WHEN 'MID'      THEN '#dd0'
        WHEN 'LOW'      THEN '#3a3'
        ELSE                  '#888'
    END;
$$;

-- ---------------------------------------------------------------------------
-- Self-test (opcional, para CI)
-- ---------------------------------------------------------------------------
DO $$
BEGIN
    ASSERT argus_anonymize_ip('192.168.1.42'::inet) = '192.168.1.0/24'::inet,
        'argus_anonymize_ip ipv4 failed';
    ASSERT argus_score_to_level(85) = 'CRITICAL';
    ASSERT argus_score_to_level(NULL) = 'UNKNOWN';
    ASSERT argus_hash_pii('foo','salt') = argus_hash_pii('foo','salt'),
        'hash must be deterministic';
    ASSERT argus_hash_pii('foo','salt') <> argus_hash_pii('foo','other-salt'),
        'hash must depend on salt';
    ASSERT argus_truncate_email('john@example.com') = 'j*****@example.com';
    RAISE NOTICE 'argus utility functions self-test OK';
END $$;

-- ============================================================================
-- FIN
-- ============================================================================
