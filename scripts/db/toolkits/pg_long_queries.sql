-- scripts/db/toolkits/pg_long_queries.sql · Pack 48-H Round 6 · #159
-- Queries activas > 30s. READ-ONLY.

SELECT pid, usename, application_name, client_addr, state,
       now() - query_start AS run_for,
       now() - xact_start  AS tx_age,
       wait_event_type, wait_event,
       left(query, 200) AS query
FROM pg_stat_activity
WHERE state = 'active'
  AND now() - query_start > interval '30 seconds'
ORDER BY run_for DESC;
