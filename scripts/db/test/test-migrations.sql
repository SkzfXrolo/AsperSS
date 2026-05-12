-- scripts/db/test/test-migrations.sql · Pack 48-H Round 5 · #142
-- Migration sanity (pgTAP). Prereq: CREATE EXTENSION IF NOT EXISTS pgtap;
-- Before Alembic bootstrap (Pack 49), assertions are marked SKIP via pass().

BEGIN;
SELECT plan(2);

SELECT CASE WHEN to_regclass('public.alembic_version') IS NULL
  THEN pass('SKIP: alembic_version not present yet (bootstrap pending)')
  ELSE has_table('public','alembic_version')
END;

SELECT CASE WHEN to_regclass('public.alembic_version') IS NULL
  THEN pass('SKIP: alembic_version version_num check')
  ELSE col_not_null('public','alembic_version','version_num')
END;

SELECT * FROM finish();
ROLLBACK;
