"""MergeStrategy - 子表合并策略基类

设计要点:
  * 每个子表对应一个 MergeStrategy 子类
  * 子类用 ClassVar 声明 "XML 位置 + 字段 XPath + 合并策略"，
    XmlMerger 负责 XPath 读写，Strategy 仅处理扁平值对象
  * 对应的 XML 结构可有三层：容器（cluster）、表（table）、行（row）
  * 容器合并可触发表合并（MergeTriggerRef），实现"因父合并而触发子合并"
  * XML 顺序 = 依赖顺序；先到先得，后来者走 rename 或 conflict

子类 Checklist:
  必填:
    resource_type   str             资源类型名
    selector_xpath  str             全文档 XPath，选中所有同类节点
    fields          Dict[str, str]  单值字段 name → 相对节点的 XPath
    key_fields      List[str]       fields 里哪些组合成唯一键

  可选:
    conflict_policy   ConflictPolicy     默认 ERROR
    children_xpaths   Dict[str, str]     多值子列表（如 ./ref/@table）
    count_field       Optional[str]      子元素个数的属性名（如 number / count）
    merge_triggers    List[MergeTriggerRef]  合并时触发的跨表合并
    foreign_keys      List[ForeignKeyRef]    跨子表引用（校验 + rename 级联）

  钩子（按需覆盖）:
    validate_item(item)                单条校验，非法抛 ValueError
    is_conflict(a, b)                  同 key 的两条是否真冲突
    resolve(a, b)                      冲突时如何保留/融合
    rename_key_value(team, f, old)     RENAME_ON_CONFLICT 时生成新 id

count_field 行为矩阵:
    策略                        融合发生  count 是否保留
    MERGE_CHILDREN              ✓         ❌ 移除（融合后重算）
    ERROR  → 记 conflict        ✗         ✓ 原值
    RENAME_ON_CONFLICT          ✗         ✓ 各自保留
    子类覆盖 resolve 返回融合   ✓         由子类决定（默认 is_merged=True 则移除）

>>> from smartci.resource_merge.strategies.base import (
...     ConflictPolicy, MergeStrategy, ResourceItem,
... )
>>> class _Demo(MergeStrategy):
...     resource_type = "_demo"
...     selector_xpath = "//demo"
...     fields = {"id": "@id", "v": "@v"}
...     key_fields = ["id"]
...     conflict_policy = ConflictPolicy.ERROR
>>> r = _Demo().merge({
...     "a": [ResourceItem("a", {"id": "1", "v": "x"})],
...     "b": [ResourceItem("b", {"id": "2", "v": "y"})],
... })
>>> sorted(it.attrs["id"] for it in r.merged)
['1', '2']
>>> r.conflicts
[]
"""
from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import ClassVar, Dict, List, Mapping, Optional, Set, Tuple

from smartci.const import (
    ConflictKind,
    RENAME_PREFIX_SEP,
    TEAM_MERGE_SEP,
)

# 不可变空默认值：防止 ClassVar 在子类间共享可变状态
_EMPTY_MAP: Mapping[str, str] = MappingProxyType({})


# ── 数据模型 ─────────────────────────────────────────────
@dataclass
class ResourceItem:
    """Strategy 处理的扁平值对象。

    attrs        单值字段
    list_attrs   多值字段（从 children_xpaths 抽取的子元素列表）
    is_merged    是否由 resolve() 融合产生（True 时 XmlMerger 写回不带 count_field）
    """
    team: str
    attrs: Dict[str, str] = field(default_factory=dict)
    list_attrs: Dict[str, List[str]] = field(default_factory=dict)
    is_merged: bool = False


@dataclass
class MergeConflict:
    resource_type: str
    detail: str
    teams: List[str] = field(default_factory=list)
    kind: str = ConflictKind.CONFLICT    # ConflictKind 常量之一


@dataclass(frozen=True)
class ValueRemap:
    """rename 后的映射：仅对 team 一个团队的 items 生效（团队内闭合级联）"""
    team: str
    resource_type: str
    field: str
    old_value: str
    new_value: str


@dataclass
class MergeResult:
    merged: List[ResourceItem] = field(default_factory=list)
    conflicts: List[MergeConflict] = field(default_factory=list)
    remaps: List[ValueRemap] = field(default_factory=list)


class ConflictPolicy(Enum):
    ERROR = "error"                       # 记 conflict 不合并（默认）
    RENAME_ON_CONFLICT = "rename"         # 后来者 rename + 团队内引用级联
    MERGE_CHILDREN = "merge_children"     # 合并 list_attrs（子列表并集）+ attrs 并集


class CrossNamePolicy(Enum):
    STRICT = "strict"                     # 表名不同 → 报 cross_name 冲突
    UNION_AS_NEW = "union_as_new"         # 表名不同 → 合并为新名 "a+b"
    KEEP_SEPARATE = "keep_separate"       # 表名不同 → 不触发，各自保留
    PRIMARY_NAME = "primary_name"         # 表名不同 → 合并，用先出现的名字


