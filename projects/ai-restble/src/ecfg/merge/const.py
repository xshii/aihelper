"""Merge 引擎常量 — 6 种 merge op 名 + 默认 rule.

由 ``docs/merge-spec.md`` 描述的 ``@merge:<op>`` 协议固定，**非用户可配置**。
"""
from __future__ import annotations

# ─── 6 种 merge op 名（与 yaml 中 @merge:<op> 的字面值一致） ─────────
OP_CONCAT = "concat"     # @merge:concat(',') — 拼接，需带带引号的分隔符
OP_SUM = "sum"           # @merge:sum — 数值求和
OP_MAX = "max"           # @merge:max — 取最大
OP_MIN = "min"           # @merge:min — 取最小
OP_UNION = "union"       # @merge:union — 集合并去重保序
OP_CONFLICT = "conflict" # @merge:conflict — 字段必须等值，否则 raise

# ref 区字段缺省 merge 规则：必须等值（多 record 不一致即 raise）。
# 业务语义：ref 是 FK 链路，不允许"自动合并"歧义引用。
REF_DEFAULT_MERGE_RULE = OP_CONFLICT
