from __future__ import annotations

from locust import HttpUser, between, task


class SoakUser(HttpUser):
    wait_time = between(1, 3)

    @task
    def soak_path(self):
        self.client.get("/")
        self.client.get("/api/version")
