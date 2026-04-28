# examples/

Runnable demo 资产。

## 文件

- **`legacy-sample.xml`** — 一份 legacy XML 样本（mini SoC 配置），适合直接喂给
  `ecfg unpack` / `ecfg scaffold` 体验 round-trip 流程
- **`tables/Interrupt.yaml`** — 带 TEMPLATE 块的 schema 示例表（merge-spec 风格，
  演示三区域 + 6 种 merge + ref 关联），喂给 schema/loader 看 schema 注解长啥样

## 30 秒上手：legacy XML round-trip

```bash
# 1. XML → YAML 文件树
ecfg unpack examples/legacy-sample.xml /tmp/sample-tree

# 2. 看一眼拆出来什么
tree /tmp/sample-tree

# 3. 拼回 XML，验证字节级一致
ecfg pack /tmp/sample-tree -o /tmp/round.xml
diff examples/legacy-sample.xml /tmp/round.xml   # 应该无输出

# 4. 顺手生成 schema scaffold（约束/FK 占位，后续手动填）
ecfg scaffold examples/legacy-sample.xml -o /tmp/sample-tree
ls /tmp/sample-tree/template/
```

## 30 秒上手：merge-spec yaml 解析

```python
from pathlib import Path
from ecfg.schema.loader import load_table_schema

schema = load_table_schema(Path("examples/tables/Interrupt.yaml"))
print(f"index: {schema.index_fields}")
print(f"attributes: {list(schema.attribute_fields.keys())}")
for name, fs in schema.attribute_fields.items():
    print(f"  {name}: merge={fs.merge_rule!r} range=[{fs.range_lo}, {fs.range_hi}]")
```

## 完整 fixture 库

`tests/fixtures/xml/valid/` 下有 4 套梯度 fixture（minimal / empty_table / hex_widths /
multi_runmode），跟 unpack/pack/scaffold round-trip 测试一一对应，可作扩展时的参考样例。
