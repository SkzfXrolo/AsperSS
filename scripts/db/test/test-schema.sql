-- scripts/db/test/test-schema.sql · Pack 48-H Round 5 · #142
-- Schema tests (pgTAP). Prereq: CREATE EXTENSION IF NOT EXISTS pgtap;
-- Run: pg_prove -d $DBURI scripts/db/test/test-schema.sql
--      OR: psql -v ON_ERROR_STOP=1 -f test-schema.sql

BEGIN;
SELECT plan(5);

SELECT has_table('public', 'scans');
SELECT has_table('public', 'companies');
SELECT has_table('public', 'ai_decisions_log');
SELECT has_column('public', 'scans', 'id');
SELECT col_not_null('public', 'companies', 'id');

SELECT * FROM finish();
ROLLBACK;
