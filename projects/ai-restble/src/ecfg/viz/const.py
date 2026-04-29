"""Phase 2A 可视化协议常量.

按职责分两大类：

- **Graph JSON 契约**：``build_graph()`` 输出的 JSON 字段名 + 枚举值，由
  ``prompts/phase2/01-graph-builder.md`` 描述。前端 ECharts 渲染层和未来 2A.2
  edge 投影 都按此契约消费。
- **Flask API 契约**：``/api/graph`` 等路由 + query key，前端 ``index.html`` 与
  ``app.py`` 共享单一来源（路径变更只改本模块）。

注：record 三区域名（``index``/``attribute``/``ref``）复用 ``schema.const.REGION_*``，
不在本模块重复定义；EDGE_* 子字段（``from``/``to``/``ref_name`` 等）当前 Python 端
无 consumer（边投影留 2A.2），protocol 由 prompt + 前端字面承载，不在此处占位。
"""
from __future__ import annotations

from ecfg.legacy.const import ROOT_TAG

# ═════════════════════════════════════════════════════════════════
#   Graph JSON 契约 — build_graph() 输出 JSON schema
# ═════════════════════════════════════════════════════════════════

# ─── 顶层 keys ──────────────────────────────────────────────────
META_KEY = "meta"
NODES_KEY = "nodes"
EDGES_KEY = "edges"
REFERENCED_BY_KEY = "referenced_by"

# ─── meta 子字段 ─────────────────────────────────────────────────
META_YAML_DIR = "yaml_dir"
META_CATEGORIES = "categories"
META_NODE_COUNT = "node_count"
META_EDGE_COUNT = "edge_count"

# ─── node 子字段 ─────────────────────────────────────────────────
NODE_ID = "id"
NODE_KIND = "kind"
NODE_SCOPE = "scope"
NODE_CATEGORY = "category"
NODE_ELEMENT = "element"
NODE_WRAPPER_TYPE = "wrapper_type"
NODE_FIELDS = "fields"
NODE_RECORDS_PREVIEW = "records_preview"
NODE_RECORDS = "records"
NODE_TABLE_ATTRIBUTES = "table_attributes"

# ─── node.fields[i] 子结构 ──────────────────────────────────────
FIELD_NAME = "name"
FIELD_REGION = "region"
# 来自 template/<scope>/<E>.yaml 的字段约束（@merge / @range / @enum），缺则省略.
FIELD_CONSTRAINTS = "constraints"

# ─── 校验产物（template 约束 vs 实际 record 值） ─────────────────
# record-level：违反约束时挂在 records[i].errors，list of {field, region, kind, message}
RECORD_ERRORS = "errors"
# node-level：本表所有 records 的错误总数，0 = 无异常；前端按此着色
NODE_ERROR_COUNT = "error_count"
# error 子结构 keys
ERR_FIELD = "field"
ERR_REGION = "region"
ERR_KIND = "kind"
ERR_MESSAGE = "message"
# error.kind 枚举
ERR_KIND_ENUM_MISMATCH = "enum_mismatch"
ERR_KIND_RANGE_VIOLATION = "range_violation"

# ─── node.kind 枚举 ─────────────────────────────────────────────
KIND_TABLE = "Table"
# FileInfo 节点的 kind 字面与 XML 根 element 同名，靠 ROOT_TAG 单一来源同步。
KIND_FILEINFO = ROOT_TAG

# ─── 默认值 ─────────────────────────────────────────────────────
# 无 RunMode 子目录时所有节点的占位 scope / category 值。
DEFAULT_SCOPE = "root"


# ═════════════════════════════════════════════════════════════════
#   Flask API 契约 — 路由 + query key（前后端单一来源）
# ═════════════════════════════════════════════════════════════════

API_GRAPH_PATH = "/api/graph"
API_HEALTH_PATH = "/api/health"
API_PATH_QUERY_KEY = "path"
