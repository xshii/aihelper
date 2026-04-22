# scripts/fpga/post_process/ — FPGA 前置加工脚本坑位

冒烟前对 FPGA 平台二进制做的加工，由 `config/platforms/fpga.yaml` 里的 `post_process` 列表逐条引用。

## 约定

- 脚本语言任意（Shell / Python），Linux
- 命令行入参由 platform yaml 写明，smartci 透传
- smartci 注入环境变量供脚本读：
  - `SMARTCI_PKG_DIR` — 联合产物解压目录（含 team-a/, team-b/, resources/）
  - `SMARTCI_PLATFORM=fpga`
  - `SMARTCI_VERSION` / `SMARTCI_COMMIT`
- 失败 → 非 0 退出，smartci 触发 fail-fast 中断后续步骤
- stdout 关键字会被 deploy.py keyword 监听（成功/失败信号）

## 当前坑位

```
remap.sh        # 地址转换
sign.py         # 签名（示例）
```

由各团队/平台 owner 实际填入。
