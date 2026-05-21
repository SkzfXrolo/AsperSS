from config.hack_signatures import (
    mod_blacklist_match,
    stem_in_filename,
    filename_is_definite_hack,
    combined_path_indicates_hack,
)


def test_mod_blacklist_vape():
    assert mod_blacklist_match("vape-4.0.jar") == "vape"


def test_mod_blacklist_no_substring_cheatengine():
    assert mod_blacklist_match("recheat-mod.jar") is None


def test_impactclient_not_bare_impact():
    assert mod_blacklist_match("impactapi-1.0.jar") is None
    assert mod_blacklist_match("impactclient-1.0.jar") == "impactclient"


def test_definite_hack_in_mods():
    assert filename_is_definite_hack("vape.jar") is True
    assert filename_is_definite_hack("sodium-0.5.jar") is False


def test_stem_boundary():
    assert stem_in_filename("vape", "my-vape-client.jar")
    assert not stem_in_filename("vape", "avaporware.jar")


def test_vape_inject_stems():
    assert mod_blacklist_match("vape-inject.dll") in ("vape", "vape-inject")
    assert mod_blacklist_match("vapeinject.jar") in ("vape", "vapeinject")


def test_combined_path_vape_inject():
    assert combined_path_indicates_hack(
        "loader.dll",
        r"C:\Users\x\AppData\Roaming\.vape\inject\loader.dll",
        r"C:\Users\x\AppData\Roaming\.vape\inject\loader.dll",
    )
    assert not combined_path_indicates_hack("sodium.jar", r"C:\mods\sodium.jar", "sodium.jar")
