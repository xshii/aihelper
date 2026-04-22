"""Excel → 团队 XML 转换器（坑位）

PATTERN: 单一 ExcelToXmlConverter 类，team 作为构造参数；所有团队共用一套转换逻辑。
FUTURE: 用 openpyxl 读 sheet → 内存 dataclass → lxml 写 XML。
"""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ExcelToXmlConverter:
    team: str

    def convert(self, input_path: Path, output_path: Path) -> None:
        """读 Excel 多 sheet，校验列/类型/枚举，落盘 team XML。

        TODO 实现要点：
        - 空行 + `#` 开头注释行忽略
        - 每个 sheet 对应一类资源
        - 列校验失败时定位到具体单元格（行/列）
        - 共用 schema/resource.xsd
        """
        raise NotImplementedError(
            f"ExcelToXmlConverter.convert 待实现 "
            f"(team={self.team}, input={input_path}, output={output_path})"
        )
