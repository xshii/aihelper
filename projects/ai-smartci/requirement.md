# smartci 仓库需求分析

## 1. 背景与定位

### 1.1 背景
多个团队（当前 2 个，后续可能扩展）协同开发同一硬件产品，需要解决：

- **硬件资源表**由各团队分别维护，最终需合并为一张 XML
- **冒烟用例**需要在 fpga / emu 等仿真平台运行，需对联合产物做平台打包和二进制加工
- 各团队脚本各自为政，维护成本高、不一致性导致事故

### 1.2 smartci 仓库定位
smartci 是一个**独立的工具仓库**，被各团队仓库拉取使用。它统一解决两件事：

1. **硬件资源表合并**：Excel → 团队 XML → 合并 XML
2. **冒烟支撑**：联合打包（多平台）+ 制品仓管理 + 仿真平台前置加工 + 冒烟执行

冒烟支撑进一步拆为**两个解耦的阶段**：
- **构建打包阶段（build）**：合并资源表 + 拉对方产物 + 联合打包 + 上传
- **冒烟执行阶段（smoke）**：拉合并产物 + 前置加工 + 跑冒烟用例

两阶段独立可调用：同一个合并产物可以被多次冒烟，跑冒烟无需重新构建。

### 1.3 设计原则
- **完全统一 + 配置化**：脚本只有一套，团队差异通过配置文件区分
- **smartci 不做构建**：构建是团队仓库的责任，smartci 只做产物后处理；团队构建脚本主动调用 smartci，smartci 不反向触发构建
- **build / smoke 解耦**：构建打包与冒烟执行是两个独立 CLI 命令，互不嵌套
- **XML 是真相源**：资源表以 XML 形式纳入版本管理，Excel 是编辑工具（走 LFS）
- **模板方法扩展平台**：新增仿真平台 = 新增一个 Packager 子类
- **对称权限**：任何团队都可以打合并版本、跑冒烟，无中心化角色
- **快速失败**：所有校验尽早做，问题在本地就暴露

---

## 2. 仓库结构

```
smartci/
├── cli.py                          # 统一 CLI 入口
├── config/
│   ├── artifact_repo.yaml          # 制品仓全局配置（地址/认证/namespace）
│   ├── teams/
│   │   ├── team-a.yaml             # 团队 A 的配置（产物路径、构建信息等）
│   │   └── team-b.yaml
│   ├── platforms/
│   │   ├── fpga.yaml               # fpga 平台的打包参数 + 前置加工脚本
│   │   └── emu.yaml
│   └── schema/
│       └── resource.xsd            # 资源表 XSD
├── resources/                      # 资源表真相源（纳入 git）
│   ├── source/                     # Excel 编辑源（走 git LFS）
│   │   ├── team-a.xlsx
│   │   └── team-b.xlsx
│   ├── team-a.xml                  # 团队 A 的 XML（普通 git）
│   ├── team-b.xml
│   └── final.xml                   # 合并 XML（普通 git）
├── resource_merge/                 # 【模块 1】资源表合并
│   ├── converter/                  # Excel → XML
│   ├── merger/                     # XML → XML（插件式策略）
│   │   └── strategies/
│   └── validator/
├── packaging/                      # 【模块 2A】构建打包
│   ├── intermediate.py             # 平台无关的统一中间产物
│   ├── packager/                   # 平台打包器
│   │   ├── base.py                 # PlatformPackager 抽象基类
│   │   ├── fpga_packager.py
│   │   ├── emu_packager.py
│   │   └── registry.py
│   └── pipeline.py                 # 构建打包流程编排
├── smoke/                          # 【模块 2B】冒烟执行
│   ├── post_process/
│   │   └── runner.py               # 执行平台自定义加工脚本
│   ├── runner.py                   # 调用团队冒烟入口脚本
│   ├── report.py                   # 解析冒烟 JSON 报告
│   └── pipeline.py                 # 冒烟流程编排
├── artifact/                       # 制品仓 client（build/smoke 共享）
│   ├── client.py                   # 封装上传/下载工具
│   └── naming.py                   # 版本命名规则
├── common/                         # 公共模块
│   ├── config_loader.py
│   ├── logging.py
│   └── model/
├── tests/
└── requirements.txt
```

