"""smartci 全局常量

所有散落的魔鬼字符串/数字集中在这里。其他模块从这里 import，不硬编码。
分组顺序：合并引擎 → XML 读写 → 环境/路径 → deploy.py 协议 → 产物命名 → 流水线。
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
# _write_output 产出 XML 的根/项标签
XML_ROOT_TAG = "merged"
XML_ITEM_TAG = "item"
XML_ENCODING = "utf-8"


# ── 环境变量 ─────────────────────────────────────────────
ENV_ROOT = "SMARTCI_ROOT"
ENV_WORKDIR = "SMARTCI_WORKDIR"
ENV_DEPLOY_PY = "SMARTCI_DEPLOY_PY"
ENV_REPORT_PATH = "SMARTCI_REPORT_PATH"

# 制品仓认证环境变量（默认；可被 artifact_repo.yaml 覆盖）
ENV_ARTIFACT_USER = "ARTIFACT_USER"
ENV_ARTIFACT_TOKEN = "ARTIFACT_TOKEN"


# ── 路径 ─────────────────────────────────────────────────
DEFAULT_WORKDIR_BASE = "/tmp/smartci"
CONFIG_DIR_NAME = "config"
TEAMS_SUBDIR = "teams"
PLATFORMS_SUBDIR = "platforms"
ARTIFACT_REPO_YAML = "artifact_repo.yaml"

# 同仓 monorepo 下 dsp-integration/deploy.py 的相对位置
DEPLOY_PY_RELATIVE = "dsp-integration/deploy.py"


# ── deploy.py 协议 ───────────────────────────────────────
DEPLOY_MANIFEST_FILENAME = "manifest.json"
DEPLOY_MANIFEST_ARG = "--manifest"
DEPLOY_AUTO_YES_ARG = "-y"


# ── 产物命名 ─────────────────────────────────────────────
PRODUCT_DEFAULT = "hw"
PKG_EXT_DEFAULT = "tar.gz"
DEFAULT_ARTIFACT_TOOL = "artifact-cli"


# ── 流水线 ───────────────────────────────────────────────
TIMESTAMP_FORMAT = "%Y%m%d-%H%M%S"
RUN_ID_BUILD_PREFIX = "build-"
RUN_ID_SMOKE_PREFIX = "smoke-"

# CLI 默认值
DEFAULT_LIST_LIMIT = 10


# ── 冒烟报告契约 ────────────────────────────────────────
class CaseStatus:
    """SmokeReport.cases[i].status 的可选值"""
    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"
