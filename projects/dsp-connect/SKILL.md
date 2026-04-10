---
name: dsp-connect
version: 1.0
difficulty: advanced
---

# Skill: 嵌入式软调框架重写

## Trigger (何时触发)

当用户需要以下任一操作时使用此技能：
- 重写现有 C++ 软调代码为 C
- 分析现有嵌入式调试代码的功能
- 为新硬件适配调试框架
- 验证新旧调试框架的一致性

关键词: dwarf, telnet, softprobe, 软调, 符号调试, 内存查看, ELF, 嵌入式调试

## Input (输入)

- 必需: 现有 C++ 软调代码仓库（或部分代码）
- 必需: dsp-connect demo 代码（本项目 src/）
- 可选: 目标硬件文档（架构、命令协议）
- 可选: 已有的功能清单（inventory.json）

## Process (过程)

1. **盘点阶段** (prompts/discover/)
   - 分析现有代码的入口函数、DWARF 用法、通信层、类型处理、架构代码
   - **识别并标记多余功能**——不是所有代码都需要重写
   - 输出: 结构化功能清单 inventory.json
   - 决策点: 如果清单中 uncertain 项 > 30%，暂停并请人类确认

2. **重写阶段** (prompts/rewrite/)
   - 按 dsp-connect 分层架构逐层重写
   - 只重写 inventory 中标记为 keep 的功能
   - 每层完成后运行该层的单元测试
   - 决策点: 如果某层重写失败 2 次，推倒重来该层（允许）

3. **验证阶段** (prompts/validate/)
   - 对比新旧 API 表面
   - 对比类型覆盖矩阵
   - 对比实际输出结果
   - 输出: 验证报告（GREEN/YELLOW/RED）
   - 决策点: 如果 RED 项 > 0，回到重写阶段修复

4. **适配阶段** (prompts/adapt/) — 按需
   - 为新硬件添加 transport/arch 适配器
   - 注册到工厂
   - 编写适配器测试

## Output (输出)

- 格式: C 代码项目，目录结构同 dsp-connect src/
- 包含:
  - 所有 keep 功能的实现
  - 完整的单元测试
  - 功能清单 inventory.json
  - 验证报告
- 不包含:
  - 标记为 remove 的功能
  - 未经验证的代码

## Quality Criteria (质量标准)

- 所有函数不超过 50 行
- 每层有独立的单元测试
- 编译通过 `-Wall -Wextra -Wpedantic -Werror`
- 验证报告为 GREEN（全部通过）或 YELLOW（有可接受差异）
- 工厂模式正确实现（新 transport/arch 只需加文件，不改核心代码）

## Common Failures (常见失败模式)

| 失败模式 | 症状 | 预防方式 |
|----------|------|----------|
| 1:1 复制 | 重写后代码量与原始相同 | 检查 inventory，确认 remove 项已跳过 |
| 遗漏类型 | 某些 struct/enum 显示为裸字节 | 运行 type coverage check |
| 地址错误 | 读到的值全是 0 或乱码 | 检查 arch adapter 的地址转换 |
| 命令格式错 | transport 连接成功但读写失败 | 对比 discover step 3 的精确命令格式 |
| 工厂未注册 | create 返回 NULL | 检查 register 调用或 constructor 属性 |

## Escalation (升级规则)

以下情况应交给人类处理，不要自行决定：
- inventory 中 uncertain 项涉及安全相关功能
- 现有代码有自定义 DWARF vendor extension
- 目标板的 telnet 命令格式未文档化
- 验证报告有 RED 项且原因不明