---

## 3. 模块一：硬件资源表合并

### 3.1 核心流程
```
Team A xlsx ──convert──► Team A xml ─┐
Team B xlsx ──convert──► Team B xml ─┼─merge──► Final xml
                                     │
                 (Git 管理,审计源)    └─► (最终交付物)
```

资源表的 XML 与 Excel 都集中在 smartci 仓 `resources/` 下：
- `source/*.xlsx` 走 **Git LFS**（避免历史膨胀，可按策略清理）
- `*.xml`、`final.xml` 走普通 git（可 diff、可 review、可追溯）

改资源表的标准动作：团队改本地 Excel → 跑 `smartci resource convert` → 提 PR（同时更新 xlsx 和 xml）。

### 3.2 功能点

**Excel → XML 转换**
- 每个 Excel 多个 sheet，每个 sheet 对应一类资源
- 所有团队共用一套 schema 和 converter
- 空行和 `#` 开头的注释行忽略
- 转换前做列/类型/枚举校验，错误定位到具体单元格

**XML 合并**
- 按资源类别分派到对应的 `MergeStrategy`
- 策略通过 `@register_strategy` 装饰器自动注册
- 冲突"收集到底"而非立即中止，统一输出报告

**校验**
- 结构校验：基于已有 XSD
- 语义校验：地址范围不重叠、外键引用有效等

**合并策略插件基类**
```python
class MergeStrategy(ABC):
    resource_type: str

    @abstractmethod
    def merge(
        self,
        items_by_team: Dict[str, List[ResourceItem]],
        context: MergeContext,
    ) -> MergeResult: ...
```

### 3.3 CLI
```bash
smartci resource convert --input team-a.xlsx --output team-a.xml --team team-a
smartci resource merge --inputs team-a.xml team-b.xml --output final.xml
smartci resource validate --input final.xml
smartci resource list-strategies
```

---

## 4. 模块二A：构建打包阶段（build）

### 4.1 触发与边界

- 触发方：**团队仓库自己的构建脚本**（make / shell / CI）
- smartci 假设：进入 `smartci build` 时，本地构建已经完成，产物按团队 yaml 的声明落到约定路径
- smartci 不调用 team 的 build 命令、不读 team 的构建日志、不感知 team 的工具链

典型调用方式（以团队 A 的 Makefile 为例）：
```makefile
smoke-package:
	make build
	python smartci/cli.py build \
	  --team team-a \
	  --peer team-b --peer-version latest \
	  --platforms fpga,emu
```

### 4.2 流程
```
1. 合并资源表（可选；--skip-merge 跳过，直接用 resources/final.xml）
2. 读取本地 team-a 产物（按 team-a.yaml 的路径）
3. 从制品仓拉取 team-b 最新产物（按 --peer-version / --peer-commit）
4. 联合打包 → 平台无关中间产物
5. 平台打包 → fpga 包 / emu 包
6. 上传到制品仓（团队产物 + 联合产物，两套都传）
```

### 4.3 产物路径约定
本地构建产物的位置通过**团队配置文件**声明：

```yaml
# config/teams/team-a.yaml
team_id: team-a
artifacts:
  binaries:
    - path: build/output/bin/team-a-core.elf
      type: elf
    - path: build/output/lib/libteam-a.so
      type: shared_lib
  metadata:
    version_file: build/output/VERSION  # 版本号来源
    commit_source: git                  # 从 git 取 commit hash
```

smartci 读取该配置后，按约定路径读取产物。团队构建脚本负责产出到这些路径。

### 4.4 联合打包（平台维度）

**粒度决策**：按**平台维度**打包（各团队产物 + 合并资源表 → fpga 包 / emu 包）。

**理由**：
- 消费侧（冒烟阶段）直接拉"可运行的平台包"，零拼装
- 平台差异（镜像格式、加工脚本）归拢到平台打包器
- 支持局部更新：一方未改时可复用对方历史产物
- 易扩展新平台

