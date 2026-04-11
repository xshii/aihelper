#!/bin/bash
# 从 golden_c/ 目录找到最新的 rar 包，解压并创建稳定命名的副本
#
# 用法:
#   ./scripts/extract_golden.sh              # 自动找最新 rar
#   ./scripts/extract_golden.sh path/to.rar  # 指定 rar 文件
#
# 流程:
#   1. 在 golden_c/ 下找最新的 .rar（文件名形如 20260326.rar，按名称倒序）
#   2. 解压到 golden_c/current/（清空旧内容）
#   3. 带时间戳的 .so（如 libgolden_20260326.so）创建软链为 libgolden.so
#   4. 带时间戳的 .h 同理创建软链为不带时间戳的名称

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
GOLDEN_DIR="$PROJECT_DIR/golden_c"
CURRENT_DIR="$GOLDEN_DIR/current"

# --- 确定 rar 文件 ---
if [ $# -ge 1 ]; then
    RAR_FILE="$1"
else
    # 文件名形如 20260326.rar，按名称倒序取最新
    RAR_FILE=$(find "$GOLDEN_DIR" -maxdepth 1 -name "*.rar" -type f \
        | sort -r | head -1)
    if [ -z "$RAR_FILE" ]; then
        echo "错误: golden_c/ 下没有找到 .rar 文件"
        echo "请将硬件团队的 rar 包放到 golden_c/ 目录下，或指定路径:"
        echo "  $0 path/to/golden_release.rar"
        exit 1
    fi
    echo "找到最新 rar: $(basename "$RAR_FILE")"
fi

if [ ! -f "$RAR_FILE" ]; then
    echo "错误: 文件不存在: $RAR_FILE"
    exit 1
fi

# 从 rar 文件名提取时间戳（20260326.rar → 20260326）
TIMESTAMP=$(basename "$RAR_FILE" .rar)
echo "时间戳: $TIMESTAMP"

# --- 检查 unrar ---
if ! command -v unrar &>/dev/null; then
    echo "错误: 需要 unrar 命令"
    echo "  macOS: brew install unrar"
    echo "  Linux: apt install unrar"
    exit 1
fi

# --- 解压到 current/ ---
echo "清空 golden_c/current/"
rm -rf "$CURRENT_DIR"
mkdir -p "$CURRENT_DIR"

echo "解压 $(basename "$RAR_FILE") → golden_c/current/"
unrar x -o+ "$RAR_FILE" "$CURRENT_DIR/"

# --- 如果解压后有同名子目录，提升一层 ---
# 20260326.rar 解压后可能得到 current/20260326/，把内容提到 current/
SUBDIR="$CURRENT_DIR/$TIMESTAMP"
if [ -d "$SUBDIR" ]; then
    echo "发现子目录 $TIMESTAMP/，提升一层"
    find "$SUBDIR" -mindepth 1 -maxdepth 1 -exec mv {} "$CURRENT_DIR/" \;
    rmdir "$SUBDIR" || true
fi

# --- 创建不带时间戳的软链 ---
echo ""
echo "创建稳定命名软链（去除时间戳 $TIMESTAMP）:"

cd "$CURRENT_DIR"

# .h：去时间戳建软链
for f in $(find . -maxdepth 1 -name "*${TIMESTAMP}*.h" -type f); do
    f=$(basename "$f")
    ln -sf "$f" "$(echo "$f" | sed "s/_*${TIMESTAMP}_*/_/;s/_\./\./")"
done

# .so：选文件名最短的那个，去时间戳建软链
SO_FILE=$(find . -maxdepth 1 -name "*.so" -type f -exec basename {} \; | awk '{print length, $0}' | sort -n | head -1 | cut -d' ' -f2-)
[ -n "$SO_FILE" ] && ln -sf "$SO_FILE" "$(echo "$SO_FILE" | sed "s/_*${TIMESTAMP}_*/_/;s/_\./\./")"

echo "软链:"
ls -la "$CURRENT_DIR" | grep "^l"

# --- 校验 ---
echo ""
H_COUNT=$(find "$CURRENT_DIR" -name "*.h" -not -type l | wc -l | tr -d ' ')
SO_COUNT=$(find "$CURRENT_DIR" -name "*.so" -not -type l | wc -l | tr -d ' ')

echo "=== 解压完成 ==="
echo "  .h 文件: $H_COUNT 个"
echo "  .so 文件: $SO_COUNT 个"

if [ "$H_COUNT" -eq 0 ]; then
    echo "  警告: 未找到 .h 文件，请检查 rar 包内容"
fi
if [ "$SO_COUNT" -eq 0 ]; then
    echo "  警告: 未找到 .so 文件，请检查 rar 包内容"
fi

echo ""
echo "文件列表:"
find "$CURRENT_DIR" -type f -o -type l | sort | while read -r f; do
    if [ -L "$f" ]; then
        echo "  $(basename "$f") → $(readlink "$f")"
    else
        echo "  $(basename "$f")"
    fi
done

echo ""
echo "下一步: make build-golden"
