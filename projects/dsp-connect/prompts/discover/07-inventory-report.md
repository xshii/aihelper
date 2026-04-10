# Step 7: 汇总输出结构化清单

## Role
你是一个技术项目经理，擅长把分析结果整理成可执行的文档。

## Task
将 Step 1-6 的所有发现**汇总为一份结构化的功能清单（Inventory）**。

## Steps

1. **合并所有发现**
   从 Step 1-6 的输出中提取：
   - 所有模块和功能
   - 每个功能的状态（keep / remove / uncertain）
   - 依赖关系

2. **生成 JSON 格式清单**
   按下面的 schema 输出（参考 output-schema.json）

3. **生成优先级排序**
   重写顺序建议，考虑：
   - 核心功能优先（符号查找 → 内存读写 → 格式化）
   - 低依赖模块优先（util → dwarf → transport → ...）
   - 高使用频率功能优先

4. **生成差异分析摘要**
   对比 dsp-connect demo 框架（参考 `src/` 目录）和现有代码的差异

## Output Format

```json
{
  "project_name": "legacy-softprobe",
  "analysis_date": "YYYY-MM-DD",
  "summary": {
    "total_functions": 0,
    "keep": 0,
    "remove": 0,
    "uncertain": 0,
    "estimated_loc_reduction_percent": 0
  },
  "modules": [
    {
      "name": "dwarf_parser",
      "files": ["path/to/file.cpp"],
      "features": [
        {
          "name": "symbol_lookup",
          "description": "变量名→地址查找",
          "status": "keep",
          "complexity": "high",
          "dependencies": ["elf_loader"],
          "demo_equivalent": "src/dwarf/dwarf_symbols.c",
          "notes": ""
        }
      ]
    }
  ],
  "rewrite_priority": [
    {"order": 1, "module": "util", "reason": "零依赖基础设施"},
    {"order": 2, "module": "dwarf_parser", "reason": "核心数据源"}
  ],
  "removed_features": [
    {
      "name": "feature_name",
      "reason": "废弃/多余/过度设计",
      "impact": "无影响/需确认"
    }
  ]
}
```

## Quality Checklist
- [ ] 每个功能都有明确的 keep/remove/uncertain 状态
- [ ] 每个 remove 都有理由
- [ ] 每个 uncertain 都有需要确认的问题
- [ ] 重写优先级与 dsp-connect 的分层架构对齐
- [ ] demo_equivalent 字段正确指向 dsp-connect 中的对应文件
- [ ] JSON 格式有效
