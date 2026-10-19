import numpy as np
import pandas as pd


def rsi_wilder(close: pd.Series, n=14):
    d = close.diff().dropna()
    if len(d) < n:
        return None
    up, dn = d.clip(lower=0), -d.clip(upper=0)
    au, ad = up.iloc[:n].mean(), dn.iloc[:n].mean()
    for u, v in zip(up.iloc[n:], dn.iloc[n:]):
        au, ad = (au * (n - 1) + u) / n, (ad * (n - 1) + v) / n
    return 100.0 if ad == 0 else 100 - 100 / (1 + au / ad)


def slope_tstat(close: pd.Series, n=60):
    y = np.log(close.iloc[-n:].values)
    if len(y) < 20:
        return None
    x = np.arange(len(y))
    b, a = np.polyfit(x, y, 1)
    res = y - (a + b * x)
    se = np.sqrt(res.var(ddof=2) / ((x - x.mean()) ** 2).sum())
    return float(b / se) if se > 0 else None


def compute(snap, cfg, bench, m):
    out, notes = {}, []
    c = snap.closes()
    mk = snap.market
    n = len(c)
    out["hist_days"] = n
    px = snap.price or (c.iloc[-1] if n else None)
    # Momentum 12-1 (Jegadeesh-Titman) si hay >=253 cierres; si no, retorno 52 semanas reportado por la fuente.
    if n >= 253:
        out["mom"] = float(c.iloc[-22] / c.iloc[-253] - 1)
    elif mk.get("ret_52w") is not None:
        out["mom"] = mk["ret_52w"]
        notes.append("mom = retorno 52 semanas de la fuente (incluye el último mes; no es 12-1 puro)")
    sma200 = float(c.iloc[-200:].mean()) if n >= 200 else mk.get("sma200")
    sma50 = float(c.iloc[-50:].mean()) if n >= 250 else mk.get("sma50")
    if px and sma200:
        out["vs_sma200"] = px / sma200 - 1
    if sma50 and sma200:
        out["sma50_vs_200"] = sma50 / sma200 - 1
    out["slope_t"] = slope_tstat(c) if n >= 20 else None
    rsi = mk.get("rsi14") if mk.get("rsi14") is not None else (rsi_wilder(c) if n > 15 else None)
    out["rsi14"] = rsi
    if n >= 22:
        out["ret_1m"] = float(c.iloc[-1] / c.iloc[-22] - 1)
    if bench is not None and out.get("mom") is not None and bench.market.get("ret_52w") is not None:
        out["rel_strength"] = out["mom"] - bench.market["ret_52w"]
    return out, notes
