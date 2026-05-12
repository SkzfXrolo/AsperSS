from __future__ import annotations

from flask import Blueprint, jsonify

api_v2 = Blueprint("api_v2", __name__, url_prefix="/api/v2")


@api_v2.get("/health")
def v2_health():
    return jsonify({"ok": True, "api_version": "v2"}), 200


@api_v2.get("/meta")
def v2_meta():
    return jsonify({
        "api_version": "v2",
        "status": "beta",
        "errors": {"format": {"error": {"code": "string", "message": "string"}}},
    }), 200
