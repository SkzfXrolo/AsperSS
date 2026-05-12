from utils.encryption import encrypt_scan_result, decrypt_scan_result


def test_encrypt_decrypt_roundtrip():
    data = {"issues_found": [{"tipo": "x"}]}
    enc = encrypt_scan_result(data, "secret")
    dec = decrypt_scan_result(enc, "secret")
    assert dec == data


def test_encrypt_returns_bytes():
    enc = encrypt_scan_result({"a": 1}, "secret")
    assert isinstance(enc, (bytes, bytearray))


def test_wrong_password_fails():
    enc = encrypt_scan_result({"a": 1}, "secret")
    failed = False
    try:
        decrypt_scan_result(enc, "bad")
    except Exception:
        failed = True
    assert failed

