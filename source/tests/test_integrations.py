from unittest import mock
from integrations.misp import submit_to_misp
from integrations.wazuh import send_to_wazuh
from integrations.splunk_hec import send_to_splunk_hec


class _Resp:
    def __init__(self, code=200, txt="ok"):
        self.status_code = code
        self.ok = code < 400
        self.text = txt


@mock.patch("integrations.misp.requests.post", return_value=_Resp())
def test_misp_submit(mock_post):
    out = submit_to_misp({"issues_found": []}, "https://misp.local", "k")
    assert out["ok"] is True


@mock.patch("integrations.wazuh.requests.post", return_value=_Resp())
def test_wazuh_submit(mock_post):
    out = send_to_wazuh({"issues_found": []}, "https://wazuh.local", "t")
    assert out["ok"] is True


@mock.patch("integrations.splunk_hec.requests.post", return_value=_Resp())
def test_splunk_submit(mock_post):
    out = send_to_splunk_hec({"issues_found": []}, "https://splunk.local/hec", "t")
    assert out["ok"] is True

