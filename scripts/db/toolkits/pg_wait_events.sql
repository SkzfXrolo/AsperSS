-- scripts/db/toolkits/pg_wait_events.sql · Pack 48-H Round 6 · #159
-- Distribución de wait events en este snapshot.
-- Para análisis temporal, programar muestreos repetidos (cada 5s) y agregar.

SELECT wait_event_type, wait_event, count(*) AS sessions
FROM pg_stat_activity
WHERE state <> 'idle' AND wait_event IS NOT NULL
GROUP BY wait_event_type, wait_event
ORDER BY sessions DESC
LIMIT 30;
