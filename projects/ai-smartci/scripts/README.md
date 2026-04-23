# scripts/ — 仓级脚本存放地

这里放的是**仓级外部脚本**（从别处拷入，smartci 直接 subprocess 调起的那种）。
平台特定脚本不在这里——在 `platforms/{plat}/{package,bundle,smoke}/` 下。

## deploy.py（流水线调度器）

smartci 不自己实现流水线调度，委托给 `dsp-integration/deploy.py`。**独立部署**（smartci 不是 monorepo 的一部分）时，把 `deploy.py` 拷到这里：

```bash
cp <path-to>/dsp-integration/deploy.py scripts/deploy.py
```

之后 `smartci build` / `smartci smoke` 会自动用 `scripts/deploy.py`。

`smartci.common.paths.deploy_py()` 的优先级：

1. 函数参数 override
2. 环境变量 `SMARTCI_DEPLOY_PY`
3. **本仓 `scripts/deploy.py`**（独立部署时）
4. fallback：monorepo `../dsp-integration/deploy.py`（开发时便利）

## 契约

scripts/ 下的脚本应满足：
- 可执行（Shell / Python）
- 命令行参数稳定（smartci 按约定拼命令）
- 不依赖 smartci 仓内相对路径（独立可调）
