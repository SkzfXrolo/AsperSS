"""ARGUS_LOCAL_SCAN=1 promete no subir nada: el config en memoria no puede traer token ni licencia."""


def test_local_scan_blanks_token(monkeypatch):
    from main import ArgusApp

    app = object.__new__(ArgusApp)
    app._load_config_from_disk = lambda: {'scan_token': 'REAL-TOKEN', 'license': 'LIC', 'api_url': 'x'}

    monkeypatch.setenv('ARGUS_LOCAL_SCAN', '1')
    cfg = app.load_config()
    assert cfg['scan_token'] == '' and cfg['license'] == '' and cfg['api_url'] == 'x'

    monkeypatch.delenv('ARGUS_LOCAL_SCAN')
    assert app.load_config()['scan_token'] == 'REAL-TOKEN'
