"""Flask 应用工厂：占位首页 + /api/health + Phase 2A /api/graph."""
from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
from typing import Any, Dict, Tuple

from flask import Flask, render_template, request

from ecfg.viz import build_graph
from ecfg.viz.const import (
    API_GRAPH_PATH,
    API_HEALTH_PATH,
    API_PATH_QUERY_KEY,
)


def create_app(config_path: str = "config.yaml") -> Flask:
    """构造 Flask app 并注入 ``config_path`` 供前端/健康检查展示。"""
    app = Flask(__name__)
    app.config["ECFG_CONFIG_PATH"] = str(Path(config_path))

    @app.get("/")
    def index() -> str:
        """渲染 Phase 2A 三栏画布（默认 yaml 目录由 query string ``path`` 指定）."""
        return render_template(
            "index.html",
            config_path=app.config["ECFG_CONFIG_PATH"],
            api_graph_path=API_GRAPH_PATH,
            api_path_query_key=API_PATH_QUERY_KEY,
        )

    @app.get(API_HEALTH_PATH)
    def health() -> Dict[str, Any]:
        """健康检查；附带当前加载的配置文件路径。"""
        return {
            "status": "ok",
            "phase": 2,
            "config": app.config["ECFG_CONFIG_PATH"],
        }

    @app.get(API_GRAPH_PATH)
    def graph() -> Tuple[Dict[str, Any], int]:
        """``GET /api/graph?path=<yaml_dir>`` → graph builder JSON.

        path 缺失或目录不存在 → 400。
        """
        yaml_dir = request.args.get(API_PATH_QUERY_KEY, "").strip()
        if not yaml_dir:
            return ({"error": f"missing required query string ``{API_PATH_QUERY_KEY}``"},
                    HTTPStatus.BAD_REQUEST)
        target = Path(yaml_dir)
        if not target.is_dir():
            return ({"error": f"yaml dir not found: {yaml_dir}"},
                    HTTPStatus.BAD_REQUEST)
        return build_graph(target), HTTPStatus.OK

    return app
