"""Phase 2A Flask `/api/graph` 端点测试 — 覆盖 happy path + 4xx 兜底."""
from __future__ import annotations

from pathlib import Path

import pytest

from ecfg.app import create_app

FIXTURES = Path(__file__).parent / "fixtures" / "xml" / "valid"


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


class TestGraphEndpoint:
    def test_happy_path_returns_graph_json(self, client):
        resp = client.get("/api/graph", query_string={"path": str(FIXTURES / "minimal.expected")})
        assert resp.status_code == 200
        body = resp.get_json()
        assert set(body.keys()) == {"meta", "nodes", "edges", "referenced_by"}
        assert body["meta"]["node_count"] > 0

    def test_missing_path_returns_400(self, client):
        resp = client.get("/api/graph")
        assert resp.status_code == 400
        assert "path" in resp.get_json()["error"]

    def test_nonexistent_dir_returns_400(self, client):
        resp = client.get("/api/graph", query_string={"path": "/no/such/dir"})
        assert resp.status_code == 400
        assert "not found" in resp.get_json()["error"]

    def test_multi_runmode_categories(self, client):
        path = str(FIXTURES / "multi_runmode.expected")
        resp = client.get("/api/graph", query_string={"path": path})
        assert resp.status_code == 200
        body = resp.get_json()
        cats = set(body["meta"]["categories"])
        assert {"shared", "0x10000000", "0x20000000"} <= cats


class TestHealthEndpoint:
    def test_health_reports_phase_2(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] == "ok"
        assert body["phase"] == 2
