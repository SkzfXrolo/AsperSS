-- scripts/db/stress-test/connection-storm.sql · Pack 48-H Round 5 · #150
-- Simula muchas sesiones concurrentes livianas (SELECT 1).
-- USO: lanzar N veces en paralelo desde bash/PowerShell contra NON-PROD.
-- Ejemplo bash: for i in $(seq 1 100); do psql "$URL" -c "SELECT pg_sleep(0.01), $i;" & done; wait

SELECT 1 AS connection_heartbeat, now() AS ts;

-- Opcional: mantener sesión abierta breve para probar pool
SELECT pg_sleep(5);
