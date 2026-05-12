from config.loader import load_config


def test_load_config_default():
    out = load_config(None)
    assert "profile" in out

