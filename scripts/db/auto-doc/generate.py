#!/usr/bin/env python3
"""scripts/db/auto-doc/generate.py · Pack 48-H #130

Generador de documentación automática del schema PostgreSQL.

Lee el schema actual desde information_schema + pg_catalog y produce un
markdown navegable agrupado por dominio.

Uso:
    python generate.py \\
        --dsn "postgresql://user:pass@host:5432/db" \\
        --out docs/db/auto-schema.md \\
        [--include-views] [--include-mvs] [--include-functions]

Si --dsn no se da, intenta leer DATABASE_URL del entorno.

SAFETY:
- Solo SELECTs read-only contra information_schema y pg_catalog.
- No modifica nada.
- No conecta a producción salvo que se pase DSN explícito.

Dependencias:
- psycopg2-binary >=2.9 (o psycopg2)

NOTA: este script no se conecta a DB en runtime de CI por default;
es una utility para correr localmente o en un job programado.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import sys
import textwrap
from collections import defaultdict
from typing import Iterable

try:
    import psycopg2
    import psycopg2.extras
except Exception:
    psycopg2 = None  # tolerated: scripts can be inspected without dep installed


DOMAIN_MAP = {
    # tabla → dominio (best-effort; sobreescribir si necesario)
    "users": "auth",
    "sessions": "auth",
    "api_keys": "auth",
    "companies": "tenant",
    "company_settings": "tenant",
    "scans": "scans",
    "scan_artifacts": "scans",
    "violations": "scans",
    "ai_decisions_log": "ai",
    "ai_player_profiles": "ai",
    "ai_feedback": "ai",
    "ai_calibrations": "ai",
    "plugin_metadata": "plugin",
    "plugin_servers": "plugin",
    "plugin_heartbeats": "plugin",
    "ban_history": "moderation",
    "warnings": "moderation",
    "staff_audit_log": "audit",
    "ddl_log": "audit",
    "data_quality_runs": "ops",
    "bench_runs": "ops",
}


def domain_of(table: str) -> str:
    if table in DOMAIN_MAP:
        return DOMAIN_MAP[table]
    if table.startswith("ai_"):
        return "ai"
    if table.startswith("plugin_"):
        return "plugin"
    if table.endswith("_log") or table.endswith("_audit"):
        return "audit"
    if table.startswith("mv_"):
        return "analytics"
    if table.startswith("cache_") or table.startswith("tmp_"):
        return "cache"
    if table.startswith("bench_") or table.startswith("data_quality"):
        return "ops"
    return "other"


def fetch_tables(cur, include_views: bool, include_mvs: bool):
    kinds = ["r", "p"]
    if include_views:
        kinds.append("v")
    if include_mvs:
        kinds.append("m")
    cur.execute(
        """
        SELECT n.nspname AS schema, c.relname AS name, c.relkind,
               obj_description(c.oid, 'pg_class') AS comment,
               pg_size_pretty(pg_relation_size(c.oid)) AS size_pretty,
               c.reltuples::BIGINT AS approx_rows
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relkind = ANY(%s)
        ORDER BY c.relname
        """,
        (kinds,),
    )
    return cur.fetchall()


def fetch_columns(cur, table_name: str):
    cur.execute(
        """
        SELECT a.attname AS name,
               format_type(a.atttypid, a.atttypmod) AS type,
               NOT a.attnotnull AS nullable,
               pg_get_expr(d.adbin, d.adrelid) AS default_expr,
               col_description(a.attrelid, a.attnum) AS comment
        FROM pg_attribute a
        LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
        WHERE a.attrelid = (SELECT oid FROM pg_class WHERE relname=%s AND relnamespace=(SELECT oid FROM pg_namespace WHERE nspname='public'))
          AND a.attnum > 0 AND NOT a.attisdropped
        ORDER BY a.attnum
        """,
        (table_name,),
    )
    return cur.fetchall()


def fetch_indexes(cur, table_name: str):
    cur.execute(
        """
        SELECT i.relname AS name, pg_get_indexdef(ix.indexrelid) AS definition,
               ix.indisunique AS is_unique, ix.indisprimary AS is_primary
        FROM pg_class t
        JOIN pg_index ix ON ix.indrelid = t.oid
        JOIN pg_class i ON i.oid = ix.indexrelid
        WHERE t.relname = %s
        ORDER BY i.relname
        """,
        (table_name,),
    )
    return cur.fetchall()


def fetch_foreign_keys(cur, table_name: str):
    cur.execute(
        """
        SELECT conname AS name,
               pg_get_constraintdef(c.oid) AS definition
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        WHERE t.relname = %s AND c.contype = 'f'
        ORDER BY conname
        """,
        (table_name,),
    )
    return cur.fetchall()


def fetch_checks(cur, table_name: str):
    cur.execute(
        """
        SELECT conname AS name, pg_get_constraintdef(c.oid) AS definition
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        WHERE t.relname = %s AND c.contype = 'c'
        ORDER BY conname
        """,
        (table_name,),
    )
    return cur.fetchall()


def fetch_functions(cur):
    cur.execute(
        """
        SELECT n.nspname AS schema, p.proname AS name,
               pg_get_function_arguments(p.oid) AS args,
               pg_get_function_result(p.oid) AS result,
               obj_description(p.oid, 'pg_proc') AS comment
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public'
          AND p.prokind = 'f'
          AND p.proname LIKE 'argus_%'
        ORDER BY p.proname
        """
    )
    return cur.fetchall()


def md_table_section(name: str, kind: str, comment: str, size: str, rows: int,
                     columns, indexes, fks, checks) -> str:
    kind_label = {"r": "table", "p": "partitioned", "v": "view", "m": "materialized view"}.get(kind, kind)
    lines = []
    anchor = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    lines.append(f"### {name}  <sub>({kind_label})</sub> <a id=\"{anchor}\"></a>")
    if comment:
        lines.append(f"\n> {comment}\n")
    lines.append(f"\n- approx rows: {rows or 0:,} · size: {size}")
    lines.append("")
    lines.append("| col | type | null | default | comment |")
    lines.append("|---|---|---|---|---|")
    for c in columns:
        col_name, col_type, nullable, default_expr, col_comment = c
        lines.append(
            f"| `{col_name}` | `{col_type}` | "
            f"{'yes' if nullable else 'no'} | "
            f"`{default_expr or ''}` | "
            f"{col_comment or ''} |"
        )
    if indexes:
        lines.append("\n**Indexes**:\n")
        for ix in indexes:
            name_, defn, uniq, primary = ix
            tag = "PK" if primary else ("UQ" if uniq else "IX")
            lines.append(f"- [{tag}] `{name_}` — `{defn}`")
    if fks:
        lines.append("\n**Foreign keys**:\n")
        for fk in fks:
            lines.append(f"- `{fk[0]}` → `{fk[1]}`")
    if checks:
        lines.append("\n**Checks**:\n")
        for ck in checks:
            lines.append(f"- `{ck[0]}` — `{ck[1]}`")
    lines.append("")
    return "\n".join(lines)


def render_index(grouped: dict[str, list[tuple[str, str]]]) -> str:
    out = ["## Índice por dominio\n"]
    for dom in sorted(grouped):
        out.append(f"### {dom}")
        for name, anchor in sorted(grouped[dom]):
            out.append(f"- [`{name}`](#{anchor})")
        out.append("")
    return "\n".join(out)


def main(argv: Iterable[str]) -> int:
    p = argparse.ArgumentParser(description="Auto-doc generator del schema Argus DB")
    p.add_argument("--dsn", default=os.environ.get("DATABASE_URL"))
    p.add_argument("--out", default="docs/db/auto-schema.md")
    p.add_argument("--include-views", action="store_true")
    p.add_argument("--include-mvs", action="store_true")
    p.add_argument("--include-functions", action="store_true")
    p.add_argument("--dry-run", action="store_true", help="No conectar; emite template")
    args = p.parse_args(list(argv))

    if args.dry_run or psycopg2 is None:
        if psycopg2 is None and not args.dry_run:
            print("WARNING: psycopg2 no instalado; usando --dry-run", file=sys.stderr)
        template = textwrap.dedent(f"""
            # Argus DB · auto-generated schema reference

            > Generated: {dt.datetime.utcnow().isoformat()}Z
            > Source: dry-run (psycopg2 no disponible o --dry-run)

            (Run real generation with DATABASE_URL set.)
            """).strip() + "\n"
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(template)
        print(f"[dry-run] wrote {args.out}")
        return 0

    if not args.dsn:
        print("ERROR: pasá --dsn o DATABASE_URL", file=sys.stderr)
        return 2

    print(f"[info] conectando a DSN (sanitizado: {re.sub(r'://[^@]+@', '://***@', args.dsn)})")
    conn = psycopg2.connect(args.dsn)
    try:
        conn.set_session(readonly=True, autocommit=True)
        with conn.cursor() as cur:
            tables = fetch_tables(cur, args.include_views, args.include_mvs)
            sections: list[str] = []
            grouped: dict[str, list[tuple[str, str]]] = defaultdict(list)
            for row in tables:
                schema, name, kind, comment, size, rows = row
                cols = fetch_columns(cur, name)
                idxs = fetch_indexes(cur, name)
                fks = fetch_foreign_keys(cur, name)
                chks = fetch_checks(cur, name)
                section = md_table_section(name, kind, comment, size, rows, cols, idxs, fks, chks)
                sections.append(section)
                dom = domain_of(name)
                anchor = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
                grouped[dom].append((name, anchor))

            fn_section = ""
            if args.include_functions:
                fns = fetch_functions(cur)
                if fns:
                    fn_section_lines = ["\n## Functions (argus_*)\n",
                                        "| name | args | returns | comment |",
                                        "|---|---|---|---|"]
                    for s, n, a, r, c in fns:
                        fn_section_lines.append(f"| `{n}` | `{a}` | `{r}` | {c or ''} |")
                    fn_section = "\n".join(fn_section_lines)

            header = textwrap.dedent(f"""
                # Argus DB · auto-generated schema reference

                > Generated: {dt.datetime.utcnow().isoformat()}Z
                > Source: live DB · `scripts/db/auto-doc/generate.py`

                Para hand-curated docs ver `schema-pack48.md` y `er-diagram.md`.
                Este archivo NO debe ser editado manualmente.
                """).strip() + "\n"

            content = "\n\n".join([
                header,
                render_index(grouped),
                "## Tablas\n",
                "\n".join(sections),
                fn_section,
            ])
            with open(args.out, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"[info] wrote {args.out} · {len(tables)} objetos")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
