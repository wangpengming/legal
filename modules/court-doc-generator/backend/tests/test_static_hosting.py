"""生产形态静态托管测试：FastAPI 挂载前端 dist + SPA fallback + 防路径穿越。"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import mount_frontend_static


def _make_dist(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>SPA App</html>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (dist / "favicon.ico").write_bytes(b"\x00\x01")
    return dist


def _client(dist: Path) -> TestClient:
    app = FastAPI()
    assert mount_frontend_static(app, dist) is True
    return TestClient(app)


class TestMountStatic:
    def test_dist_missing_returns_false(self, tmp_path):
        app = FastAPI()
        assert mount_frontend_static(app, tmp_path / "no-dist") is False

    def test_root_serves_index(self, tmp_path):
        r = _client(_make_dist(tmp_path)).get("/")
        assert r.status_code == 200
        assert "SPA App" in r.text

    def test_real_file_served(self, tmp_path):
        r = _client(_make_dist(tmp_path)).get("/favicon.ico")
        assert r.status_code == 200
        assert r.content == b"\x00\x01"

    def test_assets_mounted(self, tmp_path):
        r = _client(_make_dist(tmp_path)).get("/assets/app.js")
        assert r.status_code == 200
        assert r.text == "console.log(1)"

    def test_unknown_path_falls_back_to_index(self, tmp_path):
        r = _client(_make_dist(tmp_path)).get("/some/spa/route")
        assert r.status_code == 200
        assert "SPA App" in r.text

    def test_missing_asset_returns_404(self, tmp_path):
        """assets 前缀被 StaticFiles mount 优先拦截：缺失文件 404，不回退 index
        （mount 命中即不再进入 SPA catch-all，这是预期行为）。"""
        r = _client(_make_dist(tmp_path)).get("/assets/nope.js")
        assert r.status_code == 404

    def test_api_prefix_rejected(self, tmp_path):
        r = _client(_make_dist(tmp_path)).get("/api/v1/cases")
        assert r.status_code == 404

    def test_path_traversal_blocked(self, tmp_path):
        secret = tmp_path / "secret.txt"
        secret.write_text("TOP SECRET", encoding="utf-8")
        c = _client(_make_dist(tmp_path))
        # URL 编码的 ../ 绕过客户端归一化，验证服务端 resolve 防护
        r = c.get("/..%2fsecret.txt")
        assert r.status_code == 200
        assert "TOP SECRET" not in r.text, "越界文件内容不得泄露，应回退 index.html"