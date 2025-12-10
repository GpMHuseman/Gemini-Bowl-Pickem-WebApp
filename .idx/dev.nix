{ pkgs, ... }: {
  channel = "stable-24.05";
  packages = [
    pkgs.go
    pkgs.python311
    pkgs.python311Packages.pip
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
            "python3.11 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && GOOGLE_APPLICATION_CREDENTIALS='private/web-bowl-pickem-firebase-admin-v1.json' gunicorn --workers 1 --bind 0.0.0.0:$PORT --access-logfile - --error-logfile - --log-level debug --reload main:app"
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