@dataclass(frozen=True)
class ForeignKeyRef:
    """跨子表引用校验 + rename 级联目标。"""
    field: str
    ref_resource: str
    ref_field: str


@dataclass(frozen=True)
class MergeTriggerRef:
    """本资源合并时触发另一个 resource 的跨团队合并。

    示例: cluster 合并时，触发它引用的 tables 合并 →
        MergeTriggerRef(
            field="tables", target_resource="table",
            target_key_field="name",
            cross_name_policy=CrossNamePolicy.UNION_AS_NEW,
        )
    """
    field: str
    target_resource: str
    target_key_field: str
    cross_name_policy: CrossNamePolicy = CrossNamePolicy.STRICT


# ── 策略基类 ─────────────────────────────────────────────
class MergeStrategy(ABC):
    # ── 必填 ClassVar ──────────────────────────────────
    resource_type: ClassVar[str] = ""
    selector_xpath: ClassVar[str] = ""
    fields: ClassVar[Mapping[str, str]] = _EMPTY_MAP      # name → XPath
    key_fields: ClassVar[List[str]] = []                   # 子类必须声明（不给 "id" 默认）
    conflict_policy: ClassVar[ConflictPolicy] = ConflictPolicy.ERROR

    # ── 可选 ClassVar ──────────────────────────────────
    children_xpaths: ClassVar[Mapping[str, str]] = _EMPTY_MAP  # name → XPath
    count_field: ClassVar[Optional[str]] = None
    foreign_keys: ClassVar[List[ForeignKeyRef]] = []
    merge_triggers: ClassVar[List[MergeTriggerRef]] = []

    # ── 子类注册时校验必填 ClassVar（__init_subclass__ cookbook）──
    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        # 允许中间抽象基类（类名以 _Base 结尾或自身 abstract）跳过校验
        if cls.__name__.endswith("_Base") or getattr(cls, "__abstractmethods__", None):
            return
        if not cls.resource_type:
            raise TypeError(f"{cls.__name__}.resource_type 未声明")
        if not cls.selector_xpath:
            raise TypeError(f"{cls.__name__}.selector_xpath 未声明")
        if not cls.fields:
            raise TypeError(f"{cls.__name__}.fields 未声明")
        if not cls.key_fields:
            raise TypeError(f"{cls.__name__}.key_fields 未声明（唯一键属性名）")
        unknown = [f for f in cls.key_fields if f not in cls.fields]
        if unknown:
            raise TypeError(
                f"{cls.__name__}.key_fields 包含未在 fields 声明的字段: {unknown}"
            )
        if cls.count_field and cls.count_field not in cls.fields:
            raise TypeError(
                f"{cls.__name__}.count_field={cls.count_field!r} "
                f"必须也在 fields 里声明 XPath"
            )

    # ── 钩子（按需覆盖）───────────────────────────────
    def validate_item(self, item: ResourceItem) -> None:
        """单条校验；非法抛 ValueError。"""

    def is_conflict(self, a: ResourceItem, b: ResourceItem) -> bool:
        """同 key 两条是否冲突。MERGE_CHILDREN 下总是 True（总走 resolve 融合）。

        >>> class _D(MergeStrategy):
        ...     resource_type = "_d"
        ...     selector_xpath = "//d"
        ...     fields = {"id": "@id"}
        ...     key_fields = ["id"]
        ...     conflict_policy = ConflictPolicy.MERGE_CHILDREN
        >>> s = _D()
        >>> s.is_conflict(ResourceItem("a", {"id": "1"}), ResourceItem("b", {"id": "1"}))
        True
        """
        if self.conflict_policy is ConflictPolicy.MERGE_CHILDREN:
            return True
        return a.attrs != b.attrs or a.list_attrs != b.list_attrs

    def resolve(
        self, a: ResourceItem, b: ResourceItem,
    ) -> Optional[ResourceItem]:
        """冲突时保留/融合。None = 记 conflict 不合并。

        MERGE_CHILDREN 默认实现：list_attrs 并集（顺序去重）+ attrs 取 a 为主 +
        移除 count_field（融合后重算）+ is_merged=True。

        >>> class _D(MergeStrategy):
        ...     resource_type = "_d"
        ...     selector_xpath = "//d"
        ...     fields = {"id": "@id", "number": "@number"}
        ...     key_fields = ["id"]
        ...     conflict_policy = ConflictPolicy.MERGE_CHILDREN
        ...     count_field = "number"
        >>> a = ResourceItem("a", {"id": "1", "number": "2"}, {"tables": ["x", "y"]})
        >>> b = ResourceItem("b", {"id": "1", "number": "3"}, {"tables": ["y", "z"]})
        >>> m = _D().resolve(a, b)
        >>> m.list_attrs["tables"]
        ['x', 'y', 'z']
        >>> "number" in m.attrs
        False
        >>> m.is_merged
        True
        """
        if self.conflict_policy is ConflictPolicy.MERGE_CHILDREN:
            return self._merge_children(a, b)
        return None

    def rename_key_value(self, team: str, field_name: str, old_value: str) -> str:
        """RENAME_ON_CONFLICT 时为后到者生成新 id。默认加 team 前缀。

        >>> class _D(MergeStrategy):
        ...     resource_type = "_d"
        ...     selector_xpath = "//d"
        ...     fields = {"id": "@id"}
        ...     key_fields = ["id"]
        >>> _D().rename_key_value("team-b", "id", "1")
        'team-b_1'
        """
        return f"{team}{RENAME_PREFIX_SEP}{old_value}" if old_value else old_value

    # ── rename 前置阶段 ──────────────────────────────
    def rename_on_conflict(
        self, items_by_team: Dict[str, List[ResourceItem]],
    ) -> Tuple[Dict[str, List[ResourceItem]], List[ValueRemap]]:
        if self.conflict_policy is not ConflictPolicy.RENAME_ON_CONFLICT:
            return items_by_team, []
        remaps: List[ValueRemap] = []
        new_by_team: Dict[str, List[ResourceItem]] = {}
        seen: Set[Tuple[str, ...]] = set()
        for team, items in items_by_team.items():
            new_by_team[team] = [
                self._rename_or_keep(it, team, seen, remaps) for it in items
            ]
        return new_by_team, remaps

    # ── 模板方法（通常不覆盖）────────────────────────
    def merge(
        self, items_by_team: Dict[str, List[ResourceItem]],
    ) -> MergeResult:
        items_by_team, remaps = self.rename_on_conflict(items_by_team)
        result = MergeResult(remaps=list(remaps))
        kept: Dict[Tuple[str, ...], ResourceItem] = {}
        for team, items in items_by_team.items():
            for item in items:
                self._process_one(item, team, kept, result)
        result.merged = list(kept.values())
        return result

    # ── 内部 helper ──────────────────────────────────
    def _merge_children(
        self, a: ResourceItem, b: ResourceItem,
    ) -> ResourceItem:
        """MERGE_CHILDREN 的默认融合实现。"""
        merged_lists: Dict[str, List[str]] = {k: list(v) for k, v in a.list_attrs.items()}
        for k, vs in b.list_attrs.items():
            existing = merged_lists.setdefault(k, [])
            merged_lists[k] = _dedupe_in_order(existing + list(vs))

        merged_attrs = dict(a.attrs)
        for k, v in b.attrs.items():
            merged_attrs.setdefault(k, v)
        if self.count_field:
            merged_attrs.pop(self.count_field, None)

        return ResourceItem(
            team=f"{a.team}{TEAM_MERGE_SEP}{b.team}",
            attrs=merged_attrs,
            list_attrs=merged_lists,
            is_merged=True,
        )

    def _rename_or_keep(
        self,
        item: ResourceItem,
        team: str,
        seen: Set[Tuple[str, ...]],
        remaps: List[ValueRemap],
    ) -> ResourceItem:
        key = self._compute_key(item.attrs)
        if key not in seen:
            seen.add(key)
            return item
        new_attrs = dict(item.attrs)
        for fn in self.key_fields:
            old = item.attrs.get(fn, "")
            new = self.rename_key_value(team, fn, old)
            new_attrs[fn] = new
            if old and old != new:
                remaps.append(ValueRemap(
                    team=team, resource_type=self.resource_type,
                    field=fn, old_value=old, new_value=new,
                ))
        seen.add(self._compute_key(new_attrs))
        return ResourceItem(
            team=team, attrs=new_attrs,
            list_attrs=dict(item.list_attrs), is_merged=item.is_merged,
        )

    def _process_one(
        self,
        item: ResourceItem,
        team: str,
        kept: Dict[Tuple[str, ...], ResourceItem],
        result: MergeResult,
    ) -> None:
        try:
            self.validate_item(item)
        except ValueError as e:
            result.conflicts.append(MergeConflict(
                resource_type=self.resource_type,
                detail=f"校验失败 ({team}): {e}",
                teams=[team], kind=ConflictKind.VALIDATE,
            ))
            return
        key = self._compute_key(item.attrs)
        if key not in kept:
            kept[key] = item
            return
        existing = kept[key]
        if not self.is_conflict(existing, item):
            return
        resolved = self.resolve(existing, item)
        if resolved is None:
            result.conflicts.append(MergeConflict(
                resource_type=self.resource_type,
                detail=f"key={key} 在 {existing.team} 和 {item.team} 冲突",
                teams=[existing.team, item.team],
            ))
        else:
            kept[key] = resolved

    def _compute_key(self, attrs: Dict[str, str]) -> Tuple[str, ...]:
        return tuple(attrs.get(fn, "") for fn in self.key_fields)


# ── 模块级 helper ─────────────────────────────────────
def _dedupe_in_order(items: List[str]) -> List[str]:
    """保序去重。

    >>> _dedupe_in_order(["a", "b", "a", "c", "b"])
    ['a', 'b', 'c']
    """
    return list(dict.fromkeys(x for x in items if x))
