from scanner_integrations import results_to_issues


def test_dns_hosts_minecraft_redirect():
    raw = {
        "dns_artifacts": {
            "ok": True,
            "result": {
                "hosts_entries": ["127.0.0.1 play.hypixel.net"],
                "dns_cache": [],
                "doh_dot_anomalies": [],
            },
        }
    }
    issues = results_to_issues(raw)
    assert len(issues) == 1
    assert issues[0]["tipo"] == "hosts_minecraft_redirect"
    assert issues[0]["alerta"] == "CRITICAL"


def test_registry_hack_client_critical():
    raw = {
        "registry_anomalies": {
            "ok": True,
            "result": [
                {
                    "key": r"Software\Run",
                    "name": "Loader",
                    "value": r"C:\Users\x\Downloads\vape.exe",
                    "reason": "hack_client_reference",
                },
            ],
        }
    }
    issues = results_to_issues(raw)
    assert issues[0]["alerta"] == "CRITICAL"


def test_registry_anomalies_list():
    raw = {
        "registry_anomalies": {
            "ok": True,
            "result": [
                {"key": r"Software\Run", "name": "Updater", "value": r"%TEMP%\evil.exe", "reason": "suspicious_value"},
            ],
        }
    }
    issues = results_to_issues(raw)
    assert len(issues) == 1
    assert issues[0]["tipo"] == "registry_anomaly_modular"


def test_wmi_nonempty():
    raw = {
        "wmi_subscriptions": {
            "ok": True,
            "result": {"filters": "Name=foo", "consumers": "", "bindings": ""},
        }
    }
    issues = results_to_issues(raw)
    assert len(issues) == 1
    assert issues[0]["tipo"] == "wmi_persistence_modular"
