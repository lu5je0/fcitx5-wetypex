# 配置参考

WeTypeX 的独立设置窗口与 Fcitx5 自带配置页共用：

```text
${XDG_CONFIG_HOME:-$HOME/.config}/fcitx5/wetypex.json
```

在 Fcitx5 配置工具中选择 WeTypeX 的“配置”，可以编辑输入方式、外观、设备同步和全部快捷键。修改后插件会重新加载输入后端。

## 输入

- 输入方式：全拼、七种双拼、三种五笔。
- 智能拼写：启用原版纠错候选。
- 表情和颜文字：控制原版 emoji、颜文字与符号候选。
- 默认语言：激活输入法时进入中文或英文。
- 模糊拼音：原版 19 组模糊音可独立开关。
- 单机模式：禁止云候选和设备同步相关联网。

默认推荐标准 Unicode Emoji，例如输入 `hhh` 会出现 😂。
“微信表情文字”默认关闭；手动开启后，原版核心会优先推荐 `[破涕为笑]`
等微信专用文字标记，适合需要这些标记的聊天场景。

## 模糊音设置

运行 `fcitx5-wetypex-settings`，在“输入”页面找到“模糊拼音”，点击“设置...”后分别勾选需要的音组。也可以在 Fcitx5 配置工具中选中 WeTypeX，打开其配置页。默认 19 组全部关闭，图形设置保存后会自动重载插件。

手工编辑 `wetypex.json` 时，这些开关都位于 JSON 顶层，使用布尔值。将需要的项合并到现有配置，例如：

```json
{
  "fuzzy_nl": true,
  "fuzzy_z_zh": true,
  "fuzzy_c_ch": true,
  "fuzzy_s_sh": true,
  "fuzzy_in_ing": true,
  "fuzzy_en_eng": true
}
```

手动修改前备份配置，修改后重新加载或重启 Fcitx5。

| 音组 | JSON 键 |
| --- | --- |
| n/l | `fuzzy_nl` |
| r/l | `fuzzy_rl` |
| h/f | `fuzzy_hf` |
| g/k | `fuzzy_gk` |
| an/ang | `fuzzy_an_ang` |
| ian/iang | `fuzzy_ian_iang` |
| uan/uang | `fuzzy_uan_uang` |
| c/ch | `fuzzy_c_ch` |
| s/sh | `fuzzy_s_sh` |
| z/zh | `fuzzy_z_zh` |
| hui/fei | `fuzzy_hui_fei` |
| en/eng | `fuzzy_en_eng` |
| in/ing | `fuzzy_in_ing` |
| on/ong | `fuzzy_on_ong` |
| huang/wang | `fuzzy_huang_wang` |
| un/ong | `fuzzy_un_ong` |
| un/iong | `fuzzy_un_iong` |
| an/ai | `fuzzy_an_ai` |
| eng/ong | `fuzzy_eng_ong` |

## 配置与数据位置

以下为未设置 XDG 环境变量时的默认位置：

| 内容 | 位置 |
| --- | --- |
| WeTypeX 全部输入、模糊音与快捷键设置 | `~/.config/fcitx5/wetypex.json` |
| Fcitx5 已添加的输入法与分组 | `~/.config/fcitx5/profile` |
| Fcitx5 全局设置 | `~/.config/fcitx5/config` |
| 候选窗外观 | `~/.config/fcitx5/conf/classicui.conf` |
| 账户身份与配对状态 | `~/.local/share/fcitx5-wetypex/account/` |
| 个人词库、常用语与同步状态 | `~/.local/share/fcitx5-wetypex/state/` |
| 用户覆盖的运行时 | `~/.local/share/fcitx5-wetypex/runtime/` |
| 用户覆盖的界面资源与主题 | `~/.local/share/fcitx5-wetypex/ui/`、`~/.local/share/fcitx5/themes/wetypex-*/` |
| AI、语音临时数据 | `~/.local/share/fcitx5-wetypex/ai/`、`~/.local/share/fcitx5-wetypex/state/voice/` |
| 更新缓存 | `~/.cache/fcitx5-wetypex/updates/` |