**打包流程**：
```
team-a 产物 ─┐
team-b 产物 ─┼─► 联合打包器（平台无关合并）─► 统一中间产物 ─┐
合并资源表 ─┘                                             │
                                                           ├─► fpga 包
                                                           └─► emu 包
```

**联合包内部布局（按团队子目录）**：
```
hw-fpga-v1.2.3-a4f9d0/
├── manifest.json
├── resources/
│   └── final.xml
├── team-a/
│   ├── bin/
│   └── lib/
└── team-b/
    ├── bin/
    └── lib/
```

按团队子目录的好处：
- 不会出现重名冲突（团队各管自己的命名空间）
- 平台前置加工脚本可以按团队路径精准定位文件
- 排查问题时一眼看出哪个团队的二进制

**平台打包器基类（模板方法）**：
```python
class PlatformPackager(ABC):
    platform: str   # "fpga" / "emu"，用于注册

    def package(self, intermediate: IntermediateArtifact, output_dir: Path) -> Path:
        """模板方法：定义总流程"""
        self.pre_package(intermediate)
        content = self.build_package_content(intermediate)
        self.post_package(content)
        return self.finalize(content, output_dir)

    @abstractmethod
    def build_package_content(self, intermediate): ...

    def pre_package(self, intermediate): pass    # 可选钩子
    def post_package(self, content): pass         # 可选钩子
    def finalize(self, content, output_dir): ... # 默认实现：打 tar/zip
```

**子类示例**：
```python
@register_packager
class FpgaPackager(PlatformPackager):
    platform = "fpga"
    def build_package_content(self, intermediate):
        # fpga 特定打包逻辑：bit 文件、配置、资源表
        ...

@register_packager
class EmuPackager(PlatformPackager):
    platform = "emu"
    def build_package_content(self, intermediate):
        # emu 特定打包逻辑
        ...
```

### 4.5 制品仓管理

**配置位置**：smartci 全局配置 `config/artifact_repo.yaml`，所有团队共享同一个制品仓。

```yaml
# config/artifact_repo.yaml
endpoint: https://artifacts.example.com
namespace: hw-product
auth:
  type: env                # 凭证从环境变量读
  user_var: ARTIFACT_USER
  token_var: ARTIFACT_TOKEN
```

**访问方式**：通过已有的二进制工具上传/下载，smartci 封装一层 client。

**两类产物**：
- **团队产物**：每个团队各自上传，供对方在 build 阶段拉取
- **联合产物**：build 阶段产出，供 smoke 阶段拉取

**版本命名规则**：
```
{product}-{platform}-{version}-{commit_short}.{ext}    # 联合产物
{team}-{version}-{commit_short}.{ext}                  # 团队产物

示例：
  hw-fpga-v1.2.3-a4f9d0.tar.gz     （fpga 联合包）
  hw-emu-v1.2.3-a4f9d0.tar.gz      （emu 联合包）
  team-a-v1.2.3-a4f9d0.tar.gz      （团队产物，用于构建模式拉取对方版本）
```

- `version`：来自团队产物的 VERSION 文件
- `commit_short`：git commit 的前 8 位
- 联合产物的 version/commit 采用"最晚的团队产物"作为代表，并在 manifest 中记录所有源
- `latest`：按上传时间，最后上传者获胜（不做并发锁，靠口头协调）

**"拉取对方版本"的指定方式**：
```bash
smartci build \
  --team team-a \
  --peer team-b \
  --peer-version v1.2.3 \
  --peer-commit a4f9d0 \
  --platforms fpga,emu
```
若不指定版本/commit，默认拉对方 `latest`。

**所有联合产物附带 manifest.json**：
```json
{
  "version": "v1.2.3",
  "commit": "a4f9d0",
  "platform": "fpga",
  "built_at": "2026-04-22T10:30:00Z",
  "built_by": "team-a",
  "sources": {
    "team-a": {"version": "v1.2.3", "commit": "a4f9d0"},
    "team-b": {"version": "v1.2.2", "commit": "9c1e23"}
  },
  "resource_table": {"version": "r42", "commit": "b5d7e1"}
}
```

