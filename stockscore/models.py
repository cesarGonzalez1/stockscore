from __future__ import annotations
import json, math, datetime as dt
from dataclasses import dataclass, field
from pathlib import Path
import pandas as pd


def div(a, b):
    """División segura: None si falta algo o b==0."""
    if a is None or b is None:
        return None
    try:
        if b == 0 or math.isnan(a) or math.isnan(b):
            return None
        return a / b
    except TypeError:
        return None


def cagr(new, old, years):
    if new is None or old is None or years <= 0 or old <= 0 or new <= 0:
        return None
    return (new / old) ** (1 / years) - 1


class Snapshot:
    """Foto de una empresa en una fecha (estados anuales, TTM, mercado, precios, eventos)."""

    def __init__(self, d: dict):
        self.d = d
        self.ticker = d["ticker"]
        self.name = d.get("name", d["ticker"])
        self.sector = d.get("sector", "?")
        self.industry = d.get("industry", "") or ""
        self.price = d.get("price")
        self.as_of = dt.date.fromisoformat(d["as_of"]) if d.get("as_of") else dt.date.today()
        self.fiscal = sorted((self._repair(f) for f in d.get("fiscal", [])), key=lambda f: -f["year"])  # más reciente primero
        self.ttm = d.get("ttm", {}) or {}
        self.market = d.get("market", {}) or {}
        self.events = d.get("events", []) or []
        self.reported = d.get("reported_scores", {}) or {}

    @staticmethod
    def _repair(f):
        """Yahoo a veces omite filas (quedan en 0). Se reconstruyen con identidades contables."""
        f = dict(f)
        ta, eq = f.get("total_assets") or 0, f.get("equity") or 0
        if not f.get("total_liabilities") and ta:
            f["total_liabilities"] = ta - eq
        if not f.get("equity") and ta and f.get("total_liabilities"):
            f["equity"] = ta - f["total_liabilities"]
        return f

    @property
    def is_financial(self) -> bool:
        """Bancos/seguros/casas de bolsa: EV, FCF, capital de trabajo y Altman no aplican."""
        ind = self.industry.lower()
        return any(k in ind for k in ("bank", "insurance", "capital markets", "mortgage"))

    def fy(self, i):
        return self.fiscal[i] if 0 <= i < len(self.fiscal) else None

    def closes(self) -> pd.Series:
        ph = self.d.get("price_history") or []
        if not ph:
            return pd.Series(dtype=float)
        s = pd.Series([p[1] for p in ph], index=pd.to_datetime([p[0] for p in ph]), dtype=float)
        return s[~s.index.duplicated()].sort_index()

    @property
    def market_cap(self):
        m = self.market.get("market_cap_m")
        if m: return m
        sh = self.market.get("shares_out_m")
        return sh * self.price if sh and self.price else None

    @property
    def shares_m(self):
        sh = self.market.get("shares_out_m")
        if sh: return sh
        return div(self.market_cap, self.price)

    @property
    def enterprise_value(self):
        ev = self.market.get("enterprise_value_m")
        if ev: return ev
        f = self.fy(0)
        if f and self.market_cap:
            return self.market_cap + f["total_debt"] - f["cash_st"]
        return None

    @staticmethod
    def load(path) -> "Snapshot":
        return Snapshot(json.loads(Path(path).read_text()))


@dataclass
class Result:
    ticker: str
    name: str
    sector: str
    profile: str
    total: float
    grade: str
    coverage: float
    signal: str
    pillars: dict            # nombre -> {"score": x, "coverage": y}
    metrics: dict            # valores crudos
    metric_scores: dict      # 0-100 por métrica
    vetoes: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    as_of: str = ""
