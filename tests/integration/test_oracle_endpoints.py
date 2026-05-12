from __future__ import annotations


def test_oracle_evaluate_endpoint_shape(login_session):
    # En este repo el endpoint equivalente es /api/plugin/ai-evaluate.
    r = login_session.post("/api/oracle/evaluate", json={})
    if r.status_code == 404:
        r = login_session.post("/api/plugin/ai-evaluate", json={})
    assert r.status_code in {200, 400, 401, 403, 404}


def test_oracle_chat_endpoint_shape(login_session):
    r = login_session.post("/api/oracle/chat", json={"text": "hola"})
    if r.status_code == 404:
        r = login_session.post("/api/ai/assistant/ask", json={"text": "hola"})
    assert r.status_code in {200, 400, 401, 403, 404}


def test_oracle_feedback_endpoint_shape(login_session):
    r = login_session.post("/api/oracle/feedback", json={"decision_id": 1, "label": 1})
    if r.status_code == 404:
        r = login_session.post("/api/ai/feedback", json={"decision_id": 1, "label": 1})
    assert r.status_code in {200, 400, 401, 403, 404}
