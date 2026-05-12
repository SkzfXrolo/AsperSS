import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
OUT = ROOT / "static" / "openapi.json"


def parse_routes(text: str):
    routes = []
    pattern = re.compile(
        r"@app\.route\('([^']+)'(?:,\s*methods=\[([^\]]+)\])?\)\s*\n(?:@[^\n]+\n)*def\s+([a-zA-Z0-9_]+)\(",
        re.MULTILINE,
    )
    for m in pattern.finditer(text):
        path = m.group(1)
        methods_raw = m.group(2)
        fn = m.group(3)
        if methods_raw:
            methods = [x.strip().strip("'\"").lower() for x in methods_raw.split(",")]
        else:
            methods = ["get"]
        routes.append((path, methods, fn))
    return routes


def build_spec(routes):
    paths = {}
    for path, methods, fn in routes:
        p = paths.setdefault(path, {})
        for method in methods:
            p[method] = {
                "summary": fn.replace("_", " "),
                "responses": {
                    "200": {"description": "OK"},
                    "400": {"description": "Bad Request"},
                    "401": {"description": "Unauthorized"},
                    "500": {"description": "Server Error"},
                },
            }
    return {
        "openapi": "3.0.3",
        "info": {"title": "Argus Web API", "version": "1.0.0"},
        "paths": paths,
    }


def main():
    text = APP.read_text(encoding="utf-8", errors="ignore")
    routes = parse_routes(text)
    spec = build_spec(routes)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"generated {OUT} with {len(routes)} routes")


if __name__ == "__main__":
    main()
