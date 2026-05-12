#!/usr/bin/env python3
# ============================================================================
# Argus Projects — Pack 48-H Round 3 · #101
# synthetic-data-generator.py
# ----------------------------------------------------------------------------
# Genera data sintética masiva para staging / load testing.
# - 10k scans, 50k violations (default).
# - Distribución realista de verdicts/severities/timestamps.
# - Anonymization helper para clonar prod a dev (faker para PII).
#
# Requisitos:
#   pip install psycopg2-binary faker
#
# Uso:
#   python scripts/db/synthetic-data-generator.py --db-url $DATABASE_URL \
#       --companies 3 --players 500 --scans 10000 --violations 50000
#
#   python scripts/db/synthetic-data-generator.py --anonymize-from $PROD_DUMP \
#       --to-dev-url $DEV_DATABASE_URL
# ============================================================================
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import random
import sys
import uuid
from typing import Iterable

try:
    import psycopg2
    from psycopg2.extras import execute_values
except ImportError:  # pragma: no cover
    psycopg2 = None  # type: ignore

try:
    from faker import Faker
    fake = Faker()
except ImportError:
    Faker = None  # type: ignore
    fake = None

VIOLATION_TYPES = ["fly", "speed", "reach", "killaura", "xray", "badpkt", "nofall"]
VIOLATION_SEVERITY = ["low", "medium", "high", "critical"]
SEVERITY_WEIGHTS = [0.5, 0.3, 0.15, 0.05]
SCAN_VERDICT = ["clean", "suspicious", "ban", None]
VERDICT_WEIGHTS = [0.78, 0.15, 0.05, 0.02]


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def weighted_choice(items, weights):
    return random.choices(items, weights=weights, k=1)[0]


def rand_dt(within_days: int = 30) -> dt.datetime:
    secs = random.randint(0, within_days * 86400)
    return dt.datetime.utcnow() - dt.timedelta(seconds=secs)


def hash_pii(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


# ----------------------------------------------------------------------------
# Generators
# ----------------------------------------------------------------------------
def gen_companies(n: int) -> list[tuple]:
    return [
        (i, f"Company {i}", f"company-{i}", random.choice(["free", "pro", "enterprise"]))
        for i in range(1, n + 1)
    ]


def gen_users(companies: list[tuple]) -> list[tuple]:
    rows = []
    uid = 1
    for cid, *_ in companies:
        for role in ["admin", "staff", "staff", "viewer", "api"]:
            email = fake.email() if fake else f"user{uid}@example.com"
            rows.append((uid, cid, email, "$2b$12$SYNTHETIC", role))
            uid += 1
    return rows


def gen_players(n_players: int) -> list[tuple]:
    return [
        (str(uuid.uuid4()),
         (fake.user_name() if fake else f"player_{i}"))
        for i in range(n_players)
    ]


def gen_scans(n: int, companies: list[tuple], players: list[tuple],
              tokens_per_company: int = 20) -> Iterable[tuple]:
    company_ids = [c[0] for c in companies]
    for i in range(1, n + 1):
        cid = random.choice(company_ids)
        puuid, pname = random.choice(players)
        started = rand_dt(60)
        completed = started + dt.timedelta(seconds=random.randint(5, 90))
        status = weighted_choice(["completed", "completed", "completed", "error", "in_progress"],
                                 [0.85, 0.05, 0.0, 0.05, 0.05])
        verdict = None if status != "completed" else weighted_choice(SCAN_VERDICT, VERDICT_WEIGHTS)
        risk = round(random.betavariate(2, 5) * 100, 2)
        token_id = ((i - 1) % tokens_per_company) + 1 + (cid - 1) * tokens_per_company
        yield (i, token_id, hash_pii(f"machine-{i}"), pname,
               started, completed if status == "completed" else None,
               status, verdict, risk)


def gen_violations(n: int, n_scans: int) -> Iterable[tuple]:
    for i in range(1, n + 1):
        sid = random.randint(1, n_scans)
        yield (i, sid,
               random.choice(VIOLATION_TYPES),
               weighted_choice(VIOLATION_SEVERITY, SEVERITY_WEIGHTS),
               rand_dt(60))


# ----------------------------------------------------------------------------
# Insert
# ----------------------------------------------------------------------------
def bulk_insert(conn, table: str, cols: list[str], rows: Iterable[tuple]):
    cur = conn.cursor()
    sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES %s ON CONFLICT DO NOTHING"
    batch = []
    total = 0
    for r in rows:
        batch.append(r)
        if len(batch) >= 5000:
            execute_values(cur, sql, batch)
            total += len(batch)
            batch.clear()
    if batch:
        execute_values(cur, sql, batch)
        total += len(batch)
    conn.commit()
    cur.close()
    return total


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db-url", help="target DB to populate (synthetic mode)")
    ap.add_argument("--companies", type=int, default=3)
    ap.add_argument("--players", type=int, default=500)
    ap.add_argument("--scans", type=int, default=10_000)
    ap.add_argument("--violations", type=int, default=50_000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--anonymize-from", help="(future) path to prod dump to anonymize")
    ap.add_argument("--to-dev-url", help="(future) target dev DB for anonymize mode")
    args = ap.parse_args()

    random.seed(args.seed)

    if args.anonymize_from:
        print("Anonymize mode: see TODO in README. Out of scope for Pack48-H Round 3.")
        return 0

    if not args.db_url:
        print("ERROR: --db-url required (synthetic mode)", file=sys.stderr)
        return 2
    if psycopg2 is None:
        print("ERROR: psycopg2 not installed", file=sys.stderr)
        return 2

    print(f"[1/4] Connecting to {args.db_url.split('@')[-1]}...")
    conn = psycopg2.connect(args.db_url)

    print(f"[2/4] Generating {args.companies} companies, {args.players} players...")
    companies = gen_companies(args.companies)
    users = gen_users(companies)
    players = gen_players(args.players)

    print("[3/4] Bulk inserting...")
    bulk_insert(conn, "companies",
                ["id", "name", "slug", "plan"], companies)
    bulk_insert(conn, "users",
                ["id", "company_id", "email", "password_hash", "role"], users)

    n_scans = bulk_insert(conn, "scans",
                          ["id", "token_id", "machine_id", "minecraft_username",
                           "started_at", "completed_at", "status", "verdict", "risk_score"],
                          gen_scans(args.scans, companies, players))
    print(f"  ✓ scans: {n_scans}")

    n_v = bulk_insert(conn, "plugin_violations",
                      ["id", "scan_id", "violation_type", "severity", "detected_at"],
                      gen_violations(args.violations, args.scans))
    print(f"  ✓ violations: {n_v}")

    print("[4/4] Done. Re-set sequences manually if needed (see seed-data.sql tail).")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
