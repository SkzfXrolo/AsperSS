"""
Test del endpoint en vivo via session login.
Necesita un user/pass valido. Aprovechamos el sistema admin/owner que tiene robin.
Si no tenemos creds, este script imprime que no las tiene y skip.
"""
import os
import sys
import psycopg2
import requests
import json
from psycopg2.extras import RealDictCursor

DB_URL = "postgresql://aspers_db_user:zgwgt9YCincIkxmwrBKOIUpg3PHMPTIO@dpg-d7g3iobeo5us73bfrv10-a.oregon-postgres.render.com/aspers_db"
BASE = "https://asperss.onrender.com"

# Probar endpoint debug PUBLICO para verificar que el deploy esta vivo
print("=" * 80)
print("  GET /api/debug/scan/96 (publico, sin login)")
print("=" * 80)
r = requests.get(f"{BASE}/api/debug/scan/96", timeout=15)
print(f"  status={r.status_code}")
print(f"  body={r.text[:600]}")
print()

print("=" * 80)
print("  GET /api/debug/scan/95")
print("=" * 80)
r = requests.get(f"{BASE}/api/debug/scan/95", timeout=15)
print(f"  status={r.status_code}")
print(f"  body={r.text[:600]}")
print()

print("=" * 80)
print("  GET /api/debug/scan/94")
print("=" * 80)
r = requests.get(f"{BASE}/api/debug/scan/94", timeout=15)
print(f"  status={r.status_code}")
print(f"  body={r.text[:600]}")
print()

# Test sin login al endpoint protegido — esperamos 401 con JSON
print("=" * 80)
print("  GET /api/scans/96 (login_required)")
print("=" * 80)
r = requests.get(f"{BASE}/api/scans/96",
                 headers={'Accept': 'application/json'},
                 timeout=15,
                 allow_redirects=False)
print(f"  status={r.status_code}")
print(f"  ct={r.headers.get('Content-Type', 'n/a')}")
print(f"  body={r.text[:400]}")
