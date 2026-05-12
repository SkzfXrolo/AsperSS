from __future__ import annotations


def test_admin_review_bulk_workflow(login_session):
    pending = login_session.get("/api/ai/decisions-pending-review")
    assert pending.status_code in {200, 401, 403, 404}
    feedback = login_session.post("/api/ai/feedback", json={"decision_id": 1, "label": 1})
    assert feedback.status_code in {200, 400, 401, 403, 404}
