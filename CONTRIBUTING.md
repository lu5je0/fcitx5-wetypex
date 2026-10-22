# 贡献指南

感谢你帮助改进 WeTypeX。提交改动前请先说明要解决的具体行为，并区分 Linux 集成问题、固定原版版本兼容问题和上游服务变化。

## 基本要求

- 固定官方运行时通过 `tools/package_runtime.py` 生成独立 Release 资产，源码只更新 `runtime/asset.json` 和来源说明；不提交原版二进制、完整安装包、账户数据或个人词库。
- 不伪造候选、登录、配对、同步、语音、AI 或传输成功状态。
- 界面变更必须注明参考平台和版本；平台差异要在说明中写清楚。
- ABI 结构变更需要注明适用版本、兼容范围和失败边界。
- 日志、图片和示例数据必须删除 UIN、设备码、传输码、剪贴板及私人文本。

## 代码风格

C/C++ 使用 C++20、两空格缩进和现有命名风格。Python 与 Shell 应保持依赖少、错误即退出，并为创建的账户或用户内容设置严格权限。

## 提交前检查

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --parallel
ctest --test-dir build --output-on-failure
for script in scripts/*.sh.in; do
  case "$script" in *-syncd.sh.in|*-update.sh.in|*-sync.sh.in) continue;; esac
  sh -n "$script"
done
python3 -m py_compile scripts/setup_runtime.py tools/*.py \
  build/fcitx5-wetypex-syncd build/fcitx5-wetypex-update build/fcitx5-wetypex-sync
python3 -m unittest discover -s tests -p 'test_*.py'
python3 tools/package_release.py
```

Pull Request 应描述最终行为、适用环境、实际执行过的检查以及仍存在的限制。

已安装 Python 的 `dbus-python`、PyGObject 与 Fcitx5 后，可进行隔离的输入功能检查：

```bash
python3 tests/fcitx_dbus_smoke.py --package ./result
python3 tests/fcitx_dbus_smoke.py --package ./result --kimpanel
python3 tests/fcitx_dbus_smoke.py --package ./result --kimpanel --text-icon
python3 tests/fcitx_dbus_smoke.py --package ./result --follow-cursor
python3 tests/fcitx_dbus_smoke.py --package ./result --kimpanel --no-inline-preedit
python3 tests/backend_forget_smoke.py --package ./result
python3 tests/backend_candidates_smoke.py --package ./result
```

脚本创建临时 HOME 和独立 D-Bus，只发送固定测试文本，不连接桌面输入会话。
检查候选编号空格、默认 6 个候选、翻页、选词上屏、面板图标，以及 tmux 前缀按键透传。
同时检查拼音起点锚定、关闭锚定、无内嵌预编辑的候选窗，以及固定定位点后的方向键和退格编辑。
删词检查覆盖高亮候选、翻页、错误快照保护、学习词删除和进程重启后的持久化；词库均在临时目录中。
候选检查覆盖 `yi`、`yixuan` 的完整候选列表，第 50 个之后的翻页与选择（包括 `ji` 的“齑”），以及部分选字后继续输入；同时检查“螫、鱻、驫、龘、齉、靐、麤、犇”等生僻字。
