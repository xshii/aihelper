# ai-smartci

硬件产品多团队协作工具。两件事：

1. **硬件资源表合并**：Excel → 团队 XML → 合并 XML
2. **冒烟支撑**：联合打包（多平台）+ 制品仓 + 平台 bundle（冒烟前镜像组装）+ 冒烟执行

详见 [requirement.md](./requirement.md)。

## 快速开始

```bash
pip install -r requirements.txt
python -m smartci --help
```

## 流水线引擎

smartci 不实现流水线调度，复用 `dsp-integration/deploy.py`。smartci 把 yaml 配置渲染成 manifest.json，subprocess 调用 deploy.py：

```
smartci CLI ──render──> manifest.json ──subprocess──> deploy.py
```

**独立部署时**把 `deploy.py` 拷到本仓 `scripts/deploy.py`（参见 [scripts/README.md](./scripts/README.md)）；**monorepo 开发时**自动 fallback 到同级 `../dsp-integration/deploy.py`。

直接拿示例清单跑一遍：

```bash
python ../dsp-integration/deploy.py --manifest=manifests/smoke.example.json -y
```

## 目录

```
ai-smartci/
├── smartci/              # Python 包：CLI + 业务模块
│   ├── cli.py            # click 入口
│   ├── runner.py         # 调用 deploy.py
│   ├── manifest_render.py  # 渲染 manifest（Builder + Assembler）
│   ├── const.py          # 全局常量（ConflictKind / 环境变量 / 分隔符 / ...）
│   ├── common/           # 配置加载 / 路径工具
│   ├── resource_merge/   # 模块 1：Excel→XML、合并、校验、策略插件
│   ├── packaging/        # 模块 2A：联合打包 + 平台 packager
│   ├── smoke/            # 模块 2B：冒烟流水线 + 报告解析
│   └── artifact/         # 制品仓 client（ABC）
├── config/               # 全局配置（teams/ + artifact_repo.yaml）
│   ├── artifact_repo.yaml
│   └── teams/{team-a,team-b}.yaml
├── platforms/            # 平台自治目录（config + 脚本一处放）
│   ├── fpga/
│   │   ├── platform.yaml   # 平台配置（packager / package_entry / bundle / smoke_entry）
│   │   ├── package/        # 打包脚本（联合产物 → 平台包）
│   │   ├── bundle/         # bundle 脚本（冒烟前镜像组装：地址转换、签名等）
│   │   └── smoke/          # 冒烟入口脚本
│   └── emu/... 同上
├── scripts/              # 仓级外部脚本（deploy.py 独立部署时拷贝位置）
├── resources/            # 资源表真相源（Excel via LFS / XML in git）
├── manifests/            # deploy.py 清单示例
├── tests/                # pytest + doctest
├── PROMPT.md             # 弱 AI 适配 XML 合并策略的手册
└── .vscode/tasks.json    # IDE 常用命令
```

## 平台脚本契约

`platforms/<plat>/{package,bundle,smoke}/` 是**坑位**，各平台/团队提供：

- `package/`：联合产物 → 平台包（由 `platform.yaml` 的 `package_entry` 引用）
- `bundle/`：冒烟前镜像组装（地址转换、签名、格式转换等；`platform.yaml` 的 `bundle` 列表引用）
- `smoke/`：冒烟入口脚本，必须往 `$SMARTCI_REPORT_PATH` 写 JSON 报告

具体约定见各目录的 README.md。
