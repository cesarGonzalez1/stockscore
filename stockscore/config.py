from pathlib import Path
import yaml, hashlib

ROOT = Path(__file__).resolve().parent.parent
DEFAULT = ROOT / "config" / "default.yaml"


def load_config(path=None) -> dict:
    p = Path(path) if path else DEFAULT
    cfg = yaml.safe_load(p.read_text())
    cfg["_hash"] = hashlib.sha1(p.read_bytes()).hexdigest()[:10]
    return cfg
