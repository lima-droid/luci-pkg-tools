# dist — 归档件

ctmodem（电信光猫风格）LuCI 主题，两个格式各一份，留着以后折腾。

| 文件 | 大小 | 说明 |
|---|---|---|
| `luci-theme-ctmodem-26.293.25639~e74b366.apk` | 66105 B | **原包**，apk v3（`ADBd` 容器），`arch = noarch`，给 OpenWrt 25.x |
| `luci-theme-ctmodem_26.293.25639~e74b366_all.ipk` | 65904 B | 从原包解出重打的 ipk，`Architecture: all`，给 opkg 固件（≤ 24.10） |

```
d377a3055d7a60be72078433ce08b56df37e543fbd9f524a23d67dc8b6053ddc  luci-theme-ctmodem-26.293.25639~e74b366.apk
ca02b466a773b12aef977528752889d36a0fb493e9825eaa165dbde229616ac3  luci-theme-ctmodem_26.293.25639~e74b366_all.ipk
```

## 安装

```sh
# OpenWrt 25.x（apk）
apk add --allow-untrusted ./luci-theme-ctmodem-26.293.25639~e74b366.apk

# OpenWrt 24.10 及更老（opkg）
opkg install ./luci-theme-ctmodem_26.293.25639~e74b366_all.ipk

# 装完让它在「系统 → 语言和界面 → 设计」里可选
sh extras/luci-theme-register.sh ctmodem Telecom
uci set luci.main.mediaurlbase='/luci-static/ctmodem'
uci commit luci
rm -rf /tmp/luci-indexcache* && /etc/init.d/uhttpd restart
```

## 注意

- **包里只有 ucode 模板**（`/usr/share/ucode/luci/template/themes/ctmodem/*.ut`）。LuCI 25.x 能渲染；
  24.10 的 Lua LuCI 装了也是白屏 —— 这和架构无关，改 `arch` 救不了，得自己补
  `/usr/lib/lua/luci/view/themes/ctmodem/` 的 Lua 视图。
- 包内 `etc/uci-defaults/30_luci-theme-ctmodem` 是空操作（切换主题那行被注释了），不会劫持默认主题。
- 主题版权归原作者；包里标注 `license: MIT`，这里只做归档与格式转换（解包 → 重打 ipk，内容未改）。
- 原始 apk 是签名过的，解包重打的 ipk 不带签名；opkg 默认不校验。

来源：Telegram 渠道分发的第三方主题包，2026-11-02 收到。
实测记录见 [../docs/case-ctmodem.md](../docs/case-ctmodem.md)。
