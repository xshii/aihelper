"""Flask 应用工厂：Phase 0 占位画布 + /api/health。"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from flask import Flask, render_template


def create_app(config_path: str = "config.yaml") -> Flask:
    """构造 Flask app 并注入 ``config_path`` 供前端/健康检查展示。"""
    app = Flask(__name__)
    app.config["ECFG_CONFIG_PATH"] = str(Path(config_path))

    @app.get("/")
    def index() -> str:
        """渲染 Bootstrap 占位画布。"""
        return render_template(
            "index.html",
            config_path=app.config["ECFG_CONFIG_PATH"],
        )

    @app.get("/api/health")
    def health() -> Dict[str, Any]:
        """健康检查；附带当前加载的配置文件路径。"""
        return {
            "status": "ok",
            "phase": 0,
            "config": app.config["ECFG_CONFIG_PATH"],
        }

    return app
