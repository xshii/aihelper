"""yaml 目录 → 框架无关 graph JSON（供前端 ECharts 渲染）。

公开 API：``build_graph(yaml_dir) -> dict``。详情见 ``graph.py`` 与
``prompts/phase2/01-graph-builder.md`` 协议契约。
"""
from ecfg.viz.graph import build_graph as build_graph  # noqa: F401
