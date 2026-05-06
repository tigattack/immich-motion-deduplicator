import os
from pathlib import Path


ENV_FILENAME = ".env"


def load_dotenv():
    env_path = Path.cwd() / ENV_FILENAME
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def require_env(name):
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def require_directory_env(name):
    value = Path(require_env(name)).expanduser()

    if not value.exists():
        raise FileNotFoundError(f"Configured path for {name} does not exist: {value}")

    if not value.is_dir():
        raise NotADirectoryError(f"Configured path for {name} is not a directory: {value}")

    return str(value)


def get_immich_api_url():
    api_url = require_env("IMMICH_API_URL").rstrip("/")
    if not api_url.endswith("/api"):
        api_url = f"{api_url}/api"
    return api_url


def resolve_server_path(original_path: str, server_prefix: str, local_root: str) -> str:
    if not original_path.startswith(server_prefix):
        raise ValueError(
            f"originalPath '{original_path}' does not start with IMMICH_SERVER_PATH_PREFIX '{server_prefix}'. Check your configuration."
        )

    path = original_path[len(server_prefix):]
    return os.path.join(local_root, path.lstrip('/'))
