#!/usr/bin/env python3
"""
4字节反转转换工具，支持单文件或文件夹批量转换。

用法:
    python convert.py <input> <output>                                # 默认8字节对齐
    python convert.py <input> <output> --align 4                      # 4字节对齐
    python convert.py <input> <output> --align 8 --exclude .log .tmp  # 排除指定后缀
"""

import os
import sys


def convert_file(src: str, dst: str, align: int = 8):
    """4字节反转转换，源文件不足对齐时告警并补零"""
    if os.path.exists(dst):
        os.remove(os.path.realpath(dst))

    with (
        open(src, "rb") as fin,
        os.fdopen(os.open(dst, os.O_RDWR | os.O_CREAT, 0o644), "wb") as fout,
    ):
        data = fin.read()
        file_len = len(data)

        if file_len % align != 0:
            pad_len = align - file_len % align
            print(
                f"    ⚠ 文件大小 {file_len} 字节，非{align}字节对齐，补充 {pad_len} 字节"
            )
            data += b"\x00" * pad_len

        for i in range(0, len(data), 4):
            fout.write(data[i : i + 4][::-1])


def convert_dir(src_dir: str, dst_dir: str, excludes: set, align: int = 8):
    """递归转换文件夹"""
    for root, dirs, files in os.walk(src_dir):
        rel = os.path.relpath(root, src_dir)
        out_dir = os.path.join(dst_dir, rel)
        os.makedirs(out_dir, exist_ok=True)

        for name in files:
            if any(name.endswith(ext) for ext in excludes):
                print(f"  ⏭ 跳过: {os.path.join(rel, name)}")
                continue

            src_path = os.path.join(root, name)
            dst_path = os.path.join(out_dir, name)
            convert_file(src_path, dst_path, align)
            print(f"  ✔ {os.path.join(rel, name)}")


def main():
    args = sys.argv[1:]
    if len(args) < 2:
        print(
            "用法: python convert.py <input> <output> [--align 4|8] [--exclude .log .tmp ...]"
        )
        sys.exit(1)

    src, dst = args[0], args[1]

    # 解析 --align
    align = 8
    if "--align" in args:
        idx = args.index("--align")
        align = int(args[idx + 1])
        if align not in (4, 8):
            print("❌ --align 仅支持 4 或 8")
            sys.exit(1)

    # 解析 --exclude
    excludes = set()
    if "--exclude" in args:
        start = args.index("--exclude") + 1
        for a in args[start:]:
            if a.startswith("--"):
                break
            excludes.add(a)

    if os.path.isdir(src):
        print(f"转换文件夹: {src} → {dst} (对齐: {align}字节)")
        if excludes:
            print(f"排除后缀: {excludes}")
        convert_dir(src, dst, excludes, align)
    else:
        convert_file(src, dst, align)
        print(f"✔ {src} → {dst}")


if __name__ == "__main__":
    main()
