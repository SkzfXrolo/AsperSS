from unittest import mock
from integrations.argus_web import send_scan_to_argus_web


class _Resp:
    def __init__(self):
        self.status_code = 200
        self.ok = True
        self.text = "ok"


@mock.patch("integrations.argus_web.requests.post", return_value=_Resp())
def test_argus_web_submit(mock_post):
    out = send_scan_to_argus_web("https://argus.local", {"issues_found": []}, token="x")
    assert out["ok"] is True

