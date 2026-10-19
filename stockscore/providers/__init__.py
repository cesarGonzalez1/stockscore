from .snapshot import SnapshotProvider
from .yfinance_provider import YFinanceProvider


def get_provider(kind, **kw):
    return {"snapshot": SnapshotProvider, "yfinance": YFinanceProvider}[kind](**kw)
