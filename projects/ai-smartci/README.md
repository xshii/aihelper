# ai-smartci

硬件产品多团队协作工具。两件事：

1. **硬件资源表合并**：Excel → 团队 XML → 合并 XML
2. **冒烟支撑**：联合打包（多平台）+ 制品仓 + 平台前置加工 + 冒烟执行

详见 [requirement.md](./requirement.md)。

## 快速开始

```bash
pip install -r requirements.txt
python -m smartci --help
```

## 流水线引擎

smartci 不实现流水线调度，复用 `projects/dsp-integration/deploy.py`。
smartci 把 yaml 配置渲染成 manifest.json，subprocess 调用 deploy.py：

```
smartci CLI ──render──> manifest.json ──subprocess──> deploy.py
```

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
│   ├── common/           # 配置加载 / 路径工具
│   ├── resource_merge/   # 模块 1：Excel→XML、合并、校验、策略插件
│   ├── packaging/        # 模块 2A：联合打包 + 平台 packager
│   ├── smoke/            # 模块 2B：冒烟流水线 + 报告解析
│   └── artifact/         # 制品仓 client（ABC）
├── config/               # 配置示例（teams / platforms / artifact_repo）
├── resources/            # 资源表真相源（Excel via LFS / XML in git）
├── manifests/            # deploy.py 清单示例
├── scripts/              # 平台特定脚本坑位（团队提供）
│   ├── fpga/{post_process,smoke}/
│   └── emu/{post_process,smoke}/
├── tests/
└── .vscode/tasks.json    # IDE 常用命令
```

## 周边脚本

`scripts/<platform>/{post_process,smoke}/` 是**坑位**，由各平台/团队提供：

- `post_process/`：冒烟前的二进制加工（地址转换、签名等）
- `smoke/`：冒烟入口脚本，必须往 `$SMARTCI_REPORT_PATH` 写 JSON 报告

具体约定见各目录的 README.md。
