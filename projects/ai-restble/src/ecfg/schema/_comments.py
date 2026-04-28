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

from typing import List, Optional

from ruamel.yaml.comments import CommentedMap

_EOL_SLOT = 2
"""ruamel ``ca.items[key]`` 的 4 槽里，EOL（end-of-line）注释固定在 index 2。"""


def trailing_comment(cmap: CommentedMap, key: str) -> Optional[str]:
    """返回 ``cmap[key]`` 的**同行尾随注释**（去掉 ``#`` 和首尾空白）。

    当 key 没有注释 / 注释在下一行（standalone）/ key 不存在时返回 ``None``。
    standalone 注释请走 :func:`subsequent_comments`。

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


def subsequent_comments(cmap: CommentedMap, key: str) -> List[str]:
    """返回**紧跟在 ``cmap[key]`` 之后**的 standalone 注释行（按出现顺序，去 ``#``）。

    ruamel 把 standalone 注释（独占一行的 ``# ...``）挂到前一条 key 的 EOL 槽。
    本函数识别"原始字符串以 ``\\n`` 开头"这一标志，按行拆 ``#`` 并返回。

    >>> from ruamel.yaml import YAML
    >>> yaml = YAML(typ="rt")

    单条 standalone：

    >>> src = 'priority: 0\\n# @range: 0-15\\n'
    >>> doc = yaml.load(src)
    >>> subsequent_comments(doc, "priority")
    ['@range: 0-15']

    多条连续 standalone：

    >>> src = '''priority: 0
    ... # first note
    ... # second note
    ... # @flag: x
    ... '''
    >>> doc = yaml.load(src)
    >>> subsequent_comments(doc, "priority")
    ['first note', 'second note', '@flag: x']

    同行尾随注释**不**被此函数返回：

    >>> doc = yaml.load("priority: 0  # @merge: sum\\n")
    >>> subsequent_comments(doc, "priority")
    []

    同行尾随 + 下一行 standalone 混合（ruamel 把两者合并到一个 value，
    但本函数只返回 standalone 部分）：

    >>> src = '''priority: 0  # @merge: sum
    ... # @range: 0-15
    ... '''
    >>> doc = yaml.load(src)
    >>> subsequent_comments(doc, "priority")
    ['@range: 0-15']

    上面这个 case 的同行尾随仍然可以取到（两者互不干扰）：

    >>> trailing_comment(doc, "priority")
    '@merge: sum'
    """
    raw = _raw_eol(cmap, key)
    if raw is None:
        return []
    # raw 形态：
    #   "\n# A\n# B\n"          —— 纯 standalone（无 EOL）
    #   "  # eol\n# A\n# B\n"   —— EOL + standalone（ruamel 把两者合并）
    #   "  # eol\n"              —— 仅 EOL（无 standalone）
    nl = raw.find("\n")
    if nl < 0:
        return []  # 仅 EOL，无 standalone
    standalone = raw[nl + 1:]
    return [_strip_hash(line) for line in standalone.splitlines() if line.strip().startswith("#")]


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
