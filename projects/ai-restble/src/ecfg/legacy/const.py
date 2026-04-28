"""Legacy XML 协议常量 — element / attribute / 文件名 / 文件夹 / 注解 token / 值正则.

这些是 ``docs/yaml-schema.md`` 描述的 legacy XML 协议**固定契约**，**非用户可配置**。
任何一项变了 round-trip 立刻断。集中此处避免散落到 pre/postprocess 的 if 分支。
"""
from __future__ import annotations

import re

# ─── XML element tags ─────────────────────────────────────────────
# 文档根：``<FileInfo .../>``，所有 yaml 文件挂在它下面。
ROOT_TAG = "FileInfo"
# 通用 wrapper：``<ResTbl FooTbl="FooTbl" LineNum="N">...</ResTbl>``
# type-attr name = stem 去 variant；value = stem 全名。
WRAPPER_TAG = "ResTbl"
# 空 wrapper 默认子元素 tag：``<ResTbl FooTbl="FooTbl" LineNum="0"/>`` 时无 children，
# emit 时 LineNum=0；解析时若需要重建 ``@related:count(<X>)`` 注解，X 兜底取此。
DEFAULT_CHILD_TAG = "Line"
# scope 定义元素：``<RunModeTbl RunMode="0x..." ...>``，存在即激活 RunMode 维度
# （触发 ``shared/`` + ``<RunMode>/`` 子目录布局）。
RUNMODE_TBL_TAG = "RunModeTbl"
# RunModeTbl 的子项：``<RunModeItem ClkCfgTbl="ClkCfgTbl"/>``，
# attribute name 即引用的目标 stem，value 是 stem 字面（R9 规则）。
RUNMODE_ITEM_TAG = "RunModeItem"

# ─── XML 属性 ────────────────────────────────────────────────────
# wrapper 的 count 锚：``<ResTbl X="Y" LineNum="N">``，N 派生为 ``len(<Line>)``，
# yaml 中以 ``@related:count(...)`` 注解承载，emit 时算出。
LINE_COUNT_ATTR = "LineNum"
# scope 绑定属性：自命名元素带此 attr 时，文件直接放对应 ``<RunMode>/`` 目录。
RUNMODE_ATTR = "RunMode"
# variant scope：行级 ``RunModeValue="0x..."``，多用于 flat 多实例
# （如 ``<CapacityRunModeMapTbl RunModeValue="0x..."/>``）。
RUNMODE_VALUE_ATTR = "RunModeValue"

# ─── YAML 协议文件 ────────────────────────────────────────────────
# 文档根 yaml：放 ``<FileInfo>`` 自身的 attributes，无 ``@element`` 头（特殊豁免）。
# 位置：fixture 根 或 ``shared/``（有 RunMode 维度时）。
ROOT_YAML = "FileInfo.yaml"
# 顶层 emit 顺序的 meta 文件，位置固定 ``template/`` 下。下划线前缀
# 表示"非数据 yaml"，被 pre/postprocess 的 glob 过滤排除。
CHILDREN_ORDER_YAML = "_children_order.yaml"

# ─── Folder 语义 ─────────────────────────────────────────────────
# 跨 RunMode 共享文件：FileInfo + 多 RunMode 都引用的 wrapper（如 DmaCfgTbl）。
SHARED_FOLDER = "shared"
# meta 文件目录（仅放 ``_children_order.yaml`` 等）。
# pack/unpack glob 时 ``TEMPLATE_FOLDER not in p.parts`` 用于排除。
TEMPLATE_FOLDER = "template"

# ─── Annotation tokens（含冒号；emit 时前置 ``# `` 转为注释） ────────
# element 数据 yaml 首行：``# @element:Foo`` / ``# @element:<self>``。
ANNOT_ELEMENT = "@element:"
# 派生计数：``LineNum: # @related:count(Line)``，emit 时值 = ``len(list)``。
ANNOT_RELATED_COUNT = "@related:count"
# 跨目录引用：``- DmaCfgTbl: "DmaCfgTbl"  # @use:../shared/DmaCfgTbl.yaml``。
# pack 不消费，只给人读 + 工具静态分析用。
ANNOT_USE = "@use:"
# ``# @element:<self>`` 的特殊 value — element 名 = stem 去 variant 后缀。
ELEMENT_SELF = "<self>"

# ─── 数值/格式常量（ASCII 长度，避免散落 magic number） ─────────────
HEX_BASE = 16               # ``int(s, HEX_BASE)`` — 解析 hex 字面
HEX_PREFIX_LEN = 2          # ``0x`` / ``0X`` — 跳过前缀取 hex digits
KEY_VAL_SEP_LEN = 2         # ``: `` — yaml ``key: val`` 中 key 与 val 间隔
LXML_TO_LEGACY_INDENT_RATIO = 2  # lxml ``pretty_print`` 用 2 空格，legacy XML 用 4 → 倍率 2
XML_ERR_TRUNC_LEN = 200     # 报错时 ``etree.tostring(elem)`` 截断长度
YAML_INDENT_MAPPING = 2     # ruamel ``indent(mapping=...)``
YAML_INDENT_SEQUENCE = 2    # ruamel ``indent(sequence=...)``
YAML_INDENT_OFFSET = 0      # ruamel ``indent(offset=...)``
YAML_LINE_WIDTH = 4096      # 不让 ruamel 主动折行（业务 yaml 行长可控）

# ─── 值解析正则 ──────────────────────────────────────────────────
# 匹配 ``0xCAFE`` / ``0X01ab`` 等 legacy hex 字面（无负号），用于保留宽度+大小写。
HEX_RE = re.compile(r"^0[xX][0-9A-Fa-f]+$")
# 匹配纯整数（含负号），用于识别 count 锚字段 + 普通 int attribute。
INT_RE = re.compile(r"^-?\d+$")
# 匹配 ``ClkCfgTbl_0x20000000`` 这类 variant suffix，第 1 组 = bare class 名。
VARIANT_SUFFIX_RE = re.compile(r"^(.+?)_(0[xX][0-9A-Fa-f]+)$")


def strip_variant(stem: str) -> str:
    """去掉 stem 末尾的 ``_<hex>`` variant 后缀（若存在），返回 bare class 名.

    >>> strip_variant("ClkCfgTbl_0x20000000")
    'ClkCfgTbl'
    >>> strip_variant("ClkCfgTbl")
    'ClkCfgTbl'
    """
    m = VARIANT_SUFFIX_RE.match(stem)
    return m.group(1) if m else stem
