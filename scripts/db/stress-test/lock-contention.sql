-- scripts/db/stress-test/lock-contention.sql · Pack 48-H Round 5 · #150
-- Dos sesiones deben ejecutar secciones A y B en paralelo para deadlock/lock wait.
-- Sesión A:
BEGIN;
UPDATE bench_lock_box SET counter = counter + 1 WHERE id = 1;
SELECT pg_sleep(5);
UPDATE bench_lock_box SET counter = counter + 1 WHERE id = 2;
COMMIT;

-- Sesión B (iniciar ~1s después):
-- BEGIN;
-- UPDATE bench_lock_box SET counter = counter + 1 WHERE id = 2;
-- SELECT pg_sleep(5);
-- UPDATE bench_lock_box SET counter = counter + 1 WHERE id = 1;
-- COMMIT;

CREATE TABLE IF NOT EXISTS bench_lock_box (
  id int PRIMARY KEY,
  counter int NOT NULL DEFAULT 0
);

INSERT INTO bench_lock_box VALUES (1,0),(2,0)
ON CONFLICT (id) DO NOTHING;

-- Placeholder select para ejecución single-session (no-op safe)
SELECT 'read instructions in header; run A/B in two sessions' AS note;
