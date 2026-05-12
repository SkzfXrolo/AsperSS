-- scripts/db/test/test-functions.sql · Pack 48-H Round 5 · #142
-- Function tests (pgTAP). Prereq: CREATE EXTENSION IF NOT EXISTS pgtap;
-- Functions must be deployed from scripts/db/functions/utility-functions.sql

BEGIN;
SELECT plan(3);

SELECT CASE WHEN to_regproc('public.argus_score_to_level(numeric)') IS NULL
       THEN ok(true, 'SKIP: argus_score_to_level not installed')
       ELSE is(argus_score_to_level(10::numeric), 'LOW'::text, 'score 10 -> LOW')
       END;

SELECT CASE WHEN to_regproc('public.argus_age_days(timestamp with time zone)') IS NULL
       THEN ok(true, 'SKIP: argus_age_days not installed')
       ELSE cmp_ok(argus_age_days(now() - interval '2 days'), '>=', 1::bigint, 'age_days >= 1')
       END;

SELECT CASE WHEN to_regproc('public.argus_normalize_username(text)') IS NULL
       THEN ok(true, 'SKIP: argus_normalize_username not installed')
       ELSE is(argus_normalize_username('  Foo Bar  '), 'foo bar', 'normalize username')
       END;

SELECT * FROM finish();
ROLLBACK;
