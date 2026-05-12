-- scripts/db/toolkits/pg_connection_breakdown.sql · Pack 48-H Round 6 · #159
-- Breakdown de conexiones por estado, usuario, app.

SELECT state, count(*) FROM pg_stat_activity GROUP BY state ORDER BY 2 DESC;

SELECT usename, count(*) FROM pg_stat_activity GROUP BY usename ORDER BY 2 DESC;

SELECT application_name, count(*) FROM pg_stat_activity GROUP BY application_name ORDER BY 2 DESC;

SELECT count(*) FILTER (WHERE state='idle in transaction') AS idle_in_tx,
       count(*) FILTER (WHERE state='active') AS active,
       count(*) FILTER (WHERE state='idle') AS idle,
       max(extract(epoch FROM (now() - xact_start))) FILTER (WHERE state='idle in transaction') AS oldest_idle_in_tx_seconds
FROM pg_stat_activity;
