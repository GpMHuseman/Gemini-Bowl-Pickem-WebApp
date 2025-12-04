{ pkgs, ... }: {
  channel = "stable-24.05";
  packages = [
    pkgs.go
    pkgs.python311
    pkgs.python311Packages.pip
    pkgs.nodejs_20
    pkgs.nodePackages.nodemon
    pkgs.sudo
    pkgs.firebase-tools # Added for Firebase deployments
  ];
  env = {};
  idx = {
    extensions = [];
    previews = {
      enable = true;
      previews = {
        web = {
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
    workspace = {
      onCreate = {
        pip-install = "python3.11 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt";
      };
      onStart = {};
    };
  };
}
