"""Tests para pruning y rutas de escaneo."""
from config.scan_paths import (
    filter_relevant_files,
    max_depth_for_root,
    prune_walk_dirs,
    should_skip_dir,
)


def test_skip_exact_node_modules():
    assert should_skip_dir(r'C:\proj', 'node_modules') is True


def test_do_not_skip_temp_in_downloads():
    assert should_skip_dir(r'C:\Users\x\Downloads\temp', 'cache') is False


def test_skip_temp_in_random_appdata():
    assert should_skip_dir(r'C:\Users\x\AppData\Local\SomeApp', 'temp') is True


def test_skip_minecraft_libraries():
    assert should_skip_dir(r'C:\Users\x\AppData\Roaming\.minecraft', 'libraries') is True


def test_keep_minecraft_mods():
    assert should_skip_dir(r'C:\Users\x\AppData\Roaming\.minecraft', 'mods') is False


def test_filter_extensions():
    files = ['a.jar', 'b.png', 'c.exe', 'readme']
    assert filter_relevant_files(files) == ['a.jar', 'c.exe']


def test_prune_walk_dirs():
    dirs = ['mods', 'node_modules', 'config', 'libraries']
    prune_walk_dirs(r'C:\Users\x\.minecraft', dirs)
    assert 'mods' in dirs and 'config' in dirs
    assert 'node_modules' not in dirs and 'libraries' not in dirs


def test_depth_mc_higher():
    assert max_depth_for_root(r'C:\Users\x\AppData\Roaming\.minecraft') >= 8