### 4.6 CLI
```bash
# 完整构建打包流程
smartci build \
  --team team-a \
  --peer team-b --peer-version latest \
  --platforms fpga,emu \
  [--skip-merge]                # 不改资源表时跳过 merge
  [--no-upload]                 # 调试用，只打包不上传
```

---

## 5. 模块二B：冒烟执行阶段（smoke）

### 5.1 流程
```
1. 从制品仓拉合并产物（按 --version / --commit / --platform）
2. 平台前置加工（若该平台 yaml 中声明）
3. 调用团队冒烟入口脚本
4. 解析 JSON 报告，输出统一 run-report.json
```

冒烟阶段不依赖团队源码、不依赖本地构建产物，只依赖制品仓 + 平台配置 + 冒烟入口脚本。

### 5.2 平台前置加工

有些平台在运行前需要对二进制做加工（地址转换、格式转换、加签名等）。

**设计**：加工脚本作为**平台配置的一部分**，由 smartci 调用，不内嵌到 Python 代码。

```yaml
# config/platforms/fpga.yaml
platform: fpga
post_process:
  - name: address_remap
    script: scripts/fpga/remap.sh
    args: ["--mode", "smoke"]
  - name: sign
    script: scripts/fpga/sign.py
```

脚本语言任意（Shell / Python），Linux 平台。smartci 负责：
- 按顺序执行
- 注入环境变量（产物路径、工作目录、平台名等）
- 捕获输出，失败即中止

### 5.3 冒烟用例执行

smartci **调用团队约定的冒烟入口脚本**，不内嵌测试框架。

**约定**：
- 入口脚本路径在团队/平台 yaml 里声明（如 `smoke_entry: scripts/smoke/run.sh`）
- 脚本退出前必须往 `$SMARTCI_REPORT_PATH` 写一份 JSON 报告
- 退出码 0 = 全通过；非 0 = 至少一例失败

**JSON 报告格式（最小约定）**：
```json
{
  "platform": "fpga",
  "passed": 12,
  "failed": 1,
  "skipped": 0,
  "duration_sec": 320,
  "cases": [
    {"name": "boot", "status": "pass", "duration_sec": 30},
    {"name": "dma_loopback", "status": "fail", "message": "timeout"}
  ]
}
```

smartci 解析后聚合到统一 `run-report.json`（包含 manifest 信息 + 测试结果 + 耗时分解）。

### 5.4 CLI
```bash
# 完整冒烟流程
smartci smoke \
  --version v1.2.3 --commit a4f9d0 \
  --platform fpga
```

---

## 6. 配置体系

### 6.1 三层配置

| 配置层 | 位置 | 变更频率 | Owner |
|--------|------|----------|-------|
| smartci 全局 | `config/artifact_repo.yaml`、`config/platforms/*.yaml` | 低 | smartci 维护者 |
| 团队配置 | `config/teams/{team}.yaml` | 中 | 各团队自行维护 |
| 运行时参数 | CLI 参数 | 每次运行 | 使用者 |

优先级：**CLI 参数 > 团队配置 > 全局默认**。

### 6.2 团队配置示例
```yaml
# config/teams/team-a.yaml
team_id: team-a
repo_root: ../team-a-repo        # 相对 smartci 的路径
artifacts:
  binaries:
    - path: build/output/bin/team-a-core.elf
      type: elf
    - path: build/output/lib/libteam-a.so
      type: shared_lib
  metadata:
    version_file: build/output/VERSION
    commit_source: git
resource_table:
  excel: resources/source/team-a.xlsx
  xml: resources/team-a.xml
smoke_entry: scripts/smoke/team-a-run.sh   # 可选：团队级冒烟入口
```

