"""smartci.packaging - 模块 2A：构建打包

PURPOSE: 团队产物 + 合并资源表 → 平台无关中间产物 → 各平台联合包
PATTERN: PlatformPackager ABC（模板方法）+ PackagerRegistry（装饰器注册）
        BuildPipeline 编排 merge / fetch peer / package / upload 四步
FOR: smartci CLI 的 build 子命令。
"""

from __future__ import annotations
# 触发内置 packager 的 @register_packager
from smartci.packaging.packager import fpga_packager as _fpga  # noqa: F401
from smartci.packaging.packager import emu_packager as _emu    # noqa: F401
