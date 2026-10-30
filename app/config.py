import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"


def load_environment():
    env_path = ROOT / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"").strip("'")
        os.environ.setdefault(key, value)


def neo4j_settings():
    password = os.environ.get("NEO4J_PASSWORD")
    if not password:
        raise RuntimeError("Set NEO4J_PASSWORD in .env or the environment.")
    return {
        "uri": os.environ.get("NEO4J_URI", "bolt://localhost:17687"),
        "user": os.environ.get("NEO4J_USER", "neo4j"),
        "password": password,
        "database": os.environ.get("NEO4J_DATABASE", "neo4j"),
    }
