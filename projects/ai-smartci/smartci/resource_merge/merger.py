"""XmlMerger - 跨子表聚合：lxml 读写 + strategy 分派 + 级联传播 + 跨表触发

流程:
  1. 用 lxml 解析每份 XML，按各 strategy.selector_xpath 选节点 → ResourceItem
  2. 对每个 resource_type 调 strategy.merge() → MergeResult（含 remaps）
  3. 跨 strategy 应用 merge_triggers：cluster 合并时可带动它引用的 tables 跨团队合并
  4. 应用 ValueRemap 到 ForeignKeyRef 引用方（团队内闭合级联）；单轮传播，环检测
  5. 外键校验：引用字段值必须存在于目标资源 ref_field 值域
  6. 写回一份结构化 final XML：<merged><{rt}><item .../>...</{rt}>...</merged>

>>> from pathlib import Path
>>> from smartci.resource_merge.merger import XmlMerger
>>> from smartci.resource_merge.strategies.registry import StrategyRegistry
>>> XmlMerger(registry=StrategyRegistry())  # 空 registry 可构造
<smartci.resource_merge.merger.XmlMerger object at ...>
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type, cast

from lxml import etree

from smartci.const import (
    ConflictKind,
    CROSS_NAME_SEP,
    XML_ENCODING,
    XML_ITEM_TAG,
    XML_ROOT_TAG,
)
from smartci.resource_merge.strategies.base import (
    CrossNamePolicy,
    ForeignKeyRef,
    MergeConflict,
    MergeResult,
    MergeStrategy,
    MergeTriggerRef,
    ResourceItem,
    ValueRemap,
)
from smartci.resource_merge.strategies.registry import StrategyRegistry


class CascadeCycleError(RuntimeError):
    """级联传播产生了新的 remap → 形成多轮级联环。"""


@dataclass
class MergeReport:
    """跨 strategy 聚合报告（区别于单 strategy 的 MergeResult）。"""
    output_path: Path
    merged_by_type: Dict[str, List[ResourceItem]] = field(default_factory=dict)
    conflicts: List[MergeConflict] = field(default_factory=list)
    applied_cascades: int = 0

    @property
    def has_conflicts(self) -> bool:
        return bool(self.conflicts)


class XmlMerger:
    def __init__(self, registry: Optional[StrategyRegistry] = None) -> None:
        self._registry = registry or StrategyRegistry.default()

    # ── 对外入口 ───────────────────────────────────────
    def merge(self, inputs: List[Path], output: Path) -> MergeReport:
        items_by_type_team = self._parse_inputs(inputs)

        per_type: Dict[str, MergeResult] = {}
        for rt, items_by_team in items_by_type_team.items():
            strategy = self._registry.get(rt)()
            per_type[rt] = strategy.merge(items_by_team)

        report = MergeReport(output_path=output)
        for rt, res in per_type.items():
            report.merged_by_type[rt] = list(res.merged)
            report.conflicts.extend(res.conflicts)

        # 跨表触发合并：先于外键级联
        trigger_conflicts = self._apply_merge_triggers(
            report.merged_by_type, items_by_type_team,
        )
        report.conflicts.extend(trigger_conflicts)

        # 外键级联（rename 跟随）
        all_remaps = [r for res in per_type.values() for r in res.remaps]
        report.applied_cascades = self._apply_cascade(
            report.merged_by_type, all_remaps,
        )
        report.conflicts.extend(self._check_foreign_keys(report.merged_by_type))

        self._write_output(report.merged_by_type, output)
        return report

    # ── 级联传播 ───────────────────────────────────────
    def _apply_cascade(
        self,
        merged_by_type: Dict[str, List[ResourceItem]],
        remaps: List[ValueRemap],
    ) -> int:
        if not remaps:
            return 0
        applied, new_remaps = self._run_one_pass(merged_by_type, remaps)
        if new_remaps:
            raise CascadeCycleError(
                f"检测到多轮级联（{len(new_remaps)} 处新 remap）；单轮传播约束被破坏，"
                "请拆分子表或显式建模依赖。"
            )
        return applied

    def _run_one_pass(
        self,
        merged_by_type: Dict[str, List[ResourceItem]],
        remaps: List[ValueRemap],
    ) -> Tuple[int, List[ValueRemap]]:
        """单轮传播：对所有 ForeignKeyRef 应用 remap 表（同 team 匹配）。

        new_remaps 当前始终为空——单轮传播不产生新 remap，
        因为 rename 的 new_value 是"加前缀/数字偏移过"的派生值，
        不会再等于别的 ValueRemap 的 old_value。保留返回 None 是防御性占位。
        """
        applied = 0
        new_remaps: List[ValueRemap] = []
        index = self._index_remaps(remaps)
        for rt, items in merged_by_type.items():
            strategy_cls = self._registry.get(rt)
            for fk in strategy_cls.foreign_keys:
                applied += self._apply_fk(items, fk, index)
        return applied, new_remaps

    @staticmethod
    def _apply_fk(
        items: List[ResourceItem],
        fk: ForeignKeyRef,
        index: Dict[tuple, str],
    ) -> int:
        applied = 0
        for item in items:
            old = item.attrs.get(fk.field, "")
            if not old:
                continue
            new = index.get((item.team, fk.ref_resource, fk.ref_field, old))
            if new and new != old:
                item.attrs[fk.field] = new
                applied += 1
        return applied

    @staticmethod
    def _index_remaps(remaps: List[ValueRemap]) -> Dict[tuple, str]:
        return {
            (r.team, r.resource_type, r.field, r.old_value): r.new_value
            for r in remaps
        }

    # ── 跨表触发合并 ───────────────────────────────────
    def _apply_merge_triggers(
        self,
        merged_by_type: Dict[str, List[ResourceItem]],
        original_by_type_team: Dict[str, Dict[str, List[ResourceItem]]],
    ) -> List[MergeConflict]:
        """source_rt 真正融合时，按 merge_triggers 把它引用的 target 跨团队合并。

        触发条件:
          source_rt 的 merged_by_type 里至少有一个 is_merged=True 的 item。
          （没融合发生就不触发，避免无谓改名）

        算法:
          1. 从"原始每团队" source_rt.items 抽 list_attrs[trigger.field] → referenced[team]
             注意: 不从融合后的 item 抽（那会跨团队扩散引用集合）
          2. 按 cross_name_policy 决定统一后的目标 key
          3. 把原始 target_rt.items 中 key 在 referenced[team] 的改名为 unified
          4. 再次调 target strategy.merge() 让同名自动合并
          5. 覆盖 merged_by_type[target_resource]
        """
        conflicts: List[MergeConflict] = []
        for source_rt in list(merged_by_type):
            strategy_cls = self._registry.get(source_rt)
            if not strategy_cls.merge_triggers:
                continue
            if not any(it.is_merged for it in merged_by_type[source_rt]):
                continue  # ← 关键：没融合 → 不触发
            for trigger in strategy_cls.merge_triggers:
                conflicts.extend(self._trigger_one(
                    source_rt, trigger, merged_by_type, original_by_type_team,
                ))
        return conflicts

    def _trigger_one(
        self,
        source_rt: str,
        trigger: MergeTriggerRef,
        merged_by_type: Dict[str, List[ResourceItem]],
        original_by_type_team: Dict[str, Dict[str, List[ResourceItem]]],
    ) -> List[MergeConflict]:
        """执行单条 trigger：收集团队内引用 + 按 cross_name_policy 改名 + 触发 target merge。"""
        referenced = self._collect_referenced(
            source_rt, trigger.field, original_by_type_team,
        )
        if not referenced:
            return []

        policy = trigger.cross_name_policy
        if policy is CrossNamePolicy.KEEP_SEPARATE:
            return []
        if policy is CrossNamePolicy.STRICT:
            return self._strict_check(trigger, referenced)

        unified_name = self._unified_name(referenced, policy)
        renamed_items = self._rename_target_items(
            trigger, referenced, unified_name, original_by_type_team,
        )
        if not renamed_items:
            return []

        target_strategy = self._registry.get(trigger.target_resource)()
        result = target_strategy.merge(renamed_items)
        merged_by_type[trigger.target_resource] = list(result.merged)
        return list(result.conflicts)

    @staticmethod
    def _collect_referenced(
        source_rt: str,
        field_name: str,
        original_by_type_team: Dict[str, Dict[str, List[ResourceItem]]],
    ) -> Dict[str, List[str]]:
        """从 source_rt 的**原始每团队** items 收集 list_attrs[field_name]（去重保序）。

        严格 per-team：team-a 的 names 只来自 team-a 自己的 items，不跨团队扩散。
        """
        referenced: Dict[str, List[str]] = {}
        for team, items in original_by_type_team.get(source_rt, {}).items():
            names: List[str] = []
            for item in items:
                names.extend(item.list_attrs.get(field_name, []))
            if names:
                referenced[team] = list(dict.fromkeys(names))
        return referenced

    @staticmethod
    def _unified_name(
        referenced: Dict[str, List[str]], policy: CrossNamePolicy,
    ) -> str:
        """按策略产出统一后的名字（UNION_AS_NEW / PRIMARY_NAME）。"""
        all_names = sorted({n for names in referenced.values() for n in names})
        if policy is CrossNamePolicy.UNION_AS_NEW:
            return CROSS_NAME_SEP.join(all_names)
        # PRIMARY_NAME：取第一个团队的第一个名字（即输入顺序下最早出现的）
        for _team, names in referenced.items():
            if names:
                return names[0]
        return ""

    def _rename_target_items(
        self,
        trigger: MergeTriggerRef,
        referenced: Dict[str, List[str]],
        unified_name: str,
        original_by_type_team: Dict[str, Dict[str, List[ResourceItem]]],
    ) -> Dict[str, List[ResourceItem]]:
        """把原始目标 items 中 key_field 在 referenced 里的全部改为 unified_name。"""
        target_rt = trigger.target_resource
        original = original_by_type_team.get(target_rt, {})
        out: Dict[str, List[ResourceItem]] = {}
        for team, names in referenced.items():
            name_set = set(names)
            modified: List[ResourceItem] = []
            for item in original.get(team, []):
                if item.attrs.get(trigger.target_key_field, "") in name_set:
                    new_attrs = dict(item.attrs)
                    new_attrs[trigger.target_key_field] = unified_name
                    modified.append(ResourceItem(
                        team=team, attrs=new_attrs,
                        list_attrs=dict(item.list_attrs),
                        is_merged=item.is_merged,
                    ))
                else:
                    modified.append(item)
            out[team] = modified
        return out

    @staticmethod
    def _strict_check(
        trigger: MergeTriggerRef, referenced: Dict[str, List[str]],
    ) -> List[MergeConflict]:
        """STRICT 策略：各团队引用的 target 名字必须完全一致。"""
        sets = [frozenset(names) for names in referenced.values()]
        if len(set(sets)) <= 1:
            return []
        return [MergeConflict(
            resource_type=trigger.target_resource,
            detail=(
                f"merge_triggers(STRICT): 各团队引用的 {trigger.target_resource} "
                f"名字不一致: {dict(referenced)}"
            ),
            teams=list(referenced),
            kind=ConflictKind.CROSS_NAME,
        )]

    # ── 外键校验 ───────────────────────────────────────
    def _check_foreign_keys(
        self, merged_by_type: Dict[str, List[ResourceItem]],
    ) -> List[MergeConflict]:
        conflicts: List[MergeConflict] = []
        value_sets = self._build_value_sets(merged_by_type)
        for rt, items in merged_by_type.items():
            strategy_cls = self._registry.get(rt)
            for fk in strategy_cls.foreign_keys:
                valid = value_sets.get((fk.ref_resource, fk.ref_field), set())
                for item in items:
                    val = item.attrs.get(fk.field, "")
                    if val and val not in valid:
                        conflicts.append(MergeConflict(
                            resource_type=rt,
                            detail=(
                                f"{fk.field}={val!r} 在 "
                                f"{fk.ref_resource}.{fk.ref_field} 无对应项"
                            ),
                            teams=[item.team], kind=ConflictKind.FOREIGN_KEY,
                        ))
        return conflicts

    @staticmethod
    def _build_value_sets(
        merged_by_type: Dict[str, List[ResourceItem]],
    ) -> Dict[tuple, set]:
        out: Dict[tuple, set] = {}
        for rt, items in merged_by_type.items():
            by_field: Dict[str, set] = {}
            for item in items:
                for f, v in item.attrs.items():
                    by_field.setdefault(f, set()).add(v)
            for f, vals in by_field.items():
                out[(rt, f)] = vals
        return out

    # ── XML 读 ─────────────────────────────────────────
    def _parse_inputs(
        self, inputs: List[Path],
    ) -> Dict[str, Dict[str, List[ResourceItem]]]:
        """lxml 解析。每个 input 文件 stem 作 team 名。

        按每个注册的 strategy.selector_xpath 选节点，fields / children_xpaths
        分别抽单值和多值字段。
        """
        result: Dict[str, Dict[str, List[ResourceItem]]] = {}
        for path in inputs:
            team = path.stem
            tree = etree.parse(str(path))
            for rt in self._registry.list_types():
                strategy_cls = self._registry.get(rt)
                result.setdefault(rt, {})
                result[rt][team] = self._extract_items(tree, strategy_cls, team)
        return result

    @staticmethod
    def _extract_items(
        tree: Any,       # lxml _ElementTree；宽类型避开 mypy 对私有类型的碎吐槽
        strategy_cls: Type[MergeStrategy],
        team: str,
    ) -> List[ResourceItem]:
        # lxml xpath 返回是 Union[Element/str/bytes/int/...]，实际 selector 总拿节点列表
        nodes = cast(List[Any], tree.xpath(strategy_cls.selector_xpath))
        items: List[ResourceItem] = []
        for node in nodes:
            attrs: Dict[str, str] = {}
            for name, xp in strategy_cls.fields.items():
                vals = cast(List[Any], node.xpath(xp))
                v = _first_scalar(vals)
                if v is not None:
                    attrs[name] = v
            list_attrs: Dict[str, List[str]] = {}
            for name, xp in strategy_cls.children_xpaths.items():
                vals = cast(List[Any], node.xpath(xp))
                list_attrs[name] = [str(v) for v in vals if _first_scalar([v])]
            items.append(ResourceItem(team=team, attrs=attrs, list_attrs=list_attrs))
        return items

    # ── XML 写 ─────────────────────────────────────────
    def _write_output(
        self, merged_by_type: Dict[str, List[ResourceItem]], output: Path,
    ) -> None:
        """写结构化 final XML。

        格式 (简化版):
          <merged>
            <{resource_type}>
              <item {attr}="..." ...>
                <{child_field} value="..."/>  (多值字段)
                ...
              </item>
              ...
            </{resource_type}>
            ...
          </merged>

        注意:
          - is_merged=True 且声明了 count_field 的 item：count_field 已在 resolve
            时被移除，这里不再写
          - is_merged=False 或无 count_field 的 item：保留 attrs 里的所有键
        """
        root = etree.Element(XML_ROOT_TAG)
        for rt, items in merged_by_type.items():
            strategy_cls = self._registry.get(rt)
            container = etree.SubElement(root, rt)
            for item in items:
                self._write_item(container, item, strategy_cls)
        tree = etree.ElementTree(root)
        output.parent.mkdir(parents=True, exist_ok=True)
        tree.write(
            str(output), pretty_print=True, xml_declaration=True, encoding=XML_ENCODING,
        )

    @staticmethod
    def _write_item(
        container: "etree._Element",
        item: ResourceItem,
        strategy_cls: Type[MergeStrategy],
    ) -> None:
        node = etree.SubElement(container, XML_ITEM_TAG)
        for name in strategy_cls.fields:
            if name in item.attrs:
                node.set(name, item.attrs[name])
        for name, values in item.list_attrs.items():
            for v in values:
                child = etree.SubElement(node, name)
                child.text = v


# ── 模块级 helper ─────────────────────────────────────
def _first_scalar(vals: Any) -> Optional[str]:
    """把 lxml xpath 结果规约成 str。

    >>> _first_scalar(["a", "b"])
    'a'
    >>> _first_scalar([])
    >>> _first_scalar(["x"])
    'x'
    """
    if not vals:
        return None
    v = vals[0]
    if hasattr(v, "text"):  # Element
        return v.text or ""
    return str(v)
