#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证 repack 结果：arch 字段已改、数据段字节未变、apk datahash 仍自洽。"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from luci_pkg import Package  # noqa: E402

ENV = dict(os.environ, PYTHONIOENCODING="utf-8")
FIX = os.path.join(os.path.dirname(HERE), "examples")
OUT = os.path.join(FIX, "out")
os.makedirs(OUT, exist_ok=True)
PY = sys.executable
TOOL = os.path.join(HERE, "luci_pkg.py")


def run(args):
    return subprocess.run(args, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=ENV)


cases = [
    ("luci-theme-ctmodem_26.293_aarch64.ipk", "all"),
    ("luci-theme-ctmodem-26.293_aarch64.apk", "noarch"),
]
for name, want in cases:
    src = os.path.join(FIX, name)
    dst = os.path.join(OUT, name.replace("_aarch64", "_" + want))
    r = run([PY, TOOL, "repack", src, "-o", dst])
    print("== repack %s -> %s" % (name, os.path.basename(dst)))
    print((r.stdout or r.stderr).strip())
    assert r.returncode == 0, "repack 失败"

    a, b = Package(src), Package(dst)
    print("   arch: %s -> %s (期望 %s)" % (a.arch, b.arch, want))
    assert b.arch == want, "arch 未改"
    fa, fb = dict(a.files), dict(b.files)
    assert set(fa) == set(fb), "文件清单变了"
    for k in fa:
        assert fa[k] == fb[k], "文件内容变了: %s" % k
    print("   文件清单与内容: 一致 (%d 个)" % len(fb))
    if b.format == "apk":
        print("   datahash 校验: %s" % ("通过" if b.datahash_ok else "失败"))
        assert b.datahash_ok, "datahash 失效"
        print("   安装脚本保留: %s" % (", ".join(b.scripts) or "无"))
    print()

print("== 负向用例: 含 .so 且不带 --force ==")
src = os.path.join(FIX, "luci-theme-withlib-26.293_aarch64.apk")
dst = os.path.join(OUT, "should_not_exist.apk")
r = run([PY, TOOL, "repack", src, "-o", dst])
print("exit =", r.returncode)
print("\n".join(r.stdout.strip().splitlines()[-2:]))
assert r.returncode == 2 and not os.path.exists(dst)
print("按预期拒绝（exit 2，未生成文件）")

print("\n== 闭环用例: 解包 -> 重新打成 all 包 -> 内容一致 ==")
tree = os.path.join(OUT, "tree")
r = run([PY, TOOL, "extract", os.path.join(FIX, "luci-theme-ctmodem-26.293_aarch64.apk"), "-d", tree])
print((r.stdout or r.stderr).strip())
for fmt in ("ipk", "apk"):
    out = os.path.join(OUT, "rebuilt.%s" % fmt)
    r = run([PY, TOOL, "build", tree, "-o", out, "--format", fmt,
             "--name", "luci-theme-ctmodem", "--version", "26.293.25639~e74b366",
             "--desc", "CT modem theme (repacked, arch independent)"])
    print((r.stdout or r.stderr).strip())
    assert r.returncode == 0
    b = Package(out)
    print("   %s -> arch=%s files=%d datahash=%s" % (fmt, b.arch, len(b.files), b.datahash_ok))
    assert b.arch == ("noarch" if fmt == "apk" else "all")
    src_pkg = Package(os.path.join(FIX, "luci-theme-ctmodem-26.293_aarch64.apk"))
    assert dict(src_pkg.files) == dict(b.files), "闭环后文件内容不一致"

print("\nALL OK")
