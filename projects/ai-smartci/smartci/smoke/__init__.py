"""smartci.smoke - 模块 2B：冒烟执行

PURPOSE: 拉合并产物 → 平台前置加工 → 跑冒烟入口脚本 → 解析 JSON 报告
PATTERN: SmokePipeline 编排 + SmokeReport 解析；流水线步骤由 PlatformConfig 透传到 deploy.py
FOR: smartci CLI 的 smoke 子命令。
"""

from __future__ import annotations
