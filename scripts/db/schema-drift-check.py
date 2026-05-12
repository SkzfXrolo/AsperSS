#!/usr/bin/env python3
# ============================================================================
# Argus Projects — Pack 48-H Round 3 · #100
# schema-drift-check.py
# ----------------------------------------------------------------------------
# Compara el schema real de Postgres contra un "expected" en JSON.
# Pensado para correr en CI o en cron weekly.
#
# Uso:
#   python scripts/db/schema-drift-check.py \
#       --db-url "$DATABASE_URL" \
#       --expected scripts/db/golden-schema.json \
#       [--ignore-extra-indexes] \
#       [--slack-webhook URL]
#
# Exit code:
#   0  -> schema OK
#   1  -> drift detectado
#   2  -> error de conexión / parámetros
# ============================================================================
from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any

try:
    import psycopg2
    import psycopg2.extras
except ImportError:  # pragma: no cover
    psycopg2 = None  # type: ignore


EXCLUDE_TABLE_PATTERNS = [
    re.compile(r"^pg_"),
    re.compile(r"^sql_"),
    re.compile(r"_pkey$"),
    re.compile(r"^tmp_"),
    re.compile(r"^_alembic_"),
    re.compile(r"^scans_\d{4}_\d{2}$"),                 # partitioning
    re.compile(r"^ai_decisions_log_\d{4}w\d{2}$"),
    re.compile(r"^staff_audit_log_\d{4}q\d$"),
]


def is_excluded(name: str) -> bool:
    return any(p.search(name) for p in EXCLUDE_TABLE_PATTERNS)


# ----------------------------------------------------------------------------
# Reading "actual" from Postgres
# ----------------------------------------------------------------------------
SQL_COLUMNS = """
SELECT table_name, column_name, data_type, is_nullable, column_default,
       character_maximum_length
FROM information_schema.columns
WHERE table_schema = 'public'
ORDER BY table_name, ordinal_position;
"""

SQL_INDEXES = """
SELECT schemaname, tablename, indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'public'
ORDER BY tablename, indexname;
"""

SQL_CONSTRAINTS = """
SELECT tc.table_name, tc.constraint_name, tc.constraint_type
FROM information_schema.table_constraints tc
WHERE tc.table_schema = 'public'
ORDER BY tc.table_name, tc.constraint_name;
"""


def fetch_actual(dsn: str) -> dict[str, Any]:
    if psycopg2 is None:
        print("ERROR: psycopg2 no instalado", file=sys.stderr)
        sys.exit(2)
    conn = psycopg2.connect(dsn)
    conn.set_session(readonly=True)
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    tables: dict[str, dict[str, Any]] = {}

    cur.execute(SQL_COLUMNS)
    for row in cur.fetchall():
        t = row["table_name"]
        if is_excluded(t):
            continue
        tables.setdefault(t, {"columns": {}, "indexes": [], "constraints": []})
        col_type = row["data_type"]
        if row["character_maximum_length"]:
            col_type = f"{col_type}({row['character_maximum_length']})"
        tables[t]["columns"][row["column_name"]] = {
            "type": col_type,
            "nullable": row["is_nullable"] == "YES",
            "default": row["column_default"],
        }

    cur.execute(SQL_INDEXES)
    for row in cur.fetchall():
        t = row["tablename"]
        if is_excluded(t) or is_excluded(row["indexname"]):
            continue
        if t not in tables:
            continue
        tables[t]["indexes"].append({
            "name": row["indexname"],
            "def": row["indexdef"],
        })

    cur.execute(SQL_CONSTRAINTS)
    for row in cur.fetchall():
        t = row["table_name"]
        if is_excluded(t):
            continue
        if t not in tables:
            continue
        tables[t]["constraints"].append({
            "name": row["constraint_name"],
            "type": row["constraint_type"],
        })

    cur.close()
    conn.close()
    return {"tables": tables}


