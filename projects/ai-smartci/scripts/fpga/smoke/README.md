# scripts/fpga/smoke/ — FPGA 冒烟入口脚本坑位

冒烟用例的实际触发脚本。由 `config/platforms/fpga.yaml` 里的 `smoke_entry` 引用。

## 契约

入口脚本必须满足：

1. **报告**：退出前往 `$SMARTCI_REPORT_PATH` 写一份 JSON：
   ```json
   {
     "platform": "fpga",
     "passed": 12, "failed": 1, "skipped": 0,
     "duration_sec": 320,
     "cases": [
       {"name": "boot", "status": "pass", "duration_sec": 30},
       {"name": "dma_loopback", "status": "fail", "message": "timeout"}
     ]
   }
   ```
2. **退出码**：0 = 全通过；非 0 = 至少一例失败
3. **stdout 关键字**：建议输出 `SMOKE COMPLETE`（成功）或 `FATAL ...`（早期失败），
   被 deploy.py keyword 监听用于早终止

详见 [requirement.md §5.3](../../../requirement.md)。

## 当前坑位

```
run.sh          # 主入口
```
