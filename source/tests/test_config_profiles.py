from config.profiles import get_profile


def test_profiles_known():
    assert get_profile("quick")["threads"] >= 1
    assert get_profile("paranoid")["timeout_sec"] >= get_profile("full")["timeout_sec"]

