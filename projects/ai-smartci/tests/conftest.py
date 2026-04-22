"""pytest 共享 fixture

保持最少样板：只放跨 test 文件用到的 fixture。
"""

from __future__ import annotations
from pathlib import Path
from typing import Dict, List

import pytest

from smartci.resource_merge.strategies.base import ResourceItem

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixture_dir() -> Path:
    return FIXTURE_DIR


@pytest.fixture
def sample_items_by_team() -> Dict[str, List[ResourceItem]]:
    """两个团队各定义 3 条 irq，第二条 id 冲突用于 rename/冲突测试。"""
    return {
        "team-a": [
            ResourceItem(team="team-a", attrs={"irq_id": "1", "handler": "h_a1"}),
            ResourceItem(team="team-a", attrs={"irq_id": "2", "handler": "h_a2"}),
        ],
        "team-b": [
            ResourceItem(team="team-b", attrs={"irq_id": "1", "handler": "h_b1"}),
            ResourceItem(team="team-b", attrs={"irq_id": "3", "handler": "h_b3"}),
        ],
    }
