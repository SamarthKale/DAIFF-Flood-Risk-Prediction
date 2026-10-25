from fastapi.testclient import TestClient

from daiff.api.app import create_app


def test_serves_built_dashboard_with_spa_fallback(api_env, tmp_path):
    cfg, _, ref = api_env
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>DAIFF</html>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    c = TestClient(create_app(cfg, reference_dir=ref, web_dist=dist))
    assert "DAIFF" in c.get("/").text
    assert "DAIFF" in c.get("/subbasins").text  # client-side route
    assert c.get("/assets/app.js").text == "console.log(1)"
    assert c.get("/api/meta").json()["project"] == "synthetic"
    assert c.get("/api/nope").status_code == 404


def test_without_dist_only_api(api_env, tmp_path):
    cfg, _, ref = api_env
    c = TestClient(create_app(cfg, reference_dir=ref, web_dist=tmp_path / "missing"))
    assert c.get("/").status_code == 404
