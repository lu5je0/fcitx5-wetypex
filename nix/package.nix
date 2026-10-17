{
  lib,
  stdenv,
  fetchFromGitHub,
  fetchzip,
  cmake,
  pkg-config,
  makeWrapper,
  patchelf,
  boost,
  fcitx5,
  libime,
  json_c,
  openssl,
  llvmPackages,
  qt6,
  qt6Packages,
  bubblewrap,
  coreutils,
  util-linux,
  python3,
  pipewire,
  ffmpeg,
  wl-clipboard,
  libnotify,
  cacert,
}:

let
  runtimeAsset = builtins.fromJSON (builtins.readFile ../runtime/asset.json);
  runtimeSource = fetchzip {
    inherit (runtimeAsset) url hash;
  };
  # json-c 0.18 mistakes non-ASCII bytes for control characters in strict
  # mode, dropping every response with Chinese candidates. Fixed in 0.19.
  jsonC =
    if lib.versionAtLeast json_c.version "0.18" && lib.versionOlder json_c.version "0.19" then
      json_c.overrideAttrs (old: {
        patches = (old.patches or [ ]) ++ [ ./json-c-strict-utf8.patch ];
      })
    else
      json_c;
  kqueueSource = fetchFromGitHub {
    owner = "mheily";
    repo = "libkqueue";
    rev = "46a3e130f88b0b0742575dcb01d77e336538024b";
    hash = "sha256-bUtjzGxQHJkd9SxlXpA8xJ4hT0IeMHrlcfRLMTdT59k=";
  };
  curlSource = fetchzip {
    url = "https://curl.se/download/curl-8.22.0.tar.xz";
    hash = "sha256-3GBq7T5iU08VargRfd86qmAnheWRRd7ijH55PCw+ghY=";
  };
  runtimePath = lib.makeBinPath [
    bubblewrap
    coreutils
    util-linux
    python3
    pipewire
    ffmpeg
    wl-clipboard
    libnotify
  ];
in
stdenv.mkDerivation {
  pname = "fcitx5-wetypex";
  version = "2.2.3.657";

  src = lib.cleanSourceWith {
    src = ../.;
    filter =
      path: type:
      lib.cleanSourceFilter path type
      && !(builtins.elem (builtins.baseNameOf path) [
        "build"
        "dist"
        "vendor"
        ".cache"
        "__pycache__"
        ".agents"
        ".aws"
        ".codex"
      ]);
  };

  nativeBuildInputs = [
    cmake
    pkg-config
    makeWrapper
    patchelf
    llvmPackages.libcxxClang
    qt6.wrapQtAppsHook
  ];

  buildInputs = [
    boost
    fcitx5
    libime
    jsonC
    openssl
    llvmPackages.libcxx
    qt6Packages.fcitx5-qt
    qt6.qtbase
    qt6.qtsvg
    qt6.qtwebengine
    qt6.qtwayland
  ];

  # FetchContent may only use sources fetched and verified by Nix.
  cmakeFlags = [
    "-DCMAKE_INSTALL_LIBDIR=lib"
    "-DFCITX_INSTALL_ADDONDIR=lib/fcitx5"
    "-DWETYPE_QT_VERSION=6"
    "-DWETYPE_NIX_STORE=${builtins.storeDir}"
    "-DWETYPE_CA_BUNDLE=${cacert}/etc/ssl/certs/ca-bundle.crt"
    "-DWETYPE_CLANGXX=${llvmPackages.libcxxClang}/bin/clang++"
    "-DWETYPE_RUNTIME_SOURCE_DIR=${runtimeSource}"
    "-DFETCHCONTENT_FULLY_DISCONNECTED=ON"
    "-DFETCHCONTENT_SOURCE_DIR_KQUEUE=${kqueueSource}"
    "-DFETCHCONTENT_SOURCE_DIR_WETYPEX_CURL=${curlSource}"
  ];

  postInstall = ''
    # A profile-installed addon is outside the system Fcitx wrapper's addon
    # directories. Register the store library directly, as other Nix addons do.
    substituteInPlace "$out/share/fcitx5/addon/wetypex.conf" \
      --replace-fail 'Library=wetypex' "Library=$out/lib/fcitx5/wetypex"
  '';

  dontWrapQtApps = true;
  preFixup = ''
    # Plugin callers also need the command dependencies, not just interactive
    # shells. Keep Qt's plugin and WebEngine setup on all installed helpers.
    for program in "$out"/bin/*; do
      wrapQtApp "$program" \
        --prefix PATH : ${lib.escapeShellArg runtimePath} \
        --set-default SSL_CERT_FILE ${cacert}/etc/ssl/certs/ca-bundle.crt
    done
  '';

  postFixup = ''
    # These libraries are opened by name with dlopen, so the regular RPATH
    # shrinker cannot infer that the host needs them.
    patchelf --add-rpath ${lib.makeLibraryPath [ llvmPackages.libcxx ]} \
      "$out/lib/fcitx5-wetypex/wetypex-engine-host"
  '';

  doInstallCheck = true;
  doCheck = true;
  checkPhase = ''
    runHook preCheck
    ctest --output-on-failure
    pushd "$NIX_BUILD_TOP/$sourceRoot"
    ${python3}/bin/python3 -m unittest discover -s tests -p 'test_*.py'
    (cd ${runtimeSource} && sha256sum --check --quiet SHA256SUMS)
    popd
    runHook postCheck
  '';
  installCheckPhase = ''
    runHook preInstallCheck
    test -f "$out/lib/fcitx5/wetypex.so"
    test -f "$out/lib/fcitx5/qt6/libwetypexconfig.so"
    test -f "$out/share/fcitx5-wetypex/runtime/manifest.txt"
    test -f "$out/share/fcitx5-wetypex/runtime/flurry/manifest.txt"
    test -f "$out/share/fcitx5-wetypex/runtime/wxp2p/manifest.txt"
    test -f "$out/share/fcitx5-wetypex/ui/icons/input.svg"
    "$out/bin/fcitx5-wetypex-account" network-info > network-info.json
    ${python3}/bin/python3 -c \
      'import json; r = json.load(open("network-info.json")); assert r["ws"] and r["wss"], r'
    # Check the fallback used after bwrap --clearenv, independent of the
    # interactive shell's SSL_CERT_FILE and Qt wrapper environment.
    env -u SSL_CERT_FILE "$out/lib/fcitx5-wetypex/wetypex-engine-host" \
      "$out/lib/fcitx5-wetypex" network-info > sandbox-network-info.json
    ${python3}/bin/python3 -c \
      'import json, pathlib; r = json.load(open("sandbox-network-info.json")); assert r["ca_bundle"] == "${cacert}/etc/ssl/certs/ca-bundle.crt" and pathlib.Path(r["ca_bundle"]).is_file(), r'
    test -f "$out/share/icons/hicolor/48x48/apps/fcitx5-wetypex.png"
    grep -Fx "Icon=$out/share/icons/hicolor/48x48/apps/fcitx5-wetypex.png" \
      "$out/share/fcitx5/inputmethod/wetypex.conf"
    runHook postInstallCheck
  '';

  meta = {
    description = "Native WeType compatibility layer and input method for Fcitx5";
    homepage = "https://github.com/panxuc/fcitx5-wetypex";
    license = with lib.licenses; [
      mit
      isc
      bsd2
      curl
      unfree
    ];
    platforms = [ "x86_64-linux" ];
    mainProgram = "fcitx5-wetypex-settings";
  };
}
