from unittest import mock

from integrations.virustotal import vt_check_hash


class _Resp:
    status_code = 200
    headers = {"content-type": "application/json"}
    def json(self): return {"data": {"id": "x"}}


@mock.patch("integrations.virustotal.requests.get", return_value=_Resp())
@mock.patch("integrations.virustotal.os.environ.get", return_value="k")
def test_vt_hash(mock_env, mock_get):
    out = vt_check_hash("a" * 64)
    assert out["status_code"] == 200

