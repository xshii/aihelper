PYTHON = .venv/bin/python
PIP = .venv/bin/pip
PYTEST = .venv/bin/python -m pytest
RUFF = .venv/bin/ruff
RADON = .venv/bin/radon
VULTURE = .venv/bin/vulture

.PHONY: install dev test test-ut test-it test-st test-cov lint quality smoke check clean ci

# ============================================================
# Layer 0: 一键安装
# ============================================================

install:
	$(PIP) install -e ".[dev]"
	$(PIP) install ruff radon vulture import-linter pybind11

build-golden:
	@echo "=== 编译 golden C++ 绑定 ==="
	mkdir -p src/dsp/golden/build
	cd src/dsp/golden/build && \
		PYBIN=$$(cd ../../../.. && pwd)/.venv/bin/python && \
		cmake .. \
			-Dpybind11_DIR="$$($$PYBIN -c 'import pybind11; print(pybind11.get_cmake_dir())')" \
			-DPYTHON_EXECUTABLE=$$PYBIN \
			-Wno-dev && \
		cmake --build .
	@echo "编译成功: src/dsp/golden/build/_raw_bindings*.so"

# ============================================================
# Layer 1: 开发
# ============================================================

dev: install
	@echo "开发环境就绪。"
	@echo "  make test      — 全部测试"
	@echo "  make test-ut   — 单元测试"
	@echo "  make test-st   — 端到端测试"
	@echo "  make lint      — 代码检查"
	@echo "  make quality   — 复杂度 + 死代码"
	@echo "  make ci        — 全量 CI"

test:
	$(PYTEST) tests/ -v

test-ut:
	$(PYTEST) tests/ -m ut -v

test-it:
	$(PYTEST) tests/ -m it -v

test-st:
	$(PYTEST) tests/ -m st -v

test-cov:
	$(PYTEST) tests/ -v --cov=dsp --cov-report=term-missing

smoke:
	@echo "=== Smoke Test (E2E + 断言) ==="
	$(PYTHON) scripts/smoke_test.py

# ============================================================
# Layer 2: 代码质量
# ============================================================

LINT_IMPORTS = .venv/bin/lint-imports

lint:
	@echo "=== ruff (错误 + 风格) ==="
	$(RUFF) check src/dsp/ --select E,W,F --ignore E501,F401,E402
	@echo "=== import-linter (架构分层) ==="
	$(LINT_IMPORTS)
	@echo "=== prompt 引用校验 ==="
	@$(PYTHON) scripts/check_prompt_refs.py
	@echo "LINT DONE"

quality:
	@echo "=== 圈复杂度 (CC≥10 = 需要重构) ==="
	$(RADON) cc src/dsp/ -n C -s
	@echo ""
	@echo "=== 可维护性指数 (MI<20 = 难维护) ==="
	$(RADON) mi src/dsp/ -n B -s
	@echo ""
	@echo "=== 死代码 ==="
	$(VULTURE) src/dsp/ --min-confidence 80
	@echo ""
	@echo "=== 函数长度 (非空非注释 ≤50 行) ==="
	@$(PYTHON) scripts/check_func_length.py
	@echo ""
	@echo "=== 平均复杂度 ==="
	$(RADON) cc src/dsp/ -a -s 2>&1 | tail -1
	@echo "QUALITY DONE"

# ============================================================
# Layer 3: 全量 CI
# ============================================================

ci: lint quality test smoke
	@echo "CI PASSED"

# ============================================================
# 工具
# ============================================================

check:
	@echo "=== dtype 列表 ==="
	@$(PYTHON) -c "import dsp; print(dsp.core.list_dtypes())"
	@echo "=== 算子列表 ==="
	@$(PYTHON) -c "import dsp; print(dsp.ops.list_ops())"
	@echo "=== 当前模式 ==="
	@$(PYTHON) -c "import dsp; print(dsp.context.get_current_mode())"
	@echo "=== golden C 可用 ==="
	@$(PYTHON) -c "import dsp; print(dsp.golden.is_available())"

clean:
	rm -rf build/ *.egg-info src/*.egg-info output/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
