{
  description = "WeTypeX: native WeType compatibility layer for Fcitx5";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";

  outputs =
    { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs {
        inherit system;
        config.allowUnfree = true;
      };
      package = pkgs.callPackage ./nix/package.nix { };
    in
    {
      packages.${system} = {
        default = package;
        fcitx5-wetypex = package;
      };

      overlays.default = final: prev: {
        fcitx5-wetypex = final.callPackage ./nix/package.nix { };
      };

      devShells.${system}.default = pkgs.mkShell {
        inputsFrom = [ package ];
        inherit (package) cmakeFlags;
      };

      checks.${system}.default = package;
      formatter.${system} = pkgs.nixfmt;
    };
}
