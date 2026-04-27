# prompts/

各 Phase 的 prompt 链根目录。Phase 0 暂无独立 prompt 文件（直接产出代码）。

后续结构：

```
prompts/
├── phase1/
│   ├── 01-loader.md
│   ├── 02-indexer.md
│   ├── 03-ref-resolver.md
│   ├── 04-aggregator.md
│   ├── 05-validator.md
│   └── 06-yaml-writer.md
├── phase2/
│   └── ...
└── phase3/
    └── ...
```

每个 prompt 文件遵循仓库 CLAUDE.md 第 3.1 节的 PROMPT.md 模板（Role / Task / Context / Rules / Steps / Output / Examples / Checklist / Edge Cases）。
