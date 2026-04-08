# Prompt Eval 脚本

每个 prompt 对应一个 eval 脚本，用于验证弱 AI 的产出是否符合要求。

## 用法

弱 AI 按 prompt 操作完后，操作员运行对应的 eval：

```bash
# 验证 prompt 01 的产出（添加 codec）
.venv/bin/python prompts/eval/eval_01_codec.py bfp16

# 验证 prompt 02 的产出（添加算子）
.venv/bin/python prompts/eval/eval_02_op.py beamform

# 验证 prompt 05 的产出（添加 dtype）
.venv/bin/python prompts/eval/eval_05_dtype.py bfp16
```

每个 eval 脚本接受一个参数（新增的名称），自动检查：
- 代码结构是否正确
- 注册是否生效
- 能否正常调用
- 测试是否存在

全部检查通过输出 `EVAL PASSED`，任一失败输出具体原因并 exit 1。
