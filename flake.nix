{
  description =
    "A flake to create a devshell and build a container image for the app.";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs?ref=nixos-24.11";

    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.uv2nix.follows = "uv2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    { self, nixpkgs, uv2nix, pyproject-nix, pyproject-build-systems, ... }:
    let
      inherit (nixpkgs) lib;
      systems = lib.systems.flakeExposed;
      forAllSystems = lib.genAttrs systems;

      pyprojectOverrides = final: prev: {
        libsass = prev.libsass.overrideAttrs(old: {
          buildInputs = (old.buildInputs or []) ++ final.resolveBuildSystem ( {setuptools = [];});
          });
      };

      getPkgs = system: nixpkgs.legacyPackages.${system};

      pythonVersion = system: let pkgs = getPkgs system; in pkgs.python312;

      # Load the workspace and create the overlay for pyproject.
      workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };
      overlay = workspace.mkPyprojectOverlay { sourcePreference = "wheel"; };

      # Build a Python set based on pyproject-nix builders.
      buildPythonSet = system:
        let
          pkgs = getPkgs system;
          python = pythonVersion system;
        in (pkgs.callPackage pyproject-nix.build.packages {
          inherit python;
        }).overrideScope (lib.composeManyExtensions [
          pyproject-build-systems.overlays.default
          overlay
          pyprojectOverrides
        ]);

      # Build the virtual environment.
      buildVenv = system:
        let pythonSet = buildPythonSet system;
        in pythonSet.mkVirtualEnv "tempapp-venv" workspace.deps.default;

      # Define the production container image.
      dockerImage = system:
        let
          pkgs = getPkgs system;
          venv = buildVenv system;
        in pkgs.dockerTools.buildLayeredImage {
          name = "ghcr.io/stefur/tempapp";
          tag = (self.shortRev or "dev") + "-" + pkgs.go.GOARCH;
          contents = [
            venv
            (pkgs.glibcLocales.override {
              locales = [ "sv_SE.UTF-8/UTF-8" ];
              allLocales = false;
            })
          ];
          config = {
            Env = [
              "LOCALE_ARCHIVE=/lib/locale/locale-archive"
              "TZ=Europe/Stockholm"
            ];
            Cmd = [ "tempapp" "run" ];
            ExposedPorts = { "8000/tcp" = { }; };
            Labels = {
              "org.opencontainers.image.source" =
                "https://github.com/stefur/tempapp";
              "org.opencontainers.image.description" =
                "An image to run the app.";
            };
          };
        };

      # Define the development environment shell.
      devEnv = system:
        let
          pkgs = getPkgs system;
          python = pythonVersion system;
        in pkgs.mkShell {
          packages = [
            python
            pkgs.uv
            (pkgs.glibcLocales.override {
              locales = [ "sv_SE.UTF-8/UTF-8" ];
              allLocales = false;
            })
          ];
          env = {
            UV_PYTHON_DOWNLOADS = "never";
            UV_PYTHON = python.interpreter;
          } // lib.optionalAttrs pkgs.stdenv.isLinux {
            LD_LIBRARY_PATH =
              lib.makeLibraryPath pkgs.pythonManylinuxPackages.manylinux1;
          };
          shellHook = ''
            unset PYTHONPATH
          '';
        };
    in {
      packages = forAllSystems (system:
        lib.optionalAttrs (getPkgs system).stdenv.isLinux {
          image = dockerImage system;
        });
      devShells = forAllSystems (system: { dev = devEnv system; });
    };
}
