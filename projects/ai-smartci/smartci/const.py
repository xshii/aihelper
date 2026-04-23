"""smartci 全局常量 — 集中管理散落的魔鬼字符串/数字。

只保留被真正引用的。合并引擎优先，其次 deploy.py 协议，再之后路径。
"""
from __future__ import annotations


# ── 合并引擎 ─────────────────────────────────────────────
class ConflictKind:
    """MergeConflict.kind 的可选值"""
    CONFLICT = "conflict"
    VALIDATE = "validate"
    FOREIGN_KEY = "foreign_key"
    CROSS_NAME = "cross_name"


# 团队名融合后的分隔符："team-a" + "team-b" → "team-a+team-b"
TEAM_MERGE_SEP = "+"

# 跨表合并 UNION_AS_NEW 策略的表名分隔符："tbl_a" + "tbl_b" → "tbl_a+tbl_b"
CROSS_NAME_SEP = "+"

# RENAME_ON_CONFLICT 的默认前缀连接符："team-b" + "1" → "team-b_1"
RENAME_PREFIX_SEP = "_"


# ── XML 读写 ─────────────────────────────────────────────
XML_ROOT_TAG = "merged"
XML_ITEM_TAG = "item"
XML_ENCODING = "utf-8"


# ── 环境变量 ─────────────────────────────────────────────
ENV_ROOT = "SMARTCI_ROOT"
ENV_DEPLOY_PY = "SMARTCI_DEPLOY_PY"


# ── 路径 ─────────────────────────────────────────────────
PLATFORMS_DIR_NAME = "platforms"       # 仓库根下的平台自治目录（manifest + 脚本）
SHARED_SUBDIR = "_shared"              # 跨平台共享的 manifest（如 merge.manifest.json）
SCRIPTS_DIR_NAME = "scripts"           # 仓级外部脚本（独立部署时 deploy.py 拷进来的位置）
DEPLOY_PY_FILENAME = "deploy.py"

# 同仓 monorepo 下 dsp-integration/deploy.py 的相对位置（fallback）
DEPLOY_PY_RELATIVE = "dsp-integration/deploy.py"


# ── deploy.py 协议 ───────────────────────────────────────
DEPLOY_MANIFEST_ARG = "--manifest"
DEPLOY_AUTO_YES_ARG = "-y"
