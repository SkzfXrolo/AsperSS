from locust import HttpUser, task, between


class ArgusUser(HttpUser):
    wait_time = between(1, 4)

    @task(50)
    def panel_browse(self):
        self.client.get("/panel", name="GET /panel")
        self.client.get("/api/scans?limit=20", name="GET /api/scans")
        self.client.get("/api/statistics", name="GET /api/statistics")

    @task(30)
    def api_scans(self):
        self.client.get("/api/scans?limit=50", name="GET /api/scans?limit=50")
        self.client.get("/api/dashboard/extended", name="GET /api/dashboard/extended")

    @task(15)
    def oracle_eval(self):
        payload = {
            "player_uuid": "00000000-0000-0000-0000-000000000001",
            "player_name": "bench_player",
            "plugin_action": "watch",
            "violation": {"check_name": "reach_packet", "level": "MID", "details": "locust synthetic"},
        }
        self.client.post("/api/plugin/ai-evaluate", json=payload, name="POST /api/plugin/ai-evaluate", catch_response=True)

    @task(5)
    def scan_submit(self):
        payload = {
            "scan_token": "bench-token",
            "machine_name": "bench-host",
            "results": [],
        }
        self.client.post("/api/scans", json=payload, name="POST /api/scans", catch_response=True)
