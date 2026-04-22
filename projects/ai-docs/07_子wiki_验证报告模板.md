# 子 Wiki 7：芯片验证精度与性能报告模板

> 本子 Wiki 提供用例级、套件级、回归趋势三种报告模板，作为 Autotest 产出的标准报告格式。
>
> 对应主文档 [第 7 章](./00_主文档_AI验证整体执行流程.md)（结果分析与归档），精度 / 性能判定细则见 [子 Wiki 3](./03_子wiki_业务结果确认.md)，比对工具见 [子 Wiki 2 · 第 7 章](./02_子wiki_中间结果软调.md)。

---

## 目录

1. [模板定位与使用](#1-模板定位与使用)
2. [用例级报告模板](#2-用例级报告模板)
3. [套件级汇总报告模板](#3-套件级汇总报告模板)
4. [回归趋势报告模板](#4-回归趋势报告模板)
5. [字段说明表](#5-字段说明表)
6. [JSON Schema](#6-json-schema)
7. [填写示例](#7-填写示例)
8. [渲染说明](#8-渲染说明)

---

## 1. 模板定位与使用

### 1.1 三种报告的用途

| 报告 | 粒度 | 谁看 | 何时产出 |
|---|---|---|---|
| **用例级** | 单个用例 | 一线定位 | 用例执行完即时产出 |
| **套件级** | 一次回归的多个用例 | 值班 / 测试负责人 | 套件跑完 |
| **回归趋势** | 跨多次回归 | TL / PM / 架构 | 按周 / 月 / 里程碑 |

### 1.2 输出形态

每份报告都按统一 schema（见第 6 章）输出**三种形态**：

- **JSON**：机器可读，Autotest 平台消费（裁决 / 自动切换 / 归档）
- **HTML**：人读，带图表（差异热图、性能趋势）
- **Markdown**：便于贴入问题单 / 聊天工具

### 1.3 填写原则

- 字段 = 必填；字段缺失时 Autotest 报错，不允许静默降级
- 不适用的字段显式填 `N/A`（例如性能用例没有阶段性比数结果）
- 占位符约定 `{{xxx}}`

---

## 2. 用例级报告模板

### 2.1 元信息块

```markdown
# 用例报告：{{case_id}}

| 字段 | 值 |
|---|---|
| 用例 ID | {{case_id}} |
| 用例类型 | {{case_type}}（accuracy / perf / functional / stability）|
| pytest markers | {{markers}} |
| 执行时间 | {{start_at}} ~ {{end_at}}（{{duration_sec}} 秒）|
| **基线标识**  | |
| baseline_id | {{baseline_id}} |
| rtl_commit | {{rtl_commit}} |
| gc_version | {{gc_version}}（GOLDEN 依赖此版本，见子 Wiki 3 · 2.2）|
| 原型版本 | {{prototype_version}} |
| **执行矩阵**（4.4.4）| |
| 运行模型 | {{model}} |
| 运行规格 | {{spec}}（首用例 / 单规格优化 / 规格版本）|
| 业务软件版本 | {{biz_sw_version}}（初级 / 进阶 / 商用 / 原始）|
| 硬件规格 | {{hw_spec}}（少核 / 裁剪 / 全规格 / 跨 DIE）|
| 功耗模式 | {{power_mode}} |
| 执行平台 | {{platform}}（fpga / link / rtl2c / emu）|
| **比数配置** | |
| 比数模式 | {{compare_mode}}（end_to_end / stage_compare）|
| 执行路径 | {{compare_path}}（标准 / 备选，运行时自动选，见子 Wiki 2 · 4.1）|
| **版本指纹 VerFingerPrint** | |
| SDK | {{vfp.sdk}} |
| 平台软件 | {{vfp.platform_sw}} |
| 业务软件 | {{vfp.biz_sw}} |
| CPU 桩 | {{vfp.cpustub}} |
| 软调 | {{vfp.softdbg}} |
```

### 2.2 精度验证结果

**端到端比数用例：**

```markdown
## 精度验证

### 比对摘要（bit 级，见子 Wiki 2 · 7.1）

| 项 | 值 |
|---|---|
| 裁决 | **{{verdict.accuracy}}**（PASS / FAIL）|
| 总元素数 | {{bit_compare.total}} |
| 差异元素数 | {{bit_compare.diff_count}} |
| 差异率 | {{bit_compare.diff_ratio}} |
| 首个差异元素位置 | {{bit_compare.first_diff_pos}} |

### 辅助分析（仅 FAIL 时；PASS 时本节写 N/A）

#### 分 block 比对

- block_size：{{assistive.block.size}}
- 差异 block 数 / 总 block 数：{{assistive.block.diff}} / {{assistive.block.total}}
- 分布模式：{{assistive.block.pattern}}（全局扩散 / 局部集中 / 规律性分布 / 首尾边界）
- 热图：`{{assistive.block.heatmap_path}}`

#### 偏移比对（LCS）

- 最长匹配段长度：{{assistive.lcs.longest_len}}
- 匹配覆盖率：{{assistive.lcs.coverage}}
- 反推偏移量：{{assistive.lcs.offset}}
- 次长匹配段（如存在）：{{assistive.lcs.secondary}}

#### 位域比对

- 主导位域：{{assistive.bit_field.dominant}}（sign / exponent / mantissa）
- 三位域差异占比：sign {{assistive.bit_field.sign_ratio}} / exp {{assistive.bit_field.exp_ratio}} / mantissa {{assistive.bit_field.mantissa_ratio}}
- Top 差异元素详情：`{{assistive.bit_field.topk_path}}`

#### QSNR 比对

- QSNR：{{assistive.qsnr.value}} dB
- 参考级别：{{assistive.qsnr.level}}（极高 / 40+ / 20~40 / <20 / 负值）

### 综合定位建议

{{assistive.locator.suggestion}}
（由工具按 7.10 组合规则产出，仅供参考，最终 root cause 需工程师确认）
```

**阶段性比数用例（额外包含首发散阶段）：**

```markdown
### 首发散阶段（见子 Wiki 2 · 7.12）

| 项 | 值 |
|---|---|
| 首发散阶段 | {{stage.first_diverge.name}} |
| 覆盖层范围 | {{stage.first_diverge.layer_range}} |
| 该阶段 bit 摘要 | 总 {{total}} / 差异 {{diff}} |
| 前一阶段状态 | {{stage.prev.verdict}}（用于判断上游污染）|

### 各阶段比对总览

| 阶段名 | 层范围 | 裁决 | 差异率 | QSNR |
|---|---|---|---|---|
| backbone_out | layer1 ~ layer4.2.relu | {{...}} | {{...}} | {{...}} |
| neck_out | fpn.* | {{...}} | {{...}} | {{...}} |
| head_out | classifier | {{...}} | {{...}} | {{...}} |
```

### 2.3 性能验证结果

```markdown
## 性能验证

### 采集摘要（[PERF] 日志解析，见子 Wiki 3 · 3.1）

| 项 | 值 |
|---|---|
| 裁决 | **{{verdict.perf}}**（PASS / WARN / FAIL）|
| 采样 ROUND 数 | {{perf.rounds}} |
| Warmup 跳过数 | {{perf.warmup_skipped}} |
| 日志源 | `{{perf.log_path}}` |

### 指标对比

| 指标 | 实测（中位数 / P99）| 基线 | 偏差 | 状态 |
|---|---|---|---|---|
| E2E latency (ms) | {{e2e.median}} / {{e2e.p99}} | {{baseline.e2e.mean}} / {{baseline.e2e.p99}} | {{e2e.dev}}% | {{e2e.verdict}} |
| Pure inference latency (ms) | {{pure.median}} / {{pure.p99}} | {{baseline.pure.mean}} | {{pure.dev}}% | {{pure.verdict}} |
| Throughput (qps) | {{qps}} | {{baseline.qps}} | {{qps.dev}}% | {{qps.verdict}} |
| 功耗 (W) | {{power}} | {{baseline.power}} | {{power.dev}}% | {{power.verdict}} |

### 阈值参考

- latency / p99：+5% 内 PASS；+5%~+10% WARN；>+10% FAIL
- throughput：-5% 内 PASS；-5%~-10% WARN；< -10% FAIL

### 平台备注

- 当前平台：{{platform}}
- 性能权威出口：**emu**（FPGA 测性能不准，见 00 · 4.0.1）
- {{若 platform != emu: "本报告仅作功能联跑时的性能参考，最终性能以 emu 结果为准"}}
```

### 2.4 DFX 联合判定

```markdown
## DFX 告警

| 项 | 值 |
|---|---|
| 查询寄存器数 | {{dfx.total}} |
| 告警条目数 | {{dfx.alert_count}} |
| 阻断告警 | {{dfx.blocking_count}} |
| 非阻断告警 | {{dfx.non_blocking_count}} |

### 告警详情

| 寄存器 | 值 | 级别 | 含义 |
|---|---|---|---|
| {{reg}} | {{value}} | {{level}} | {{desc}} |
| ... | | | |

（查询方式与寄存器清单见 [子 Wiki 4](./04_子wiki_DFX告警寄存器查询.md)）
```

### 2.5 综合裁决

```markdown
## 综合裁决

| 维度 | 结果 |
|---|---|
| 精度 | {{verdict.accuracy}} |
| 性能 | {{verdict.perf}} |
| DFX | {{verdict.dfx}}（无告警 / 非阻断 / 阻断）|
| **综合** | **{{verdict.final}}**（PASS / WARN / FAIL）|

判定依据：按 [子 Wiki 3 · 5.2 联合判定表](./03_子wiki_业务结果确认.md) 匹配。

### FAIL 原因摘要（仅 FAIL 时）

{{fail.root_cause_summary}}

### 问题单（FAIL 自动生成）

- 问题单 ID：{{issue_id}}
- 状态：{{issue_status}}
- 负责人（git blame）：{{issue_owner}}
```

### 2.6 日志与附件

```markdown
## 日志与附件

| 项 | 路径 |
|---|---|
| Autotest 主日志 | `{{logs.autotest}}` |
| CPU 桩串口日志 | `{{logs.cpustub}}` |
| [PERF] 日志 | `{{logs.perf}}` |
| dump 目录 | `{{artifacts.dump_dir}}` |
| GOLDEN 引用 | `{{artifacts.golden_ref}}`（GC {{gc_version}}，硬件目标格式）|
| compare 综合报告 | `{{artifacts.compare_report}}`（HTML）|
| DFX 寄存器快照 | `{{artifacts.dfx_snapshot}}` |
| 归档位置 | `{{archive.path}}`（保留策略见 00 · 7.3）|
```

---

## 3. 套件级汇总报告模板

```markdown
# 套件报告：{{suite_id}}

## 汇总

| 项 | 值 |
|---|---|
| 套件 ID | {{suite_id}} |
| pytest markers | {{markers}} |
| 基线 | {{baseline_id}}（GC {{gc_version}}）|
| 平台 | {{platform}} |
| 执行时间 | {{start_at}} ~ {{end_at}}（{{duration_min}} 分钟）|
| 用例总数 | {{total}} |
| PASS | {{pass}}（{{pass_ratio}}）|
| WARN | {{warn}} |
| FAIL | {{fail}} |
| FLAKY | {{flaky}} |
| 跳过 | {{skipped}} |

## 失败列表

| case_id | 失败维度 | 一行原因 | 问题单 |
|---|---|---|---|
| {{case_id}} | 精度 / 性能 / DFX | {{summary}} | [{{issue_id}}]({{issue_url}}) |
| ... | | | |

## FLAKY 列表

| case_id | N 次失败 / 总重试 | 近期 flake rate | 建议 |
|---|---|---|---|
| {{case_id}} | {{retry.fail}} / {{retry.total}} | {{flake_rate}} | quarantine / 复跑 / 不处理 |

## 首用例阻断（如有）

- 首用例 {{first_case_id}} FAIL → 套件后续用例**跳过**（见 02 · 5.5）
- 跳过用例数：{{first_case_blocked_count}}

## 性能趋势（对比前 N 次构建）

| 指标 | 本次中位数 | 上一基线 | 近 5 次 trend |
|---|---|---|---|
| E2E latency | {{this.e2e}} ms | {{prev.e2e}} ms | ↑ / ↓ / flat |
| Throughput | {{this.qps}} | {{prev.qps}} | ↑ / ↓ / flat |

## 下钻

→ [用例级报告索引]({{drill_down_url}})
```

---

## 4. 回归趋势报告模板

```markdown
# 回归趋势：{{period}}（{{start_date}} ~ {{end_date}}）

## 范围

- 基线区间：{{baseline_range}}
- 涉及 RTL commits：{{rtl_commit_list}}
- 执行次数：{{total_runs}}

## PASS 率变化

| 指标 | 当前区间 | 上一区间 | 变化 |
|---|---|---|---|
| 总 PASS 率 | {{current.pass_rate}} | {{prev.pass_rate}} | {{delta.pass_rate}} |
| 精度 FAIL 占比 | {{current.accuracy_fail}} | {{prev.accuracy_fail}} | {{delta}} |
| 性能 FAIL 占比 | {{current.perf_fail}} | {{prev.perf_fail}} | {{delta}} |
| DFX 告警占比 | {{current.dfx_alert}} | {{prev.dfx_alert}} | {{delta}} |
| FLAKY 率 | {{current.flaky_rate}} | {{prev.flaky_rate}} | {{delta}} |

## 性能 drift 预警

| 模型 | 指标 | 累积漂移 | 是否预警 |
|---|---|---|---|
| {{model}} | E2E latency | {{drift}}% | {{alert}} |
| ... | | | |

（漂移判定规则：连续 N 轮同向偏差超阈值，单轮可能 PASS 但累积越线，见 03 · 3.4）

## 失败聚类（按签名）

| 失败签名 | 出现次数 | 涉及用例数 | 建议归因 |
|---|---|---|---|
| {{signature}} | {{count}} | {{case_count}} | {{hint}} |

## Top Bug（问题单聚合）

| 问题单 | 失败次数 | 首次出现 | 状态 |
|---|---|---|---|
| {{issue_id}} | {{count}} | {{first_seen}} | {{status}} |

## 平台对比

| 平台 | 总 PASS 率 | 覆盖用例数 | 备注 |
|---|---|---|---|
| fpga | {{}} | {{}} | 功能主力 |
| emu | {{}} | {{}} | 性能权威出口 |
| link | {{}} | {{}} | 准入闸门 |
| rtl2c | {{}} | {{}} | 波形辅助 |
```

---

## 5. 字段说明表

### 5.1 必填（所有报告共有）

| 字段 | 类型 | 取值规则 | 示例 |
|---|---|---|---|
| `baseline_id` | string | `<version>-<date>-<commit_short>` | `v1.2.3-20260421-a1b2c3d` |
| `rtl_commit` | string | 全 hash 或 short hash | `abc1234` |
| `gc_version` | string | `gc_v<major.minor.patch>` | `gc_v1.2.3` |
| `platform` | enum | `fpga / link / rtl2c / emu` | `fpga` |
| `case_id` | string | 见主文档 5.2 命名规范 | `proto_v1_resnet50_accuracy_001` |
| `verdict.final` | enum | `PASS / WARN / FAIL` | `FAIL` |

### 5.2 精度字段

| 字段 | 类型 | 取值 | 说明 |
|---|---|---|---|
| `verdict.accuracy` | enum | `PASS / FAIL` | 无 WARN（bit 级裁决二态）|
| `bit_compare.total` | int | ≥ 0 | 总元素数 |
| `bit_compare.diff_count` | int | ≥ 0 | 差异元素数 |
| `bit_compare.diff_ratio` | float | [0, 1] | 差异率 |
| `assistive.*` | object | FAIL 时填，PASS 时 `null` | 见 02 · 7.x |

### 5.3 性能字段

| 字段 | 类型 | 取值 | 说明 |
|---|---|---|---|
| `verdict.perf` | enum | `PASS / WARN / FAIL` | 按 03 · 3.4 阈值 |
| `perf.rounds` | int | ≥ 1 | 采样轮次 |
| `perf.metrics[*].median` | float | ≥ 0 | 中位数 |
| `perf.metrics[*].p99` | float | ≥ 0 | P99 |
| `perf.metrics[*].deviation` | float | — | 相对基线偏差（%）|

### 5.4 DFX 字段

| 字段 | 类型 | 取值 | 说明 |
|---|---|---|---|
| `dfx.alert_count` | int | ≥ 0 | 告警条目数 |
| `dfx.blocking_count` | int | ≥ 0 | 阻断告警数（只要 ≥1 即裁决 FAIL）|

---

## 6. JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "CaseReport",
  "type": "object",
  "required": [
    "case_id", "baseline_id", "rtl_commit", "gc_version",
    "platform", "verdict"
  ],
  "properties": {
    "case_id": { "type": "string" },
    "case_type": { "enum": ["accuracy", "perf", "functional", "stability"] },
    "markers": { "type": "array", "items": { "type": "string" } },
    "baseline_id": { "type": "string" },
    "rtl_commit": { "type": "string" },
    "gc_version": { "type": "string" },
    "prototype_version": { "type": "string" },
    "platform": { "enum": ["fpga", "link", "rtl2c", "emu"] },
    "compare_mode": { "enum": ["end_to_end", "stage_compare"] },
    "compare_path": { "enum": ["standard", "fallback"] },
    "biz_sw_version": { "enum": ["初级", "进阶", "商用", "原始"] },

    "verfinger_print": {
      "type": "object",
      "properties": {
        "sdk": { "type": "string" },
        "platform_sw": { "type": "string" },
        "biz_sw": { "type": "string" },
        "cpustub": { "type": "string" },
        "softdbg": { "type": "string" }
      }
    },

    "accuracy": {
      "type": "object",
      "properties": {
        "verdict": { "enum": ["PASS", "FAIL", "N/A"] },
        "bit_compare": {
          "type": "object",
          "properties": {
            "total": { "type": "integer", "minimum": 0 },
            "diff_count": { "type": "integer", "minimum": 0 },
            "diff_ratio": { "type": "number", "minimum": 0, "maximum": 1 },
            "first_diff_pos": { "type": "integer" }
          }
        },
        "assistive": {
          "type": ["object", "null"],
          "properties": {
            "block": { "type": "object" },
            "lcs": { "type": "object" },
            "bit_field": { "type": "object" },
            "qsnr": { "type": "object" }
          }
        },
        "stages": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "name": { "type": "string" },
              "layer_range": { "type": "string" },
              "verdict": { "enum": ["PASS", "FAIL"] },
              "diff_ratio": { "type": "number" }
            }
          }
        },
        "first_diverge_stage": { "type": ["string", "null"] }
      }
    },

    "performance": {
      "type": "object",
      "properties": {
        "verdict": { "enum": ["PASS", "WARN", "FAIL", "N/A"] },
        "rounds": { "type": "integer", "minimum": 1 },
        "warmup_skipped": { "type": "integer", "minimum": 0 },
        "log_path": { "type": "string" },
        "metrics": {
          "type": "object",
          "properties": {
            "e2e_latency_ms": { "$ref": "#/definitions/metric" },
            "pure_inference_ms": { "$ref": "#/definitions/metric" },
            "throughput_qps": { "$ref": "#/definitions/metric" },
            "power_w": { "$ref": "#/definitions/metric" }
          }
        }
      }
    },

    "dfx": {
      "type": "object",
      "properties": {
        "alert_count": { "type": "integer", "minimum": 0 },
        "blocking_count": { "type": "integer", "minimum": 0 },
        "non_blocking_count": { "type": "integer", "minimum": 0 },
        "alerts": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "register": { "type": "string" },
              "value": { "type": "string" },
              "level": { "enum": ["blocking", "non_blocking"] },
              "description": { "type": "string" }
            }
          }
        }
      }
    },

    "verdict": {
      "type": "object",
      "properties": {
        "accuracy": { "enum": ["PASS", "FAIL", "N/A"] },
        "perf": { "enum": ["PASS", "WARN", "FAIL", "N/A"] },
        "dfx": { "enum": ["none", "non_blocking", "blocking"] },
        "final": { "enum": ["PASS", "WARN", "FAIL"] }
      }
    },

    "artifacts": { "type": "object" },
    "issue_id": { "type": "string" },
    "archive_path": { "type": "string" }
  },

  "definitions": {
    "metric": {
      "type": "object",
      "properties": {
        "median": { "type": "number", "minimum": 0 },
        "p99": { "type": "number", "minimum": 0 },
        "baseline": { "type": "number" },
        "deviation_pct": { "type": "number" },
        "verdict": { "enum": ["PASS", "WARN", "FAIL"] }
      }
    }
  }
}
```

---

## 7. 填写示例

### 7.1 精度用例 PASS 示例

```json
{
  "case_id": "proto_v1_resnet50_accuracy_001",
  "case_type": "accuracy",
  "markers": ["accuracy", "cv", "l1"],
  "baseline_id": "v1.2.3-20260421-a1b2c3d",
  "rtl_commit": "a1b2c3d",
  "gc_version": "gc_v1.2.3",
  "prototype_version": "proto_v1",
  "platform": "fpga",
  "compare_mode": "end_to_end",
  "compare_path": "standard",
  "biz_sw_version": "原始",

  "verfinger_print": {
    "sdk": "65010219930822401X",
    "platform_sw": "65010219930822402X",
    "biz_sw": "65010219930822403X",
    "cpustub": "65010219930822404X",
    "softdbg": "65010219930822405X"
  },

  "accuracy": {
    "verdict": "PASS",
    "bit_compare": {
      "total": 1000000,
      "diff_count": 0,
      "diff_ratio": 0.0,
      "first_diff_pos": -1
    },
    "assistive": null,
    "stages": [],
    "first_diverge_stage": null
  },

  "performance": {
    "verdict": "N/A",
    "metrics": null
  },

  "dfx": {
    "alert_count": 0,
    "blocking_count": 0,
    "non_blocking_count": 0,
    "alerts": []
  },

  "verdict": {
    "accuracy": "PASS",
    "perf": "N/A",
    "dfx": "none",
    "final": "PASS"
  }
}
```

### 7.2 精度 FAIL + 辅助分析指向地址错位的示例（关键字段）

```json
{
  "case_id": "proto_v1_resnet50_accuracy_017",
  "accuracy": {
    "verdict": "FAIL",
    "bit_compare": {
      "total": 1000000,
      "diff_count": 999872,
      "diff_ratio": 0.999872,
      "first_diff_pos": 0
    },
    "assistive": {
      "block": {
        "diff_ratio": 0.998,
        "pattern": "全局扩散"
      },
      "lcs": {
        "longest_len": 999872,
        "coverage": 0.999,
        "offset": 128,
        "secondary": null
      },
      "bit_field": {
        "dominant": null,
        "note": "位域差异均匀（因整体偏移，内容本身一致）"
      },
      "qsnr": { "value": -3.4, "level": "负值" }
    },
    "locator_suggestion": "LCS 最长匹配段 ≈ 总长度 + offset=128：高置信度**整体地址/布局错位 bug**；查 DMA 起址、padding、layout 转换"
  },
  "verdict": { "accuracy": "FAIL", "final": "FAIL" }
}
```

---

## 8. 渲染说明

### 8.1 渲染管线

```
比数模块 / DFX 查询 / [PERF] 解析
         │
         ▼
   合并产出 JSON（第 6 章 schema）
         │
         ├──► HTML 渲染（pytest-html / Allure 插件）  → 人读
         ├──► Markdown 渲染（jinja2 模板）           → 贴问题单 / chat
         └──► JUnit XML（pytest 自带）                → CI 消费
```

### 8.2 模板文件位置

- 用例级 HTML 模板：`templates/case_report.html.j2`
- 套件级 HTML 模板：`templates/suite_report.html.j2`
- 趋势报告 HTML 模板：`templates/trend_report.html.j2`
- Markdown 模板：同名 `.md.j2`
- JSON schema：`schemas/case_report.schema.json`

### 8.3 字段缺失策略

- 必填字段缺失 → Autotest 报错终止
- 可选字段缺失 → JSON 里写 `null`；HTML / Markdown 里渲染为 `N/A`
- 不适用字段（如性能用例不跑精度）→ 整块写 `"verdict": "N/A"`，UI 上块状折叠

### 8.4 归档与保留

- 每个报告 JSON + HTML + Markdown 三份一起归档
- 归档路径：`reports/{date}/{build}/{case_id}/`
- 保留策略按主文档 7.3 节
- FAIL 用例的 JSON 长期保留，便于回归趋势和失败聚类分析
