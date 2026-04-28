"""ruamel.yaml 注释 API 封装。

把 ruamel 的 ``CommentedMap.ca.items[key]`` 这个 4 槽结构吸收在本模块，
上层 schema loader 只见"字符串或 None / list"。这是 spec §7.1 标记的最大
技术风险点的隔离层。

ruamel 行为（本模块已验证并 doctest 固化）：

- 同行尾随注释 (``key: val  # comment``) → ``ca.items[key][2]``，原始字符串以 ``#`` 开头
- 下一行 standalone 注释 → 挂到**前一条** key 的 ``ca.items[key][2]``，原始字符串以 ``\\n`` 开头
- 多条连续 standalone 注释会合并进同一个 ``CommentToken`` 的 value 里

本模块用 "原始字符串是否以 ``\\n`` 开头" 区分这两种形态。
"""
from __future__ import annotations

from typing import Optional

from ruamel.yaml.comments import CommentedMap

_EOL_SLOT = 2
"""ruamel ``ca.items[key]`` 的 4 槽里，EOL（end-of-line）注释固定在 index 2。"""


def trailing_comment(cmap: CommentedMap, key: str) -> Optional[str]:
    """返回 ``cmap[key]`` 的**同行尾随注释**（去掉 ``#`` 和首尾空白）。

    当 key 没有注释 / 注释在下一行（standalone）/ key 不存在时返回 ``None``。

    >>> from ruamel.yaml import YAML
    >>> yaml = YAML(typ="rt")

    同行尾随注释：

    >>> doc = yaml.load("priority: 0  # @merge: concat(',')\\n")
    >>> trailing_comment(doc, "priority")
    "@merge: concat(',')"

    没注释 → ``None``：

    >>> doc = yaml.load("priority: 0\\n")
    >>> trailing_comment(doc, "priority") is None
    True

    standalone 注释（下一行）不算尾随 → ``None``：

    >>> doc = yaml.load("priority: 0\\n# standalone note\\n")
    >>> trailing_comment(doc, "priority") is None
    True

    一次性多 annotation 注释原样返回（工具上层再拆）：

    >>> doc = yaml.load("priority: 0  # @merge: concat(','); @range: 0-15\\n")
    >>> trailing_comment(doc, "priority")
    "@merge: concat(','); @range: 0-15"

    mapping 值的 key 也能拿（ref 入口那种）：

    >>> src = 'owner:  # @merge: conflict\\n  kind: uart\\n'
    >>> doc = yaml.load(src)
    >>> trailing_comment(doc, "owner")
    '@merge: conflict'

    未知 key 返回 ``None``：

    >>> doc = yaml.load("priority: 0\\n")
    >>> trailing_comment(doc, "nope") is None
    True
    """
    raw = _raw_eol(cmap, key)
    if raw is None or raw.startswith("\n"):
        return None
    return _strip_hash(raw.split("\n", 1)[0])


def _raw_eol(cmap: CommentedMap, key: str) -> Optional[str]:
    """从 ``ca.items[key][2]`` 拿原始字符串（含 ``#`` / ``\\n``）；无 → ``None``。"""
    ca = getattr(cmap, "ca", None)
    if ca is None:
        return None
    entry = ca.items.get(key)
    if not entry or len(entry) <= _EOL_SLOT:
        return None
    token = entry[_EOL_SLOT]
    if token is None:
        return None
    return getattr(token, "value", None)


def _strip_hash(raw: str) -> str:
    """把 ``'  # @merge: sum\\n'`` 或 ``'# foo'`` 归一化为 ``'@merge: sum'`` / ``'foo'``。"""
    return raw.strip().lstrip("#").strip()
