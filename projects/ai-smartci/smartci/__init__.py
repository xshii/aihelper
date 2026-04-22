"""smartci - 硬件资源表合并 + 冒烟支撑

PURPOSE: 统一两个团队（后续可扩展）的资源表合并 + 联合打包/冒烟脚本。
PATTERN: 业务模块（resource_merge / packaging / smoke / artifact）+
         流水线编排（pipeline）+ 通过 runner 委托给 dsp-integration/deploy.py
FOR: 团队成员通过 `python -m smartci` 调用，弱 AI 参照本包模式扩展。
"""


from __future__ import annotations
__version__ = "0.0.1"
