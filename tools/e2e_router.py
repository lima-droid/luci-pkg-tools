#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在真实 OpenWrt 路由上验证「多架构包」能装、能卸、文件到位。

用法:
    set ROUTER_PW=...            # 或 ROUTER_PW_FILE=path
    python tools/e2e_router.py --pkg out/luci-theme-x_noarch.apk \\
        --expect www/luci-static/x/style.css

流程: 探测(架构/包管理器) -> 上传 -> 安装 -> 校验文件 -> 卸载 -> 校验已清理
退出码: 0 全通过, 1 有步骤失败, 2 环境/参数问题
"""
from __future__ import annotations

import argparse
import os
import posixpath
import sys

try:
    import paramiko
except ImportError:
    sys.exit("需要 paramiko: pip install paramiko")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from luci_pkg import Package  # noqa: E402


class Router:
    def __init__(self, host, port, user, password):
        self.c = paramiko.SSHClient()
        self.c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.c.connect(host, port=port, username=user, password=password,
                       timeout=20, banner_timeout=25, auth_timeout=25,
                       look_for_keys=False, allow_agent=False)
        self.sftp = self.c.open_sftp()

    def run(self, cmd, timeout=120):
        _in, out, err = self.c.exec_command(cmd, timeout=timeout)
        o = out.read().decode("utf-8", "replace")
        e = err.read().decode("utf-8", "replace")
        return out.channel.recv_exit_status(), (o + e).strip()

    def put(self, local, remote):
        self.sftp.put(local, remote)

    def close(self):
        try:
            self.sftp.close()
            self.c.close()
        except Exception:
            pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default=os.environ.get("RH", "192.168.100.1"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("RP", "22")))
    ap.add_argument("--user", default=os.environ.get("RU", "root"))
    ap.add_argument("--pkg", required=True, help="要装的包（.ipk / .apk）")
    ap.add_argument("--expect", action="append", default=[],
                    help="安装后应存在的设备路径，可多次给")
    ap.add_argument("--keep", action="store_true", help="装完不卸载")
    a = ap.parse_args()

    pw = os.environ.get("ROUTER_PW")
    if not pw:
        f = os.environ.get("ROUTER_PW_FILE", ".pw")
        if os.path.exists(f):
            pw = open(f, encoding="utf-8").read().strip()
    if not pw:
        return 2

    pkg = os.path.abspath(a.pkg)
    base = os.path.basename(pkg)
    remote = "/tmp/" + base
    fails = []

    r = Router(a.host, a.port, a.user, pw)
    try:
        rc, out = r.run("uname -m; . /etc/openwrt_release 2>/dev/null && echo $DISTRIB_DESCRIPTION")
        print("== 目标机 ==")
        print("   " + out.replace("\n", " | "))
        rc_apk, _ = r.run("command -v apk")
        rc_opkg, _ = r.run("command -v opkg")
        pm = "apk" if rc_apk == 0 else ("opkg" if rc_opkg == 0 else None)
        print("   包管理器: %s" % (pm or "未知"))
        if pm is None:
            return 2

        name = None
        p = Package(pkg)
        name = p.name
        if not name:
            print("包名解析失败")
            return 2
        print("   包: %s %s (arch=%s, format=%s)" % (name, p.version, p.arch, p.format))

        r.put(pkg, remote)
        print("== 上传 ==\n   %s (%d 字节)" % (remote, os.path.getsize(pkg)))

        if pm == "apk":
            rc, out = r.run("apk add --allow-untrusted %s 2>&1" % remote, timeout=180)
        else:
            rc, out = r.run("opkg install %s 2>&1" % remote, timeout=180)
        print("== 安装 (rc=%d) ==\n   %s" % (rc, out.replace("\n", "\n   ")))
        if rc != 0:
            fails.append("install rc=%d" % rc)

        rc, out = r.run("apk info -L %s 2>/dev/null | head -20" % name if pm == "apk"
                        else "opkg files %s 2>/dev/null | head -20" % name)
        print("== 清单 ==\n   " + out.replace("\n", "\n   "))

        for path in a.expect:
            rc, _ = r.run("test -e %s" % path)
            print("   %-55s %s" % (path, "OK" if rc == 0 else "缺失"))
            if rc != 0:
                fails.append("missing " + path)

        rc, out = r.run("rm -rf /tmp/luci-indexcache* /tmp/luci-modulecache/*; "
                        "echo cleared")
        print("== 清缓存 ==\n   " + out)

        if not a.keep:
            rc, out = r.run(("apk del %s 2>&1" if pm == "apk" else "opkg remove %s 2>&1") % name,
                            timeout=120)
            print("== 卸载 (rc=%d) ==\n   %s" % (rc, out.replace("\n", "\n   ")))
            if rc != 0:
                fails.append("uninstall rc=%d" % rc)
            for path in a.expect:
                rc, _ = r.run("test -e %s" % path)
                print("   %-55s %s" % (path, "已清理" if rc != 0 else "残留!"))
                if rc == 0:
                    fails.append("residual " + path)
        r.run("rm -f %s" % remote)
    finally:
        r.close()

    print("\n" + ("PASS" if not fails else "FAIL: " + "; ".join(fails)))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
