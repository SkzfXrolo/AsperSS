-- scripts/db/toolkits/pg_cache_hit_ratio.sql · Pack 48-H Round 6 · #159
-- Cache hit ratio (buffer cache) global y por tabla top.

SELECT 'global' AS scope,
       round(sum(blks_hit)::numeric / NULLIF(sum(blks_hit + blks_read), 0), 4) AS hit_ratio,
       sum(blks_hit) AS hits, sum(blks_read) AS reads
FROM pg_stat_database;

SELECT relname AS table,
       round(heap_blks_hit::numeric / NULLIF(heap_blks_hit + heap_blks_read, 0), 4) AS heap_hit_ratio,
       round(idx_blks_hit::numeric  / NULLIF(idx_blks_hit  + idx_blks_read,  0), 4) AS idx_hit_ratio
FROM pg_statio_user_tables
ORDER BY heap_blks_hit + heap_blks_read DESC
LIMIT 20;
