#!/usr/bin/env python3
# ============================================================================
# Argus Projects — Pack 48-H Round 3 · #107
# cost-projection.py
# ----------------------------------------------------------------------------
# Proyección de costos de DB sobre 12 meses. Lee tabla de tiers + drivers de
# crecimiento + clientes actuales, escupe una tabla por mes con tier
# recomendado y costo estimado.
#
# Uso:
#   python scripts/db/cost-projection.py \
#       --current-clients 10 \
#       --growth-per-month 25 \
#       --current-gb 3 \
#       --months 12 \
#       [--gb-per-client-month 0.07] \
#       [--include-replica]
# ============================================================================
from __future__ import annotations

import argparse
import dataclasses
import sys


@dataclasses.dataclass(frozen=True)
class Tier:
    name: str
    storage_gb_included: int
    monthly_usd: float
    cpu_label: str
    ram_gb: int


# Snapshot pricing 2026-Q2 (ajustar cuando cambie).
TIERS: list[Tier] = [
    Tier("Basic",         10,   7.0,  "shared", 1),
    Tier("Standard",      60,  35.0,  "2 vCPU", 4),
    Tier("Pro",          200,  95.0,  "4 vCPU", 16),
    Tier("Pro+",         500, 195.0,  "8 vCPU", 32),
    Tier("Heroku-large",1024, 395.0, "16 vCPU", 64),
]

STORAGE_OVERAGE_USD_PER_GB = 0.20
REPLICA_MULTIPLIER = 1.0          # asumir misma tier para replica


def select_tier(needed_gb: float) -> Tier:
    for t in TIERS:
        if needed_gb <= t.storage_gb_included:
            return t
    return TIERS[-1]


def cost_for_tier(tier: Tier, gb_used: float, include_replica: bool = False) -> float:
    base = tier.monthly_usd
    overage = max(0.0, gb_used - tier.storage_gb_included) * STORAGE_OVERAGE_USD_PER_GB
    total = base + overage
    if include_replica:
        total += base * REPLICA_MULTIPLIER
    return total


def project(args) -> list[dict]:
    results = []
    clients = args.current_clients
    gb = args.current_gb
    for m in range(args.months + 1):
        gb_growth = clients * args.gb_per_client_month
        gb_now = gb + (gb_growth * m)
        clients_now = clients + (args.growth_per_month * m)
        # estimación del crecimiento se basa en client_count promedio del mes
        # (modelo simple, no acumulativo per cliente).
        tier = select_tier(gb_now)
        cost = cost_for_tier(tier, gb_now, include_replica=args.include_replica)
        results.append({
            "month": m,
            "clients": clients_now,
            "gb_used": round(gb_now, 2),
            "tier": tier.name,
            "monthly_usd": round(cost, 2),
        })
    return results


def print_table(rows: list[dict]) -> None:
    headers = ["month", "clients", "gb_used", "tier", "monthly_usd"]
    widths = {h: max(len(h), max(len(str(r[h])) for r in rows)) for h in headers}
    line = " | ".join(h.ljust(widths[h]) for h in headers)
    sep = "-+-".join("-" * widths[h] for h in headers)
    print(line)
    print(sep)
    for r in rows:
        print(" | ".join(str(r[h]).ljust(widths[h]) for h in headers))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--current-clients", type=int, default=10)
    ap.add_argument("--growth-per-month", type=int, default=25)
    ap.add_argument("--current-gb", type=float, default=3.0)
    ap.add_argument("--gb-per-client-month", type=float, default=0.07)
    ap.add_argument("--months", type=int, default=12)
    ap.add_argument("--include-replica", action="store_true")
    ap.add_argument("--format", choices=["table", "json"], default="table")
    args = ap.parse_args()

    rows = project(args)
    if args.format == "json":
        import json
        print(json.dumps(rows, indent=2))
    else:
        print_table(rows)
        total = sum(r["monthly_usd"] for r in rows[1:])  # excluye mes 0
        print()
        print(f"Total 12-month spend (excluding current month): ${total:,.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
