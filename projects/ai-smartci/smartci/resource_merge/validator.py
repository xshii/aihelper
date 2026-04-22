"""XML 校验器：结构（XSD）+ 语义（地址不重叠、外键有效等）坑位"""

from __future__ import annotations
from pathlib import Path


class XmlValidator:
    def validate(self, xml_path: Path) -> None:
        """先 XSD 结构校验，再语义校验。失败抛异常（类型 TBD）。

        TODO:
        - XSD 基于 config/schema/resource.xsd
        - 语义规则集建议独立成 SemanticRule 子类（可扩展），这里注入一组跑完
        """
        raise NotImplementedError(f"XmlValidator.validate 待实现 (xml={xml_path})")
