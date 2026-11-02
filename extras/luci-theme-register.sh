#!/bin/sh
# luci-theme-register.sh — 让已安装的 LuCI 主题出现在「系统 → 语言和界面 → 设计」下拉里
#
# 原理：luci-mod-system 的 Design 下拉是遍历 /etc/config/luci 里
#       config internal 'themes' 段的每个 option，key 当显示名、value 当 mediaurlbase。
#       主题包只装了文件、没写这个段，所以下拉里看不到。
#
# 用法：
#   sh luci-theme-register.sh              # 扫描所有已安装主题，补注册
#   sh luci-theme-register.sh ctmodem      # 只注册指定主题
#   sh luci-theme-register.sh ctmodem "CTModem ONT"   # 指定显示名
#
# 幂等：已注册过（value 相同）就不会重复写。
# 装成 uci-defaults 就在升级后自动补：cp 到 /etc/uci-defaults/99-luci-theme-register

THEMES=/usr/share/ucode/luci/template/themes
STATIC=/www/luci-static
CHANGED=0

ucfirst() {
	printf '%s\n' "$1" | awk '{ print toupper(substr($0,1,1)) substr($0,2) }'
}

register() {
	name=$1
	label=${2:-$(ucfirst "$name")}
	base="/luci-static/$name"

	[ -d "$THEMES/$name" ] || { echo "跳过 $name：没有模板目录 $THEMES/$name"; return; }
	[ -f "$THEMES/$name/header.ut" ] || { echo "跳过 $name：缺 header.ut，LuCI 渲染不了"; return; }
	[ -d "$STATIC/$name" ] || echo "注意：$STATIC/$name 不存在，样式/图片可能加载失败"

	for key in $(uci -q show luci.themes 2>/dev/null | sed -n 's/^luci\.themes\.\([^.=]*\)=.*/\1/p'); do
		val=$(uci -q get "luci.themes.$key")
		if [ "$val" = "$base" ]; then
			echo "已注册：$key -> $base"
			return
		fi
		if [ "$key" = "$label" ]; then
			echo "冲突：$label 已被 $val 占用，改用 $name"
			label=$name
		fi
	done

	uci set "luci.themes.$label=$base"
	echo "注册：$label -> $base"
	CHANGED=1
}

if [ $# -gt 0 ]; then
	register "$1" "$2"
else
	for d in "$THEMES"/*; do
		[ -d "$d" ] || continue
		register "$(basename "$d")"
	done
fi

if [ "$CHANGED" = 1 ]; then
	uci commit luci
	echo "已 uci commit luci（刷新页面即可在「设计」里选到）"
else
	echo "无需改动"
fi
