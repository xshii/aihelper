"""legacy/ 子包共享的 ruamel YAML rt instance + 序列化 helper.

集中此处避免 preprocess / scaffold / postprocess 各自重复配置 indent / width。
"""
from __future__ import annotations

import io
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

from ecfg.legacy.const import (
    ANNOT_ELEMENT,
    ANNOT_RELATED_COUNT,
    KEY_VAL_SEP_LEN,
    YAML_INDENT_MAPPING,
    YAML_INDENT_OFFSET,
    YAML_INDENT_SEQUENCE,
    YAML_LINE_WIDTH,
)

YAML_RT = YAML(typ="rt")
# 紧凑序列：``- `` 与父 key 同列，list item 内嵌 mapping 字段缩进 2
YAML_RT.indent(
    mapping=YAML_INDENT_MAPPING,
    sequence=YAML_INDENT_SEQUENCE,
    offset=YAML_INDENT_OFFSET,
)
YAML_RT.preserve_quotes = True
YAML_RT.width = YAML_LINE_WIDTH


def dump_yaml(doc: Any) -> str:
    """ruamel rt dump → str."""
    buf = io.StringIO()
    YAML_RT.dump(doc, buf)
    return buf.getvalue()


def element_header(elem_name: str) -> str:
    """生成 ``# @element:<X>\\n`` 数据/scaffold yaml 首行."""
    return f"# {ANNOT_ELEMENT}{elem_name}\n"


def attach_count_anchor(doc: CommentedMap, key: str, subtag: str) -> None:
    """给 ``key`` 挂 EOL 注释 ``# @related:count(<subtag>)``，列对齐到 ``KEY_VAL_SEP_LEN``."""
    doc.yaml_add_eol_comment(
        f"{ANNOT_RELATED_COUNT}({subtag})", key,
        column=len(key) + KEY_VAL_SEP_LEN,
    )
