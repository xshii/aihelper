#!/bin/bash
# 解压硬件团队发布的 golden C rar 包到 golden_c/ 目录
# 用法: ./scripts/extract_golden.sh path/to/golden_release.rar

set -euo pipefail

RAR_FILE="${1:?用法: $0 <golden_release.rar>}"
DEST_DIR="$(cd "$(dirname "$0")/.." && pwd)/golden_c"

if ! command -v unrar &>/dev/null; then
    echo "错误: 需要 unrar 命令。安装: brew install unrar (macOS) 或 apt install unrar (Linux)"
    exit 1
fi

echo "解压 $RAR_FILE → $DEST_DIR"
mkdir -p "$DEST_DIR"
unrar x -o+ "$RAR_FILE" "$DEST_DIR/"
echo "完成。文件列表:"
ls -la "$DEST_DIR"/*.h "$DEST_DIR"/*.so 2>/dev/null || echo "  (未找到 .h/.so 文件)"