### 6.3 平台配置示例
```yaml
# config/platforms/fpga.yaml
platform: fpga
packager: FpgaPackager            # 类名，自动匹配已注册的 packager
post_process:
  - name: address_remap
    script: scripts/fpga/remap.sh
output:
  format: tar.gz
  naming: "hw-{platform}-{version}-{commit_short}"
smoke_entry: scripts/smoke/fpga-run.sh   # 平台级冒烟入口（优先级高于团队）
```

### 6.4 制品仓全局配置
```yaml
# config/artifact_repo.yaml
endpoint: https://artifacts.example.com
namespace: hw-product
tool: artifact-cli              # 已有的二进制工具名
auth:
  type: env
  user_var: ARTIFACT_USER
  token_var: ARTIFACT_TOKEN
```

### 6.5 流水线引擎：复用 dsp-integration/deploy.py

smartci 不重新发明流水线调度。构建打包、冒烟执行、平台前置加工的「按依赖跑一串子进程 + 监听 stdout 关键字 + 跨步骤状态传递」全部复用 `projects/dsp-integration/deploy.py`。

**调用方式**：smartci 把 yaml 配置渲染成临时 manifest.json，然后 subprocess 调用：

```bash
python deploy.py --manifest=/tmp/smartci-work/{run-id}/build.json -y
```

deploy.py 已支持 `--manifest=path` 参数指定非默认路径，向后兼容（默认仍读 `manifest.json`）。

**复用到的能力**：
- 同 `order` task 自动并行（如 fpga 包和 emu 包同时打）
- `keyword` 监听 stdout 早期失败 + 命名组提取（`(?P<x>...)`）→ `#{x}` 跨步骤引用
- `cont_ref` 触发后续 task：长跑进程（仿真器、服务）的协同
- 状态文件 `.deploy.state` 跨运行 PID 追踪
- 变量替换 `${var}` + CLI `--key=value` 覆盖

**platform yaml 直接套 manifest task schema**：
```yaml
# config/platforms/fpga.yaml
post_process:
  - name: address_remap
    usage: scripts/fpga/remap.sh ${pkg_dir}/work --mode smoke
    keyword:
      - {type: success, word: "Remap done"}
      - {type: error,   word: "ERROR"}
smoke_entry:
  usage: scripts/smoke/fpga-run.sh ${pkg_dir}/work --report ${report_path}
  keyword:
    - {type: error,   word: "FATAL"}
    - {type: success, word: "SMOKE COMPLETE"}
```

平台维护者学一次 manifest task 语法，build / smoke / 前置加工三处都用。

**smartci Python 代码相应瘦身**——不实现进程管理 / 关键字监听 / 变量替换 / 并行调度，只保留：
1. 业务模块：`resource_merge` / `packaging.packager` / `artifact.client`
2. `manifest_render.py`：从 yaml + CLI 参数渲染 manifest.json
3. `runner.py`：subprocess 调 deploy.py + 解析退出码 / 收集 run-report

---

## 7. 非功能需求

### 7.1 运行环境
- Python 3.8+
- Linux（仿真平台加工脚本运行环境）；CLI 本体尽量跨平台
- 最小化外部依赖

### 7.2 推荐依赖
| 用途 | 库 |
|------|-----|
| Excel | openpyxl |
| XML | lxml |
| CLI | click |
| 配置 | PyYAML |
| 数据模型 | dataclasses / pydantic |

### 7.3 可观测性
- 分级日志（DEBUG/INFO/WARNING/ERROR），`--verbose` 控制
- 关键步骤打印耗时
- 每次运行输出 `run-report.json`（步骤结果、产物清单、上传记录、冒烟结果）

### 7.4 可测试性
- IO 与逻辑解耦（打包器接受内存数据结构，不直接操作文件）
- Mock 制品仓 client 便于测试
- 每个 Packager / MergeStrategy 必须有单元测试
- 端到端测试：用假产物跑完整 pipeline

---

## 8. CLI 命令总览

