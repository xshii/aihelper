"""smartci.resource_merge - 模块 1：硬件资源表合并

PURPOSE: Excel → 团队 XML → 合并 XML
PATTERN: Converter / Merger / Validator 类各负其责；合并按资源类型分派到 MergeStrategy 子类。
        新增资源类型 = 新增 strategies/{type}_strategy.py + @StrategyRegistry.register
FOR: smartci CLI 的 resource convert / merge / validate 子命令。
"""

from __future__ import annotations
