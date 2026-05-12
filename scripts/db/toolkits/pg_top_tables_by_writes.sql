-- scripts/db/toolkits/pg_top_tables_by_writes.sql · Pack 48-H Round 6 · #159
-- Top tablas por escrituras (inserts + updates + deletes acumulados desde reset).

SELECT schemaname, relname,
       n_tup_ins AS inserts,
       n_tup_upd AS updates,
       n_tup_del AS deletes,
       (n_tup_ins + n_tup_upd + n_tup_del) AS total_writes,
       n_tup_hot_upd AS hot_updates,
       last_autovacuum, last_autoanalyze
FROM pg_stat_user_tables
ORDER BY total_writes DESC
LIMIT 30;
