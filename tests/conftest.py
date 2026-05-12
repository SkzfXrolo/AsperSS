from __future__ import annotations

import math
import random
import sqlite3
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
WEB_APP = ROOT / "web_app"
if str(WEB_APP) not in sys.path:
    sys.path.insert(0, str(WEB_APP))


@pytest.fixture(autouse=True)
def _deterministic_random():
    random.seed(12345)


@pytest.fixture
def flask_app():
    from web_app.app import app

    app.config.update(TESTING=True)
    return app


@pytest.fixture
def client(flask_app):
    return flask_app.test_client()


@pytest.fixture
def login_session(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["username"] = "tester"
        sess["roles"] = ["administrador"]
        sess["company_id"] = 1
    return client


@pytest.fixture
def mock_db():
    conn = sqlite3.connect(":memory:")
    yield conn
    conn.close()


@pytest.fixture
def sample_evidence():
    return {
        "violations": [
            {"check_name": "reach", "level": "MID", "age_seconds": 20},
            {"check_name": "killaura_no_swing", "level": "HIGH", "age_seconds": 5},
        ],
        "account_age_hours": 12,
        "playtime_hours": 8,
        "prior_clean_scans": 0,
        "scan_detected_hacks_recent": False,
        "reports_in_chat": 1,
        "first_seen_now": True,
        "current_score": 0.1,
        "last_evaluated_at_age_seconds": 60,
        "avg_cps": 12.0,
        "cps_variance": 1.2,
        "avg_reach": 3.4,
        "reach_max": 4.1,
        "hit_accept_rate": 0.8,
        "yaw_stability_extreme": False,
        "pitch_stability_extreme": False,
        "movement_jitter": 0.2,
        "session_length_hours": 2.0,
        "scan_count_total": 2,
        "scan_count_clean": 2,
        "scan_count_positive": 0,
        "cross_server_violations": 0,
        "cross_server_clean_streak": 30,
        "is_first_time_in_argus_network": False,
        "heuristic_score": 0.3,
    }


@pytest.fixture
def sample_feature_vector():
    return [0.1, 0.8, 0.0, 0.4, 0.2, 0.3]


@pytest.fixture
def weird_evidence():
    return {
        "violations": [
            {"check_name": "unknown_check", "level": "WHAT", "age_seconds": -10},
            {"check_name": "", "level": None, "age_seconds": 10**9},
        ],
        "account_age_hours": -1,
        "playtime_hours": float("inf"),
        "current_score": math.nan,
        "reports_in_chat": -99,
    }
