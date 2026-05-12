from __future__ import annotations

import pytest

from web_app.app import app


@pytest.fixture
def flask_app():
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
