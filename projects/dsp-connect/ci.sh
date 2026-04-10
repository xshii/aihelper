#!/bin/bash
# PURPOSE: 本地 CI 脚本 — 配置 → 编译 → 测试，可在任何环境运行
# 用法: ./ci.sh          全量 CI
#       ./ci.sh build    只编译
#       ./ci.sh test     只测试（需先编译）
#       ./ci.sh clean    清理

set -euo pipefail

BUILD_DIR="build"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

step() { echo -e "\n${GREEN}=== $1 ===${NC}"; }
fail() { echo -e "${RED}FAIL: $1${NC}"; exit 1; }

do_clean() {
    step "Clean"
    rm -rf "${PROJECT_DIR}/${BUILD_DIR}"
    echo "done"
}

do_configure() {
    step "Configure (cmake)"
    cmake -B "${PROJECT_DIR}/${BUILD_DIR}" \
          -DCMAKE_BUILD_TYPE=Release \
          -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
          "${PROJECT_DIR}" \
        || fail "cmake configure"
}

do_build() {
    step "Build"
    cmake --build "${PROJECT_DIR}/${BUILD_DIR}" \
        || fail "cmake build"
}

do_test() {
    step "Test (ctest)"
    ctest --test-dir "${PROJECT_DIR}/${BUILD_DIR}" \
          --output-on-failure \
        || fail "tests failed"
}

do_all() {
    do_clean
    do_configure
    do_build
    do_test
    echo -e "\n${GREEN}=== CI PASSED ===${NC}"
}

case "${1:-all}" in
    all)       do_all ;;
    clean)     do_clean ;;
    configure) do_configure ;;
    build)     do_configure; do_build ;;
    test)      do_test ;;
    *)         echo "Usage: $0 [all|clean|configure|build|test]"; exit 1 ;;
esac
