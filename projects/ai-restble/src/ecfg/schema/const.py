"""Schema 协议常量 — record 三区域名 / annotation key / TEMPLATE 块 marker.

由 ``docs/merge-spec.md`` §2.3 描述的 yaml schema 协议固定，**非用户可配置**。
集中此处避免散落到 ``loader.py`` 的多个 if-elif 分支。

注：``Region = Literal["index", "attribute", "ref"]`` 仍写在 ``model.py``
（Python ``Literal`` 不接受 alias，必须字面），常量仅服务于 **运行期比较**。
"""
from __future__ import annotations

# ─── Record 三区域 ────────────────────────────────────────────────
# 索引字段（合并时不参与，作为 record 主键定位）：``index: {key1: ..., key2: ...}``
REGION_INDEX = "index"
# 普通属性字段（参与 merge，可挂 @range/@enum/@merge 注解）：``attribute: {f: ...}``
REGION_ATTRIBUTE = "attribute"
# 引用字段（值为 list-of-mappings，子字段挂 FK 注解 ``Module.col``）：``ref: {refName: [...]}``
REGION_REF = "ref"

# ─── Annotation keys（``@<key>:<value>`` 中的 key 部分） ─────────────
ANNOT_KEY_MERGE = "merge"       # @merge:concat(',') / sum / conflict ...
ANNOT_KEY_RANGE = "range"       # @range:0-15
ANNOT_KEY_ENUM = "enum"         # @enum:a,b,c
ANNOT_KEY_INDEX = "index"       # @index:repeatable

# ─── Annotation 特定 value ─────────────────────────────────────────
# ``@index:`` 当前**仅**接受此值；其他值即 raise（不静默 fallback）。
ANNOT_INDEX_REPEATABLE = "repeatable"

# ─── TEMPLATE 块 marker（merge-spec.md §2.3） ─────────────────────
# 包裹 yaml 文件首部的 schema 占位 record；行间需以 ``# `` 开头。
TEMPLATE_BEGIN = "# ----- TEMPLATE BEGIN -----"
TEMPLATE_END = "# ----- TEMPLATE END -----"
