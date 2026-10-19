from pathlib import Path
from ..models import Snapshot


class SnapshotProvider:
    """Lee data/snapshots/<TICKER>.json (datos congelados, reproducibles, sin red)."""

    def __init__(self, directory="data/snapshots"):
        self.dir = Path(directory)

    def get(self, ticker):
        p = self.dir / f"{ticker.upper()}.json"
        return Snapshot.load(p) if p.exists() else None

    def available(self):
        return sorted(p.stem for p in self.dir.glob("*.json"))
