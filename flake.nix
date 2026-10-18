{
  description = "Development environment for eink-emulator";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs {
          inherit system;
        };

        kindletool = pkgs.stdenv.mkDerivation rec {
          pname = "kindletool";
          version = "1.6.6";

          src = pkgs.fetchFromGitHub {
            owner = "NiLuJe";
            repo = "KindleTool";
            rev = "v${version}";
            hash = "sha256-IelccR8b6btLiiJQ5gXyizSIgfZzQtztV5QT3eCHBms=";
          };

          nativeBuildInputs = with pkgs; [
            pkg-config
          ];

          buildInputs = with pkgs; [
            gmp
            nettle
            libarchive
            openssl
            libgcrypt
            libgpg-error
            zlib
          ];

          makeFlags = [ "PREFIX=$(out)" ];

          installPhase = ''
            runHook preInstall
            install -Dm755 KindleTool/Release/kindletool "$out/bin/kindletool" || install -Dm755 kindletool "$out/bin/kindletool"
            runHook postInstall
          '';

          meta = with pkgs.lib; {
            description = "Tool for creating and manipulating Amazon Kindle update packages";
            homepage = "https://github.com/NiLuJe/KindleTool";
            license = licenses.gpl3Plus;
            maintainers = [ ];
            platforms = platforms.unix;
          };
        };
      in
      {
        packages.kindletool = kindletool;

        devShells.default = pkgs.mkShell {
          name = "eink-emulator-dev";

          packages = [
            # Host requirements from README.md
            (pkgs.python3.withPackages (ps: [ ]))
            pkgs.ninja
            pkgs.e2fsprogs
            pkgs.openssh
            pkgs.zstd
            kindletool

            # QEMU build dependencies & tools
            pkgs.git
            pkgs.pkg-config
            pkgs.meson
            pkgs.bison
            pkgs.flex
            pkgs.glib
            pkgs.pixman
            pkgs.dtc
            pkgs.libslirp

            # required for deleting machine
            pkgs.lsof
          ] ++ pkgs.lib.optionals pkgs.stdenv.hostPlatform.isLinux [
            # QEMU display backends. Without these QEMU only offers the
            # headless "none" and "dbus" backends, so ./eink run boots the
            # guest but never opens a window.
            pkgs.gtk3
            pkgs.SDL2
          ] ++ pkgs.lib.optionals pkgs.stdenv.hostPlatform.isDarwin [
            # macOS specific dependencies if needed
            pkgs.darwin.apple_sdk.frameworks.Cocoa
          ];

          shellHook = ''
            export AR="gcc-ar"
            export RANLIB="gcc-ranlib"
            export NM="gcc-nm"

            if [ -f qemu/build/config-host.h ] &&
               ! grep -q '^#define CONFIG_GTK$' qemu/build/config-host.h; then
              echo "eink-emulator: the existing QEMU build has no GTK display backend." >&2
              echo "Run 'rm -rf qemu/build && ./eink build' once to enable the VM window." >&2
            fi
          '';
        };
      });
}