Nix profile 安装的默认核心、词典和界面资源可从
`~/.nix-profile/share/fcitx5-wetypex/{runtime,ui}/` 访问，实际位于 `/nix/store`。
源码中的 `runtime/asset.json` 只记录独立 Release 资源包的地址和校验和；资源在构建时下载，个人配置和词库不会写入这些只读资源。
设置 `XDG_CONFIG_HOME`、`XDG_DATA_HOME` 或 `XDG_CACHE_HOME` 后，上述用户目录随之变化。

## 外观

- 候选字号：10–18。
- 每页候选：3–9，默认 6 个；编号与候选词之间保留一个空格。
- 排列方式：横排或竖排。
- 候选框固定在拼音起始位置：默认开启，同一轮拼音追加字母时不向右移动；
  在“外观”页关闭后恢复跟随光标，也可将 `preedit_cursor_at_beginning` 设为 `false`。
- 主题：跟随系统、浅色、深色。

外观设置会更新 Fcitx5 Classic UI 的 WeTypeX 主题项。其他输入法共用同一个 Classic UI 时，主题切换也会影响其候选窗口。

## 快捷键

未在组字时，`Ctrl+b` 及随后的一次按键直接传给应用，支持 tmux 的
`Ctrl+b` → `x` 等前缀命令；命令键释放后恢复正常输入。切换输入框或重置输入法会清除待处理的前缀。

快捷键使用 Fcitx5 原生 `Key` / `List|Key` 类型，可在系统配置页直接捕获。默认值包括：

| 操作 | 默认按键 |
| --- | --- |
| 中英文切换 | `Shift` |
| 中英文标点 | `Ctrl + .` |
| 简繁切换 | 默认关闭，预设 `Ctrl + Shift + F` |
| 全半角切换 | 默认关闭，预设 `Shift + Space` |
| 候选翻页 | `-` / `=`、`[` / `]` |
| 高亮前一个 / 后一个候选 | `↑` / `↓` |
| 删除当前高亮候选词 | `Ctrl + Delete`，仅组字时有效 |
| AI 助手 | `=`，仅非组合状态 |
| 启动语音 | `Ctrl + Win + Shift` |
| 按住说话 | `Ctrl + Win` |

单独按下并松开 `Shift` 切换中英文；组字时会先将当前原始预编辑内容上屏，例如 `nihao` 上屏为 `nihao`，再切到英文。
引擎自动插入的音节分隔符不会上屏，手动输入的撇号和已经选定的中文部分会保留。
按住 `Shift` 本身不会创建候选列表。中文半角模式下，`Shift + 字母` 将大写字母加入组合输入，由原版核心生成候选，支持 `AbC` 这样的大小写混合输入；松开 `Shift` 保留当前组合。
`Ctrl/Alt/Win + Shift` 组合键不会触发原始预编辑上屏。输入尚未返回候选时，空格、数字选词与 Shift 上屏会按输入顺序进入后端队列。

输入拼音后，用上下键高亮错误候选，按 `Ctrl + Delete` 删除；翻页后也可操作。
此操作调用原版核心的用户屏蔽词接口，不提交候选、不改变当前拼音，重启后仍生效。
它会屏蔽该词，并非只降低词频；当前没有单词级恢复界面。
`Ctrl + Delete` 当前是固定快捷键。
手动添加的常用语仍在“常用语和剪贴板”页管理。

## 设备同步

三个同步开关会直接写入官方设备组功能位。没有完成配对时，独立设置窗口会禁用这些开关。切换失败时界面恢复服务器返回的原状态。

## 自动更新

开启“有新版本时自动更新”后，WeTypeX 每天检查一次 GitHub Release。发现新版本时，会为 Arch、Debian/Ubuntu 或 Fedora 下载对应软件包并核对发布页中的 SHA-256；桌面通知的“安装更新”按钮随后调用系统授权界面完成升级。关闭开关会停止后台检查。

## 手工恢复

配置损坏时先退出 Fcitx5，备份并移走 `wetypex.json`，再重新启动。插件会使用内置默认值创建新配置。不要为了重置界面删除 `account` 或 `state`，否则会丢失配对身份和用户词库。
