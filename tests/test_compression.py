import gzip

from flask import Flask, Response, jsonify

from compression import init_compression


def _make_app(tmp_path):
    static = tmp_path / "static"
    static.mkdir()
    (static / "app.js").write_text("console.log('argus');\n" * 200)
    app = Flask(__name__, static_folder=str(static))
    init_compression(app)

    @app.route("/big")
    def big():
        return jsonify(items=["x" * 50] * 100)

    @app.route("/small")
    def small():
        return jsonify(ok=True)

    @app.route("/stream")
    def stream():
        return Response((c for c in ["data: a\n\n"] * 200), mimetype="text/event-stream")

    return app


def test_json_is_gzipped_when_accepted(tmp_path):
    c = _make_app(tmp_path).test_client()
    r = c.get("/big", headers={"Accept-Encoding": "gzip"})
    assert r.headers["Content-Encoding"] == "gzip"
    assert "Accept-Encoding" in r.headers["Vary"]
    assert b'"items"' in gzip.decompress(r.get_data())


def test_no_gzip_without_accept_or_when_small(tmp_path):
    c = _make_app(tmp_path).test_client()
    assert "Content-Encoding" not in c.get("/big").headers
    assert "Content-Encoding" not in c.get("/small", headers={"Accept-Encoding": "gzip"}).headers


def test_streams_are_untouched(tmp_path):
    c = _make_app(tmp_path).test_client()
    r = c.get("/stream", headers={"Accept-Encoding": "gzip"})
    assert "Content-Encoding" not in r.headers


def test_static_gzip_and_conditional_requests(tmp_path):
    c = _make_app(tmp_path).test_client()
    r = c.get("/static/app.js?v=3", headers={"Accept-Encoding": "gzip"})
    assert r.status_code == 200
    assert r.headers["Content-Encoding"] == "gzip"
    assert "immutable" in r.headers["Cache-Control"]
    assert gzip.decompress(r.get_data()) == (tmp_path / "static" / "app.js").read_bytes()
    etag = r.headers["ETag"]
    r.close()
    r2 = c.get("/static/app.js", headers={"Accept-Encoding": "gzip", "If-None-Match": etag})
    assert r2.status_code == 304


def test_static_range_requests_are_not_compressed(tmp_path):
    c = _make_app(tmp_path).test_client()
    r = c.get("/static/app.js", headers={"Accept-Encoding": "gzip", "Range": "bytes=0-9"})
    assert r.status_code == 206
    assert "Content-Encoding" not in r.headers
    assert len(r.get_data()) == 10
    r.close()
