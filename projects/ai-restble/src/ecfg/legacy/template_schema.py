"""Template scaffold → 字段约束 dict 的桥层（read-only，给 viz / form 消费）.

scaffold 本身只产**结构骨架** + null 占位（见 ``skill-scaffold.md``）；用户后填
``@merge / @range / @enum / FK`` 等注解，本模块把这些注解从 EOL 注释中抽出来，
返回 flat ``Dict[field_name, FieldConstraint]``。

与 ``ecfg.schema.loader`` 的区别：
- ``schema.loader`` 读 data yaml 内嵌的 ``# ----- TEMPLATE BEGIN -----`` 块
  （merge-spec 三区域形态），用于 merge engine
- 本模块读 ``template/<scope>/<E>.yaml`` scaffold 文件（legacy flat 形态），
  用于 viz read-only 显示约束 + 后续 form 编辑控件分派

注解 key 集复用 ``ecfg.schema.const::ANNOT_KEY_*``，不重复定义。
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, fields as dc_fields
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from ruamel.yaml.comments import CommentedMap, CommentedSeq

from ecfg.legacy._yaml import YAML_RT
from ecfg.legacy.const import (
    FAKE_RUNMODE_FOLDER,
    SHARED_FOLDER,
    TEMPLATE_FOLDER,
    strip_variant,
)
from ecfg.schema._comments import trailing_comment
from ecfg.schema.annotations import parse_comment
from ecfg.schema.const import (
    ANNOT_KEY_ENUM,
    ANNOT_KEY_MERGE,
    ANNOT_KEY_RANGE,
)

_RANGE_RE = re.compile(r"^([+-]?\d+(?:\.\d+)?)\s*-\s*([+-]?\d+(?:\.\d+)?)$")


# region public types ────────────────────────────────────────────────────────
@dataclass
class FieldConstraint:
    """单字段在 template 上声明的约束（来自 EOL ``@<key>:<value>`` 注解）.

    所有字段 ``Optional`` 默认 None；缺失即"无该约束"，前端退化为通用 text input。
    """

    merge_rule: Optional[str] = None
    range_lo: Optional[float] = None
    range_hi: Optional[float] = None
    enum_values: Optional[List[str]] = None

    def is_empty(self) -> bool:
        """全字段未填 → 调用方可跳过此条 constraint（输出更紧凑）."""
        return all(getattr(self, f.name) is None for f in dc_fields(self))

    def to_dict(self) -> Dict[str, Any]:
        """JSON-friendly sparse dict（None 字段省略，键名为前端契约 short form）."""
        out: Dict[str, Any] = {}
        if self.merge_rule is not None:
            out["merge"] = self.merge_rule
        if self.range_lo is not None and self.range_hi is not None:
            out["range"] = [self.range_lo, self.range_hi]
        if self.enum_values is not None:
            out["enum"] = list(self.enum_values)
        return out


# endregion

# region path resolution ────────────────────────────────────────────────────
def resolve_template_path(data_yaml_path: Path, yaml_dir: Path) -> Path:
    """data yaml 路径 → 对应 template scaffold 路径（不检查存在性）.

    布局规则（来自 ``skill-scaffold.md``）：

    - root scope（无 scope 子目录）：``<yaml_dir>/<E>.yaml`` →
      ``<yaml_dir>/template/<E>.yaml``
    - shared scope：``<yaml_dir>/shared/<E>.yaml`` →
      ``<yaml_dir>/template/shared/<E>.yaml``
    - RunMode scope（任意 ``0x...``）：``<yaml_dir>/0x10000000/<E>.yaml`` →
      ``<yaml_dir>/template/0x00000000/<E>.yaml``（``FAKE_RUNMODE_FOLDER`` 占位，
      所有 RunMode scope 共享同一份 schema）
    - variant suffix（``ClkCfgTbl_0x20000000``）→ bare class lookup
      （``template/0x00000000/ClkCfgTbl.yaml``）
    """
    rel = data_yaml_path.relative_to(yaml_dir)
    bare_stem = strip_variant(data_yaml_path.stem)
    template_root = yaml_dir / TEMPLATE_FOLDER
    if len(rel.parts) == 1:
        return template_root / f"{bare_stem}.yaml"
    scope = rel.parts[0]
    if scope == SHARED_FOLDER:
        return template_root / SHARED_FOLDER / f"{bare_stem}.yaml"
    return template_root / FAKE_RUNMODE_FOLDER / f"{bare_stem}.yaml"


# endregion

# region constraint loading ────────────────────────────────────────────────
def load_template_constraints(template_path: Path) -> Dict[str, FieldConstraint]:
    """读 template scaffold → flat ``{field_name: FieldConstraint}``.

    template 不存在 / 无注解 → 空 dict。不抛异常，前端按"无 schema"路径退化。
    field_name 名字collision（顶层标量 + 内 record 子字段同名）→ 后写覆盖前写
    （legacy template 极少出现此情形，MVP 接受）。
    """
    if not template_path.is_file():
        return {}
    text = template_path.read_text(encoding="utf-8")
    body = YAML_RT.load(io.StringIO(text))
    if not isinstance(body, CommentedMap):
        return {}
    out: Dict[str, FieldConstraint] = {}
    for fname, fc in _walk_template(body):
        if not fc.is_empty():
            out[fname] = fc
    return out


def _walk_template(
    body: CommentedMap,
) -> Iterator[Tuple[str, FieldConstraint]]:
    """yield ``(field_name, constraint)`` 对，覆盖：

    - 顶层 scalar 键（self-named flat / self-named with children 的 outer 字段）
    - 内层 record list 首行 mapping 的所有键（wrapper / self-named with children
      的 inner row 字段）

    嵌套更深的 mapping 当前不递归（legacy template 不出现 3 层嵌套）。
    """
    for k, v in body.items():
        if isinstance(v, CommentedSeq) and v and isinstance(v[0], CommentedMap):
            inner = v[0]
            for inner_name in inner:
                yield str(inner_name), _parse_constraint(
                    trailing_comment(inner, inner_name) or ""
                )
        elif not isinstance(v, (CommentedSeq, CommentedMap)):
            yield str(k), _parse_constraint(trailing_comment(body, k) or "")


def _parse_constraint(comment: str) -> FieldConstraint:
    """单条 EOL 注释字符串 → ``FieldConstraint``（未识别 annotation 静默跳过）."""
    fc = FieldConstraint()
    parsed = parse_comment(comment)
    for ann in parsed.annotations:
        if ann.key == ANNOT_KEY_MERGE:
            fc.merge_rule = ann.value
        elif ann.key == ANNOT_KEY_RANGE:
            m = _RANGE_RE.match(ann.value)
            if m:
                fc.range_lo = float(m.group(1))
                fc.range_hi = float(m.group(2))
        elif ann.key == ANNOT_KEY_ENUM:
            fc.enum_values = [v.strip() for v in ann.value.split(",") if v.strip()]
    return fc


# endregion
