# ai-smartci

硬件产品多团队协作工具。两件事：

1. **硬件资源表合并**：Excel → 团队 XML → 合并 XML
2. **流水线编排**：调 `dsp-integration/deploy.py` 跑平台 manifest（打包/冒烟）

详见 [requirement.md](./requirement.md) 和 [PROMPT.md](./PROMPT.md)。

## 快速开始

```bash
pip install -r requirements.txt
python -m smartci --help
```

## 架构

```
smartci CLI
   │
   ├─ resource {convert,merge,validate}   ← XML 合并引擎（Python 业务）
   │
   └─ bundle / smoke                      ← 薄包装：定位 manifest → 调 deploy.py
         │
         ├─ platforms/{plat}/bundle.manifest.json   （打包流水线模板）
         ├─ platforms/{plat}/smoke.manifest.json    （冒烟流水线模板）
         ├─ platforms/_shared/merge.manifest.json   （公共：资源表合并）
         ├─ platforms/_shared/vars.json             （公共静态公参，自动 --vars-file）
         ▼
     dsp-integration/deploy.py            ← 流水线调度引擎（独立可用）
```

**smartci 不重新发明流水线调度**。bundle/smoke 就是把 CLI 参数透传给 deploy.py（`--key=value`），把仓内固化的公参透传为 `--vars-file`。

## 目录

```
ai-smartci/
├── smartci/                          # Python 包（~700 行）
│   ├── cli.py                        # click 入口：3 组命令
│   ├── runner.py                     # run_deploy 函数（~20 行）
│   ├── const.py                      # 全局常量
│   ├── common/paths.py               # 路径/manifest helper
│   └── resource_merge/               # XML 合并引擎（独立业务，~800 行）
├── platforms/                        # 平台自治
│   ├── _shared/
│   │   ├── merge.manifest.json       # 公共：资源表合并
│   │   └── vars.json                 # 公共静态公参（artifact_endpoint 等）
│   ├── fpga/
│   │   ├── bundle.manifest.json      # 打包流水线（fetch + package + upload）
│   │   ├── smoke.manifest.json       # 冒烟流水线（pull + extract + bundle + run）
│   │   ├── bundle/                   # 打包脚本坑位（build.sh 等）
│   │   └── smoke/                    # 冒烟入口脚本坑位（run.sh）
│   └── emu/... 同上
├── scripts/                          # 仓级外部脚本（deploy.py 拷贝落点）
├── resources/                        # 资源表真相源（Excel via LFS / XML in git）
├── tests/                            # pytest + doctest（38 个）
├── PROMPT.md                         # 弱 AI 适配 XML 合并策略/manifest 手册
└── .vscode/tasks.json                # IDE 常用命令
```

## 常用命令

```bash
# 资源表合并
smartci resource merge --inputs resources/team-a.xml resources/team-b.xml --output resources/final.xml

# 打包（合并 + 拉对方 + 打包 + 上传）
smartci bundle --platform fpga --team team-a --peer team-b --peer-version latest
smartci bundle --platform fpga --team team-a --peer team-b --skip-merge   # 跳过公共合并

# 冒烟（拉合并产物 + bundle 脚本 + 跑用例）
smartci smoke --platform fpga --version v1.2.3 --commit a4f9d01234
```

## 变量传递（重要）

| 类型 | 方式 | 位置 |
|---|---|---|
| **动态 CLI 参数**（platform/team/peer/version/commit ...） | `--key=value` 透传给 deploy.py | cli.py 命令行参数 |
| **静态公参**（artifact_endpoint / workdir_base 等） | `--vars-file` 自动附加 | **仓内固化** `platforms/_shared/vars.json` |
| **manifest 私有派生**（work_dir / pkg_dir / out_pkg 等） | 在 manifest 的 `variables` 段用 `${xxx}` 拼接 | 每份 manifest 自己 |

合并优先级（低 → 高覆盖，由 deploy.py 自动处理）：

```
manifest.variables  <  platforms/_shared/vars.json  <  CLI --key=value
```

## deploy.py 落点

smartci 需要 `deploy.py`。优先级：
1. 环境变量 `SMARTCI_DEPLOY_PY`
2. `scripts/deploy.py`（独立部署时拷贝于此）
3. monorepo `../dsp-integration/deploy.py`（开发时 fallback）

详见 [scripts/README.md](./scripts/README.md)。
