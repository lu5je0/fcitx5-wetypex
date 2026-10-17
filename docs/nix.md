# Nix / NixOS

目前支持 `x86_64-linux`。Flake 提供 `packages.x86_64-linux.default`、
`packages.x86_64-linux.fcitx5-wetypex`、`overlays.default` 和开发 shell。
默认使用 NixOS 26.05，具体 Nixpkgs 修订由 `flake.lock` 固定。

## 本地构建

启用 Nix 的 `nix-command` 和 `flakes` 后，在项目目录执行：

```sh
nix build path:.
./result/bin/fcitx5-wetypex-account network-info
```

`path:.` 也会包含尚未被 Git 跟踪的新文件；文件加入版本控制后可直接使用 `nix build`。
构建自动检查中文/emoji 候选响应解析、插件安装位置，以及传输桥接的 WS/WSS 能力。
官方输入核心、词典和界面资源存放在独立的 GitHub Release，源码不包含这些文件。
Nix 使用 `fetchzip` 按 `runtime/asset.json` 固定的 URL 和哈希下载、解包并校验它们，
再将只读资源目录传给 CMake；构建阶段不额外联网，安装后无需再次下载。
账户和个人词库仍在用户目录中，未包含在包内。包中含原版专有组件，因此 Nix 元数据标为 unfree；本 flake 的直接包输出已允许构建这些组件。

## 使用 nix profile

```sh
cd fcitx5-wetypex
nix profile install path:.
fcitx5-wetypex-setup --check
```

更新已安装的本地包时，先用 `nix profile list` 查看对应名称，再执行
`nix profile upgrade fcitx5-wetypex`（名称以实际列表为准）。
若旧版初始化留下只读主题，可离线修复用户资源：

```sh
fcitx5-wetypex-setup --bundled
```

如果旧包出现拼音预编辑、却没有候选窗口，请升级并重启 Fcitx5。
当前包已回补 json-c 0.18 严格模式误拒绝中文和 emoji 的
[上游修复](https://github.com/json-c/json-c/commit/565f181f656439847ef79650caad5c0b6c20171b)。

Nix 包将输入插件注册为绝对 store 路径；只要桌面会话的 `XDG_DATA_DIRS` 包含 profile 的 share 目录，Fcitx5 就能加载它。安装或升级后重启 Fcitx5，再打开配置工具：

```sh
fcitx5 -rd
fcitx5-config-qt
```

如果当前会话未包含 profile 路径，或需要加载 WeTypeX 的 Qt 扩展配置页，可显式添加搜索路径：

```sh
export FCITX_ADDON_DIRS="$HOME/.nix-profile/lib/fcitx5${FCITX_ADDON_DIRS:+:$FCITX_ADDON_DIRS}"
export XDG_DATA_DIRS="$HOME/.nix-profile/share:${XDG_DATA_DIRS:-/run/current-system/sw/share}"
fcitx5 -rd
fcitx5-config-qt
```

在配置窗口中添加 WeTypeX。将上述搜索路径加入桌面会话环境或 Fcitx5 启动脚本，可在下次登录时继续使用。

输入法状态图标随模式切换显示“中”或“英”，同时提供文字标签与单色 SVG，
桌面面板无需重新登录或刷新图标主题缓存。应用图标继续使用包内 PNG。
账户、云候选等原版网络连接使用包内固定的 CA 证书路径，即使沙箱清除了环境变量也能验证服务端证书。

## NixOS

下面的系统 flake 保留现有 `configuration.nix`，并启用插件：

```nix
{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";
    wetypex = {
      url = "path:/absolute/path/to/fcitx5-wetypex";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = inputs@{ nixpkgs, ... }: {
    nixosConfigurations.my-host = nixpkgs.lib.nixosSystem {
      system = "x86_64-linux";
      specialArgs = { inherit inputs; };
      modules = [
        ./configuration.nix
        ({ inputs, pkgs, ... }: {
          nixpkgs.overlays = [ inputs.wetypex.overlays.default ];
          nixpkgs.config.allowUnfree = true;
          i18n.inputMethod = {
            enable = true;
            type = "fcitx5";
            fcitx5.addons = [ pkgs.fcitx5-wetypex ];
          };
        })
      ];
    };
  };
}
```

将路径和主机名替换成自己的配置。也可将输入改成已包含这些 Nix 文件的 Git 仓库。
跟随系统 Nixpkgs 并使用 overlay，让插件与系统 Fcitx5、Qt 使用相同的依赖版本。
不需要单独向 `environment.systemPackages` 添加 Fcitx5；由
`i18n.inputMethod.fcitx5.addons` 负责插件搜索路径和命令集成。
参见 [NixOS 的 Fcitx5 配置说明](https://wiki.nixos.org/wiki/Fcitx5)。

## Home Manager

将同一个 overlay 加到 Home Manager 使用的 `pkgs`，并通过
`extraSpecialArgs = { inherit inputs; };` 传入输入后，可在 `home.nix` 中使用：

```nix
{ inputs, pkgs, ... }: {
  nixpkgs.overlays = [ inputs.wetypex.overlays.default ];
  nixpkgs.config.allowUnfree = true;
  i18n.inputMethod = {
    enable = true;
    type = "fcitx5";
    fcitx5.addons = [ pkgs.fcitx5-wetypex ];
  };
}
```

NixOS 集成的 Home Manager 如果启用了 `useGlobalPkgs`，请在 NixOS 层添加 overlay。
Fcitx5 由系统配置或 Home Manager 中的一处管理即可。

## 首次运行

安装后即可使用包内运行时，无需下载或提取：

```sh
fcitx5-wetypex-setup --check
```

如需恢复用户界面资源、修复旧版只读主题：

```sh
fcitx5-wetypex-setup --bundled
```

保留从官方安装包单独安装用户运行时的方式：

```sh
fcitx5-wetypex-setup --archive /path/to/WeType_2.2.3_657.zip
# 或明确接受上游许可后下载：
fcitx5-wetypex-setup --download --accept-upstream-license
fcitx5-wetypex-setup --check
```

随后在 Fcitx5 配置中添加 WeTypeX。默认运行时在包内只读的
`share/fcitx5-wetypex/runtime`，已有用户运行时或 `WETYPE_RUNTIME_DIR` 可覆盖它；账户和个人词库保存在 XDG 用户目录。
更新本项目输入并重建系统即可升级；NixOS 安装不使用
面向 deb、rpm 和 Arch 软件包的内置自动安装流程。

## 开发与构建细节

```sh
nix develop path:.
cmake -S . -B build $cmakeFlags
cmake --build build --parallel
```

也可用 `nix flake check path:.` 完整构建并执行安装检查。

Nix 构建预先获取固定版本的原版运行时、libkqueue 和 curl，再传给 CMake，
构建阶段无需 FetchContent 联网。引擎继续使用带 WS/WSS 的私有 curl。
Clang/libc++ 用于与原版核心交互的桥接，宿主通过 RPATH 查找动态加载的 libc++。
Qt、Python、Bubblewrap、PipeWire、FFmpeg 和剪贴板命令都由包内启动器提供。

所有引擎入口与 `setup --check` 共享沙箱启动器。普通发行版保留原来的 `/usr`
布局；Nix 构建通过 `WETYPE_NIX_STORE` 将 store 只读挂载到沙箱，
离线模式继续隔离网络，用户数据仍只挂载运行时目录和当前工作目录。
