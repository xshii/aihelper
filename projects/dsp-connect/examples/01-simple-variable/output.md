# Expected Output

```
42 (0x0000002A)
```

---

**Why this output:**
- 十进制值 `42` 在前，方便人类阅读
- 十六进制 `0x0000002A` 在后，补齐到类型宽度（uint32 = 8 位 hex）
- 没有变量名前缀——`dsc_read_var` 只返回值，调用者自己加名字
