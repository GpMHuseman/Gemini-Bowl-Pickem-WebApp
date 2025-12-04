
# To learn more about how to use Nix to configure your environment
# see: https://firebase.google.com/docs/studio/customize-workspace
{ pkgs, ... }: {
  # Which nixpkgs channel to use.
  channel = "stable-24.05"; # or "unstable"

  # Use https://search.nixos.org/packages to find packages
  packages = [
    pkgs.go
    pkgs.python311
    pkgs.python311Packages.pip
    pkgs.nodejs_20
    pkgs.nodePackages.nodemon
    pkgs.sudo
  ];

  # Sets environment variables in the workspace
  env = {};
  idx = {
    # Search for the extensions you want on https://open-vsx.org/ and use "publisher.id"
    extensions = [
      # "vscodevim.vim"
    ];

    # Enable previews for the web server
    previews = {
      enable = true;
      previews = {
        web = {
          # This command creates a venv, installs dependencies, and starts the server.
          command = [
            "bash"
            "-c"
            "python3.11 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && gunicorn --workers 3 --bind 0.0.0.0:$PORT app:app"
            #"python3.11 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && FLASK_APP=app.py FLASK_DEBUG=1 flask run --host=0.0.0.0 --port=$PORT"

          ];
          manager = "web";
        };
      };
    };

    # Workspace lifecycle hooks
    workspace = {
      # Runs when a workspace is first created
      onCreate = {
        # Set up the virtual environment for the main terminal.
        pip-install = "python3.11 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt";
      };
      # onStart is not needed.
      onStart = {};
    };
  };
}
