from __future__ import annotations

from locust import HttpUser, between, task


class NormalTrafficUser(HttpUser):
    wait_time = between(1, 2)

    @task
    def normal_browse(self):
        self.client.get("/health")
        self.client.get("/api/version")
