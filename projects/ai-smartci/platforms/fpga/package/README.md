# platforms/fpga/package/ — FPGA 打包脚本坑位

联合产物 → FPGA 平台包。由 `platform.yaml` 的 `package_entry` 引用。

## 约定

- 脚本语言任意（Shell / Python），Linux
- 入参：`${intermediate_dir}`（平台无关中间产物目录，含 team-a/、team-b/、resources/final.xml）+ `${output_dir}`（写出 `.tar.gz` 的目录）
- 成功 stdout 含 `PACKAGE OK`（keyword success 信号）
- 失败非 0 退出 + stdout 含 `ERROR`（keyword error 信号）
- smartci 注入环境变量：`SMARTCI_PLATFORM=fpga` / `SMARTCI_VERSION` / `SMARTCI_COMMIT`

## 当前坑位

```
build.sh       # 主入口，生成 hw-fpga-<version>-<commit>.tar.gz
```

---
**替代方案**：如果脚本做不到的复杂逻辑（如精密镜像布局），可用 Python `FpgaPackager` 子类（`smartci/packaging/packager/fpga_packager.py`）作逃生舱。platform.yaml 里 `packager` 字段声明，`package_entry` 留空时 smartci 走 Python 路径。
