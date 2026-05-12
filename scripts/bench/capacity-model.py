#!/usr/bin/env python3
import argparse


def project(users, scans_per_day, cost_per_scan, growth, months):
    cur = users
    out = []
    for m in range(1, months + 1):
        monthly_scans = cur * scans_per_day * 30
        monthly_cost = monthly_scans * cost_per_scan
        out.append((m, cur, monthly_scans, monthly_cost))
        cur = int(cur * (1 + growth))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--users", type=int, default=1000)
    ap.add_argument("--scans-per-day", type=float, default=1.0)
    ap.add_argument("--cost-per-scan", type=float, default=0.01)
    ap.add_argument("--growth", type=float, default=0.1, help="mensual, ej 0.1=10%")
    ap.add_argument("--months", type=int, default=12)
    args = ap.parse_args()

    print("month,users,monthly_scans,monthly_cost")
    for r in project(args.users, args.scans_per_day, args.cost_per_scan, args.growth, args.months):
        print(f"{r[0]},{r[1]},{int(r[2])},{r[3]:.2f}")


if __name__ == "__main__":
    main()
