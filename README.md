# LuCI 主题包：跨架构 / 跨固件 工具箱

判断一个 OpenWrt LuCI 主题包**到底会不会被架构卡住**，以及在真的卡住时怎么改包。
配套三个脚本：`inspect` / `repack` / `extract` + `build`，外加一个真机安装验证器。

> 实测结论（见 [docs/case-ctmodem.md](docs/case-ctmodem.md)）：
> `luci-theme-ctmodem-26.293.25639~e74b366.apk` **本来就是 `noarch`**，包内 15 个文件全是
> CSS / JS / 图片 / ucode 模板，没有任何 ELF；在 x86_64 iStoreOS 25.12.6 上直接装好并渲染成功。
> **主题不需要为多架构做什么改造** —— 真正会挡人的是固件包格式和 LuCI 版本。

---

## 1. 先认清：三种包格式

| 格式 | 谁在用 | 结构 | 架构字段在哪 |
|---|---|---|---|
| `ipk` | opkg，OpenWrt ≤ 24.10 | gzip(tar){ `debian-binary`, `control.tar.gz`, `data.tar.gz` } | `control` 里 `Architecture:` |
| `apk` v2 | Alpine / apk-tools 2.x | gzip( tar[`.SIGN.*`] + tar[`.PKGINFO`] + tar[数据] ) | `.PKGINFO` 里 `arch =` |
| `apk` v3 | **OpenWrt 25.x，apk-tools 3.x** | `ADB.`/`ADBd`/`ADBc` 容器 → `ADB.pckg` + 若干块（ADB 元数据 / SIG / DATA×N） | ADB 元数据里，用 `apk adbdump` 看 |

三条容易被忽略的事实：

1. **`arch` 跟 CPU 无关，只跟「包里有没有编译产物」有关。** 纯资源的包写 `noarch`（ipk 写 `all`）就能装在任何架构上。
2. **apk-tools 3.0.5 不认 v2 包**（实测报 `unexpected end of file`）。给 25.x 造包必须用 v3。
3. `ADBd` 只是 deflate 包装，`xxd` 看着像随机数据 —— 别把它当成加密或损坏（我一开始就误判过）。

## 2. 判断你手上的包是哪种

```bash
python tools/luci_pkg.py inspect 主题.apk
```

- `ipk` / `apk v2`：打印包名、版本、arch、依赖、文件清单，并扫描 ELF/`.so`；发现架构相关文件时 `repack` 会拒绝。
- `apk v3`：直接告诉你「这是 ADB 容器，用 `apk adbdump` / `apk extract`」。

```bash
apk adbdump 主题.apk | head -30     # 看 info: 段里的 arch / depends
```

## 3. 三种改法

### A. 只改 arch 字段（ipk / apk v2）

```bash
python tools/luci_pkg.py repack 主题.apk -o 主题_noarch.apk   # apk → noarch
python tools/luci_pkg.py repack 主题.ipk -o 主题_all.ipk      # ipk → all
```

apk 改完签名失效，装的时候要 `apk add --allow-untrusted`；ipk 侧 opkg 默认不验签。

### B. 解包重组（推荐，能顺手修依赖）

```bash
# ipk / apk v2
python tools/luci_pkg.py extract 主题.apk -d tree/
# apk v3（OpenWrt 25.x 自带 apk，任何一台 25.x 设备或容器都行）
mkdir -p tree && cd tree && apk --allow-untrusted extract ../主题.apk

# 重打包
python tools/luci_pkg.py build tree/ -o 主题_all.ipk --format ipk \
    --name luci-theme-xxx --version 1.0.0 --depends "luci-base"
```

`build` 会重算 `datahash`、生成干净的 control、并把 `tree/_luci_pkg_control/post-install` 映射成
ipk 的 `postinst` / apk 的 `.post-install`。

### C. 包里真有 `.so` / Go 二进制

`inspect` 会明确列出来。此时改字段只能「装得上」，跑起来会炸。选项按性价比排序：

1. 找作者要 `PKGARCH:=all` 的重发版；
2. 判断它是不是可选增强 —— 删掉 `.so` 看主题是否照常工作；
3. 用 ucode/Lua 重写那部分功能（LuCI 25.x 模板是解释执行的，天然跨架构）；
4. `qemu-user-static` + `binfmt_misc` 兜底（慢，且吃内核支持，不推荐）。

## 4. 让主题出现在「系统 → 语言和界面 → 设计」下拉

