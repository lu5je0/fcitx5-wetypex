#!/bin/sh
set -eu

command -v update-desktop-database >/dev/null 2>&1 && \
  update-desktop-database /usr/share/applications >/dev/null 2>&1 || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && \
  gtk-update-icon-cache -q -t /usr/share/icons/hicolor >/dev/null 2>&1 || true

cat <<'EOF'

WeTypeX 已安装。首次使用请依次执行：

  1. 检查包内输入核心（无需下载）：
     fcitx5-wetypex-setup --check

  2. 打开 fcitx5-configtool，将 WeTypeX 添加到当前输入法列表。

  3. 重启 Fcitx5：
     fcitx5 -rd

完整说明：https://github.com/panxuc/fcitx5-wetypex#首次设置
EOF
