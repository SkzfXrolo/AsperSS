-- scripts/db/stress-test/long-transaction.sql · Pack 48-H Round 5 · #150
-- Mantiene una transacción abierta con lock compartido en fila dummy.
-- NON-PROD. Propósito: ver impacto `idle in transaction` + bloqueo lecturas concurrentes.

BEGIN;

CREATE TABLE IF NOT EXISTS bench_long_tx_anchor (
  id int PRIMARY KEY,
  note text
);

INSERT INTO bench_long_tx_anchor VALUES (1, 'hold')
ON CONFLICT (id) DO UPDATE SET note = EXCLUDED.note;

SELECT * FROM bench_long_tx_anchor WHERE id = 1 FOR SHARE;

SELECT pg_sleep(120);  -- ajustar duración; matar con pg_terminate_backend si necesario

ROLLBACK;