这是第三方主题最常见的缺口：包只管装文件，**没人往 `/etc/config/luci` 里写主题条目**，
所以 LuCI 的下拉里只有 Argon / Bootstrap。

LuCI 25 的前端代码（`/www/luci-static/resources/view/system/system.js`）就是遍历
`config internal 'themes'` 的每个 option —— key 当显示名，value 当 mediaurlbase：

```js
const th = Object.keys(uci.get('luci','themes') || {}).sort();
for (let t of th) if (t.charAt(0) != '.') o.value(uci.get('luci','themes',t), t);
```

所以补一条即可，[extras/luci-theme-register.sh](extras/luci-theme-register.sh) 封装了这件事：

```sh
# 扫描 /usr/share/ucode/luci/template/themes/* 补齐所有未注册主题（幂等）
sh extras/luci-theme-register.sh
# 或者只注册一个 + 自定义显示名
sh extras/luci-theme-register.sh ctmodem "CTModem ONT"
```

实测输出：

```
已注册：Argon -> /luci-static/argon
已注册：Bootstrap -> /luci-static/bootstrap
注册：Ctmodem -> /luci-static/ctmodem
已 uci commit luci（刷新页面即可在「设计」里选到）
```

想升级后自动补：

```sh
cp extras/luci-theme-register.sh /etc/uci-defaults/99-luci-theme-register
chmod +x /etc/uci-defaults/99-luci-theme-register
```

（脚本会检查 `header.ut` 是否存在 —— 没有 `header.ut` 的主题即使注册了，LuCI 也渲染不出来。）

## 5. 在真机上验证

```bash
pip install paramiko
set ROUTER_PW=...            # 或用 ROUTER_PW_FILE 指向一个只放密码的文件
python tools/e2e_router.py --pkg out/主题.apk \
    --expect /www/luci-static/xxx/style.css \
    --expect /usr/share/ucode/luci/template/themes/xxx/header.ut
```

它会：探测目标机架构与包管理器 → 上传 → 安装 → 校验文件 → 清 LuCI 缓存 → 卸载 → 校验无残留，
最后打印 `PASS` / `FAIL`。本轮就是用它 + 手工 `uci set luci.main.mediaurlbase` 完成验证的。

## 6. 真正会挡住「多固件」的两件事

**包格式**：给 24.10 及更老的 opkg 固件，v3 包永远装不上，得转 ipk（§3B）。
反过来也一样，25.x 装不了 ipk。

**LuCI 版本**：25.x 是 ucode 模板（`/usr/share/ucode/luci/template/themes/<t>/*.ut`），
24.10 及更老是 Lua 视图（`/usr/lib/lua/luci/view/themes/<t>/`）。
只带 `.ut` 的主题在老固件上「装得上但白屏」—— 这个不是架构问题，也不是改 arch 能救的。

## 7. 依赖别照抄

闭源包常见 `Depends: luci-app-xxx, kmod-xxx`，换固件后包名不存在，装主题直接失败，报错还像架构问题。
主题留 `luci-base` 就够（老固件可能要 `luci-compat`）；`kmod-*` 一律删。

## 8. 装完必做

```sh
rm -rf /tmp/luci-indexcache* /tmp/luci-modulecache/*
uci set luci.main.mediaurlbase='/luci-static/<theme>'
uci commit luci
/etc/init.d/uhttpd restart
```

## 9. 仓库内容

```
tools/luci_pkg.py       inspect / repack / extract / build（ipk + apk v2；v3 识别并给指引）
tools/e2e_router.py     真机装/卸/校验（paramiko）
tools/make_fixtures.py  造测试包
tools/verify.py         回归：改 arch、datahash、拒 .so、解包重组
extras/luci-theme-register.sh  把已装主题补进「系统 → 设计」下拉
docs/case-ctmodem.md    本次实测：adbdump 摘录、安装日志、渲染校验
.github/workflows/ci.yml  Python 3.10 / 3.12 跑回归
```

本地跑：

```bash
python tools/make_fixtures.py && python tools/verify.py   # 应输出 ALL OK
```

## 10. 限制

- 不重签：改过的 apk 只能 `--allow-untrusted` 装；要干净签名请用 `abuild-sign`。
- v3 只做识别，解包交给 `apk extract`（重写一个 v3 writer 成本高、且必须跟着 apk-tools 版本走）。
- `build` 不解析依赖树，`--depends` 手填。

License: MIT