# ----------------------------------------------------------------------------
# Diff
# ----------------------------------------------------------------------------
def diff_schemas(actual: dict, expected: dict, *, ignore_extra_indexes=False) -> list[dict]:
    issues: list[dict] = []
    a_tables = set(actual["tables"])
    e_tables = set(expected["tables"])

    for t in sorted(e_tables - a_tables):
        issues.append({"kind": "missing_table", "name": t, "severity": "critical"})
    for t in sorted(a_tables - e_tables):
        issues.append({"kind": "extra_table", "name": t, "severity": "medium"})

    for t in sorted(a_tables & e_tables):
        a_cols = actual["tables"][t]["columns"]
        e_cols = expected["tables"][t]["columns"]
        for c in sorted(set(e_cols) - set(a_cols)):
            issues.append({"kind": "missing_column", "table": t, "column": c, "severity": "critical"})
        for c in sorted(set(a_cols) - set(e_cols)):
            issues.append({"kind": "extra_column", "table": t, "column": c, "severity": "medium"})
        for c in sorted(set(a_cols) & set(e_cols)):
            a, e = a_cols[c], e_cols[c]
            if a["type"] != e["type"]:
                issues.append({
                    "kind": "type_mismatch",
                    "table": t, "column": c,
                    "actual": a["type"], "expected": e["type"],
                    "severity": "high",
                })
            if a["nullable"] != e["nullable"]:
                issues.append({
                    "kind": "nullable_mismatch",
                    "table": t, "column": c,
                    "actual": a["nullable"], "expected": e["nullable"],
                    "severity": "high",
                })

        a_idx = {i["name"] for i in actual["tables"][t]["indexes"]}
        e_idx = {i["name"] for i in expected["tables"][t]["indexes"]}
        for i in sorted(e_idx - a_idx):
            issues.append({"kind": "missing_index", "table": t, "index": i, "severity": "medium"})
        if not ignore_extra_indexes:
            for i in sorted(a_idx - e_idx):
                issues.append({"kind": "extra_index", "table": t, "index": i, "severity": "low"})

        a_cons = {c["name"] for c in actual["tables"][t]["constraints"]}
        e_cons = {c["name"] for c in expected["tables"][t]["constraints"]}
        for c in sorted(e_cons - a_cons):
            issues.append({"kind": "missing_constraint", "table": t, "constraint": c, "severity": "high"})

    return issues


def severity_summary(issues: list[dict]) -> dict[str, int]:
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for i in issues:
        counts[i.get("severity", "low")] = counts.get(i.get("severity", "low"), 0) + 1
    return counts


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db-url", required=True)
    ap.add_argument("--expected", required=True, help="path to expected schema JSON")
    ap.add_argument("--ignore-extra-indexes", action="store_true")
    ap.add_argument("--slack-webhook", help="optional Slack webhook to post results")
    ap.add_argument("--dump-actual", help="optional path to dump current schema JSON")
    args = ap.parse_args()

    try:
        with open(args.expected, "r", encoding="utf-8") as f:
            expected = json.load(f)
    except OSError as e:
        print(f"ERROR: cannot read --expected: {e}", file=sys.stderr)
        return 2

    actual = fetch_actual(args.db_url)
    if args.dump_actual:
        with open(args.dump_actual, "w", encoding="utf-8") as f:
            json.dump(actual, f, indent=2, sort_keys=True)

    issues = diff_schemas(actual, expected, ignore_extra_indexes=args.ignore_extra_indexes)
    summary = severity_summary(issues)
    output = {"summary": summary, "issues": issues}
    print(json.dumps(output, indent=2, sort_keys=True))

    if args.slack_webhook and (summary["critical"] or summary["high"]):
        try:
            import urllib.request
            payload = {
                "text": f":rotating_light: Schema drift: "
                        f"{summary['critical']} critical, {summary['high']} high, "
                        f"{summary['medium']} medium issues."
            }
            req = urllib.request.Request(
                args.slack_webhook,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:  # noqa: BLE001
            print(f"WARN: slack notify failed: {e}", file=sys.stderr)

    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