| 命令 | 作用 |
|------|------|
| `smartci resource convert` | Excel → 团队 XML |
| `smartci resource merge` | 多团队 XML → 最终 XML |
| `smartci resource validate` | 校验 XML |
| `smartci build` | **构建打包阶段**（merge + 联合打包 + 上传） |
| `smartci smoke` | **冒烟执行阶段**（拉合并产物 + 加工 + 跑冒烟） |
| `smartci artifact list` | 查询制品 |
| `smartci artifact pull` | 下载产物（debug 用） |

辅助命令（少用）：
| 命令 | 作用 |
|------|------|
| `smartci resource list-strategies` | 列出已注册的合并策略 |
| `smartci list-packagers` | 列出已注册的平台打包器 |

---

## 9. 端到端工作流示例

### 场景 A：团队 A 改了代码 + 资源表，想冒烟验证
```bash
# 1. 团队 A 在自己仓库改代码、改 Excel、本地构建
make build

# 2. 触发构建打包
python smartci/cli.py build \
  --team team-a \
  --peer team-b --peer-version latest \
  --platforms fpga,emu

# 3. 跑冒烟（用 build 上传的版本）
python smartci/cli.py smoke \
  --version v1.2.3 --commit a4f9d0 \
  --platform fpga
```

### 场景 B：只想验证已有合并版本
```bash
# 直接跑冒烟，不重打包
python smartci/cli.py smoke \
  --version v1.2.3 --commit a4f9d0 \
  --platform fpga
```

### 场景 C：只改了资源表，不想重新构建代码
```bash
# 团队 A 本地改 Excel 后
python smartci/cli.py resource convert \
  --input resources/source/team-a.xlsx \
  --output resources/team-a.xml \
  --team team-a
# 提交 PR，xlsx (LFS) + xml 一起进 review
```

### 场景 D：fpga 板子有限，多人轮流跑同一个版本
```bash
# 不需要重新构建打包，直接拉同一个合并产物多次冒烟
python smartci/cli.py smoke --version v1.2.3 --commit a4f9d0 --platform fpga
python smartci/cli.py smoke --version v1.2.3 --commit a4f9d0 --platform fpga
```

---

## 10. 待明确事项

以下不影响框架搭建，编码或实际使用前再定：

### 资源表相关
1. 具体的资源类别清单（有哪些 sheet / resource_type）
2. 每类资源的合并规则细节
3. Excel 列规范与枚举值
4. 团队 ID 命名规范

### 冒烟相关
5. 制品仓二进制工具的具体接口（上传/下载命令、错误码）
6. 各团队本地构建产物的具体清单
7. fpga/emu 平台特定的打包细节（需要哪些文件、目录结构）
8. 仿真平台前置加工的具体脚本（各平台团队提供）
9. 冒烟入口脚本的位置与参数（团队 / 平台谁优先）
10. 版本号 `VERSION` 文件的格式约定

### 已对齐（保留作为决策记录）
- ✅ 资源表方案：方案 3（各团队 Excel → XML → 合并 XML）
- ✅ Excel 上库方式：Git LFS
- ✅ XML 物理位置：smartci 仓 `resources/`
- ✅ final.xml 用途：团队构建也消费（merge 必须先于 build）
- ✅ 联合包布局：按团队子目录
- ✅ 制品仓产物：团队产物 + 联合产物两套
- ✅ 制品仓配置：smartci 全局配置
- ✅ 构建触发：团队自行触发，smartci 不反向调用
- ✅ build / smoke 解耦：两个独立顶层命令
- ✅ 冒烟报告格式：自定义 JSON
- ✅ 并发：暂不处理，latest 按上传时间，靠口头协调

---

## 11. 里程碑建议

| 阶段 | 交付物 |
|------|--------|
| M1 | 代码框架 + CLI 骨架（7 条命令）+ 配置体系 + 制品仓 client 接口 |
| M2 | 资源表 convert + merge 可用（含 1-2 个示例 Strategy） |
| M3 | 联合打包器框架 + fpga/emu 两个 Packager |
| M4 | build 流程端到端跑通（含上传） |
| M5 | smoke 流程端到端跑通（含前置加工 + 报告解析） |
| M6 | 补齐所有资源策略 + 语义校验 + 文档 |
