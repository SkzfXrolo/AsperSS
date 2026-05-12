from __future__ import annotations

from locust import HttpUser, between, task


class ArgusUser(HttpUser):
    wait_time = between(1, 3)

    @task(3)
    def browse_panel(self):
        self.client.get("/")
        self.client.get("/health")

    @task(2)
    def api_version(self):
        self.client.get("/api/version")

    @task(1)
    def oracle_eval(self):
        self.client.post("/api/plugin/ai-evaluate", json={})
