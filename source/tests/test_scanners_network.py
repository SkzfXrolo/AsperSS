from scanners import network_artifacts as na


def test_scan_network_state_keys():
    out = na.scan_network_state()
    assert "arp_entries" in out
    assert "routes" in out


def test_parse_arp_with_mock(monkeypatch):
    monkeypatch.setattr(na, "_run", lambda cmd: "  10.0.0.1 aa-bb-cc dynamic" if cmd[0] == "arp" else "")
    out = na.scan_network_state()
    assert len(out["arp_entries"]) == 1


def test_parse_routes_with_mock(monkeypatch):
    monkeypatch.setattr(na, "_run", lambda cmd: "0.0.0.0 0.0.0.0 192.168.1.1" if cmd[0] == "route" else "")
    out = na.scan_network_state()
    assert len(out["routes"]) >= 1


def test_parse_netstat_listen(monkeypatch):
    monkeypatch.setattr(na, "_run", lambda cmd: "TCP 0.0.0.0:80 0.0.0.0:0 LISTENING 1234" if cmd[0] == "netstat" else "")
    out = na.scan_network_state()
    assert len(out["listening_ports"]) == 1


def test_blocklist_detection(monkeypatch):
    monkeypatch.setattr(na, "_run", lambda cmd: "TCP 10.0.0.2:50000 45.9.148.108:443 ESTABLISHED 1111" if cmd[0] == "netstat" else "")
    out = na.scan_network_state()
    assert len(out["suspicious_connections"]) == 1

