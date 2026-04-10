# Discover Chain — 分析现有 C++ 软调代码库

## 目标

在重写之前，先彻底理解现有代码做了什么。产出一份结构化的功能清单（Inventory），
包含每个模块的职责、依赖、接口、以及**是否仍然需要**。

## 前置条件

- 可访问现有 C++ 软调代码仓库
- 已知关键词：dwarf、telnet、ELF
- 有可运行的构建环境（或至少能读代码）

## 链结构

| 步骤 | 文件 | 做什么 |
|------|------|--------|
| 1 | 01-find-entry-points.md | 找到所有入口函数和主要 API |
| 2 | 02-extract-dwarf-usage.md | 盘点 DWARF 相关功能 |
| 3 | 03-map-transport-layer.md | 盘点通信/连接层 |
| 4 | 04-catalog-type-handling.md | 盘点类型解析和格式化 |
| 5 | 05-identify-arch-specifics.md | 盘点架构相关代码 |
| 6 | 06-identify-dead-code.md | 识别多余和废弃功能 |
| 7 | 07-inventory-report.md | 汇总输出结构化清单 |

## 预期产出

一份 JSON 格式的功能清单（schema 见 output-schema.json），包含：
- 每个模块的功能列表
- 每个功能的状态：`keep` / `remove` / `uncertain`
- 依赖关系图
- 重写优先级排序

## ⚠️ 核心原则

**不是所有现有功能都需要保留。** 现有代码可能有：
- 历史遗留的废弃功能
- 过度设计的抽象层
- 从未被调用的代码路径
- 与当前需求不匹配的功能

你的任务不只是"列出所有功能"，而是"判断哪些值得重写"。
