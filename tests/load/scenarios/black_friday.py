from __future__ import annotations

from locust import HttpUser, between, task


class BlackFridayUser(HttpUser):
    wait_time = between(0, 1)

    @task(3)
    def heavy_mix(self):
        self.client.get("/health")
        self.client.get("/api/version")
        self.client.post("/api/plugin/ai-evaluate", json={})
