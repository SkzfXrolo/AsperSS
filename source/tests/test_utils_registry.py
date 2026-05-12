from unittest import mock
import utils.registry as reg


def test_safe_open_key_returns_none_on_error():
    with mock.patch("utils.registry.winreg.OpenKey", side_effect=Exception("x")):
        assert reg.safe_open_key(None, "x") is None


def test_safe_read_value_default():
    with mock.patch("utils.registry.winreg.QueryValueEx", side_effect=Exception("x")):
        assert reg.safe_read_value(object(), "a", default="d") == "d"


def test_walk_subkeys_stops():
    with mock.patch("utils.registry.winreg.EnumKey", side_effect=[ "a", "b", OSError() ]):
        out = list(reg.walk_subkeys(object()))
    assert out == ["a", "b"]

