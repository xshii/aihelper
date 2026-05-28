"""L3 导出:把抽取结果整理成可比的 dict 列表,并按"同 tid 第几次"配 iter。

导出形状与具体日志字段挂钩——这里给依赖表的导出做参考实现(预留的槽)。项目按同样
套路为其它日志数据补导出函数,产物都喂给 ``compare.diff_records``。
iter 在离线按 trace 顺序数同 tid 出现次数算出,不依赖运行期计数器。
"""

from __future__ import annotations

from .deps import DepConfig, DepSlot, HeaderField, extract_dependency_table


def export_dependencies(
    records: list[dict],
    cfg: DepConfig,
    layout: list[HeaderField] | None = None,
    dep_slots: list[DepSlot] | None = None,
) -> list[dict]:
    """trace → 依赖表 → 每条配 iter → 可序列化、可比对的记录列表。"""
    counts: dict[int, int] = {}
    out: list[dict] = []
    for rec in extract_dependency_table(records, cfg, layout, dep_slots):
        iteration = counts.get(rec.tid, 0)
        counts[rec.tid] = iteration + 1
        out.append(
            {
                "tid": rec.tid,
                "iter": iteration,
                "curComputeUnit": rec.cur_compute_unit,
                "deps": [{"slot": d.slot, "tid": d.tid} for d in rec.deps],
            }
        )
    return out
