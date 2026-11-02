# 案例：luci-theme-ctmodem 到底需不需要改

被试包：`luci-theme-ctmodem-26.293.25639~e74b366.apk`（66105 字节，Telegram 渠道分发）

测试机：iStoreOS **25.12.6**（DISTRIB_TARGET `x86/64`，`apk-tools 3.0.5`），LuCI 为 ucode 版

---

## 1. 先纠正一个误判：`ADBd` 不是加密

文件头是 `41 44 42 64` = `ADBd`，整体熵 7.996 bit/B，`file`/`tar`/`unzip` 全都认不出来，
很容易当成「下载坏了」或「被加密了」。

实际上 `ADBd` 是 apk-tools 3.x 的压缩包装：`ADB` + `d`(deflate)。
用 raw deflate 解 4 字节之后就是标准的 ADB 包：

```
ADBd + rawdeflate( "ADB.pckg" + schema=0x676b6370 + blocks )
blocks:
  type 0 (ADB)   元数据，3364 字节
  type 2 (DATA)  × 15，每个文件一块，前 8 字节是 (目录 id, 块序号)，后面是原始内容
```

对照 apk-tools 源码 `src/adb_comp.c`：

```c
case '.':  /* ADB. 未压缩 */ break;
case 'd':  /* ADBd deflate */ ...
case 'c':  /* ADBc + struct adb_compression_spec */ ...
```

## 2. 包的真实内容：纯静态资源，`arch: noarch`

`apk adbdump` 摘要：

```
# ADB block, size: 3364, compat: 0, ver: 0
info:
  name: luci-theme-ctmodem
  version: 26.293.25639~e74b366
  arch: noarch                      ← 已经是通用架构
  license: MIT
  depends: libc
  provides: luci-theme-ctmodem-any
  installed-size: 96479
paths: # 17 items
  etc/uci-defaults/30_luci-theme-ctmodem
  lib/apk/packages/luci-theme-ctmodem.list
  usr/share/ucode/luci/template/themes/ctmodem/{footer,header,sysauth}.ut
  www/luci-static/ctmodem/{cascade.css,logo.svg,menu-ctmodem.js}
  www/luci-static/ctmodem/img/*.{jpg,gif}
```

15 个文件全部是模板 / 样式 / 图片，**零个 ELF、零个 `.so`**。

## 3. 实机安装

```
# apk add --allow-untrusted /tmp/ctmodem.apk
(1/1) Installing luci-theme-ctmodem (26.293.25639~e74b366)
  Executing luci-theme-ctmodem-26.293.25639~e74b366.post-install
OK: 673.1 MiB in 1059 packages

# apk list --installed | grep ctmodem
luci-theme-ctmodem-26.293.25639~e74b366 noarch {...} (MIT) [installed]
```

## 4. 实机渲染

```
uci set luci.main.mediaurlbase='/luci-static/ctmodem'; uci commit luci
/etc/init.d/uhttpd restart

GET /cgi-bin/luci/  ->  200, 3956 bytes
  ctmodem 关键字命中: 4
  错误页关键字: 0
  <link rel="stylesheet" href="/luci-static/ctmodem/cascade.css?v=20261020b">
  <link rel="icon" href="/luci-static/ctmodem/logo.svg" sizes="any">
```

静态资源直接可取（27528 字节 CSS，200）。**主题完整工作。**

## 5. 结论

| 问题 | 答案 |
|---|---|
| 需要为 ARM / MIPS 软路由重新打包吗？ | **不需要**，`noarch` + 无二进制，任何架构都能装 |
| 那你真正会踩的坑是什么？ | ① 24.10 及更老的 **opkg 固件**装不了 v3 包；② 老 **Lua LuCI** 没有 ucode 模板，装上也是白屏 |
| 想在老固件上用怎么办？ | `apk --allow-untrusted extract` 解包 → `build --format ipk` 转 ipk；模板要另写 Lua 版 |

## 6. 让它在「系统 → 语言和界面 → 设计」里可选

装完只解决了“能用”，没解决“能选”：主题包没往 `/etc/config/luci` 写
`config internal 'themes'` 条目，所以下拉里只有 Argon / Bootstrap。

前端逻辑（`resources/view/system/system.js`）：

```js
const th = Object.keys(uci.get('luci','themes') || {}).sort();
for (let t of th) if (t.charAt(0) != '.') o.value(uci.get('luci','themes',t), t);
```

补一条即可：

```sh
uci set luci.themes.Ctmodem='/luci-static/ctmodem'
uci commit luci
```

实测 ubus 数据（就是前端拿到的）：

```json
"themes": {
  "Argon": "/luci-static/argon",
  "Bootstrap": "/luci-static/bootstrap",
  "BootstrapDark": "/luci-static/bootstrap-dark",
  "BootstrapLight": "/luci-static/bootstrap-light",
  "Ctmodem": "/luci-static/ctmodem"
}
```

用 `extras/luci-theme-register.sh` 可以幂等地批量补，并且自带 `header.ut` 存在性检查。
装成 `/etc/uci-defaults/99-luci-theme-register` 后，固件升级也会自动补回来。

## 7. 复现命令
```bash
# 看元数据
apk adbdump luci-theme-ctmodem-*.apk

# 解包（任意 25.x 设备 / 容器）
mkdir -p tree && cd tree && apk --allow-untrusted extract ../luci-theme-ctmodem-*.apk

# 转成 opkg 固件能装的 ipk
python tools/luci_pkg.py build tree -o ctmodem_all.ipk --format ipk \
    --name luci-theme-ctmodem --version 26.293.25639~e74b366 \
    --depends luci-base --desc "CT modem theme (repacked)"
```
