from __future__ import annotations

from locust import HttpUser, between, task


class SpikeUser(HttpUser):
    wait_time = between(0, 1)

    @task
    def spike_hit(self):
        self.client.get("/health")
