"""Universo SINTÉTICO (datos inventados, reproducibles) SOLO para probar mecánica de ranking/top-N/validación.
No representa empresas reales. Los tickers son SYNxx."""
import numpy as np
import datetime as dt
from .models import Snapshot

SECTORS = ["Technology", "Consumer Discretionary", "Health Care", "Financials", "Industrials", "Energy", "Consumer Staples"]


def make_company(i, rng, as_of="2026-10-09", n=260):
    q = rng.normal()                      # calidad latente
    gr = float(np.clip(0.05 + 0.04 * rng.normal(), -0.10, 0.30))
    om = float(np.clip(0.14 + 0.06 * q + 0.03 * rng.normal(), 0.01, 0.40))
    gm = float(np.clip(om + 0.18 + 0.05 * rng.normal(), 0.1, 0.8))
    turn = float(np.clip(0.9 + 0.3 * rng.normal(), 0.3, 2.0))
    eqr = float(np.clip(0.45 + 0.12 * rng.normal() - 0.05 * q, 0.1, 0.8))
    conv = float(np.clip(0.95 + 0.2 * q + 0.1 * rng.normal(), 0.3, 1.6))
    dil = float(np.clip(0.0 + 0.01 * rng.normal(), -0.04, 0.04))
    rev0 = float(np.exp(rng.normal(9, 1.0)))
    fiscal = []
    for k in range(5):
        rev = rev0 / (1 + gr) ** k * (1 + 0.02 * rng.normal())
        ta = rev / turn
        eq = ta * eqr
        tl = ta - eq
        ca = ta * 0.4
        cr = float(np.clip(1.5 + 0.4 * rng.normal(), 0.6, 3.0))
        oi = rev * (om - 0.005 * k * np.sign(q) + 0.01 * rng.normal())
        ni = max(oi * 0.75 - 0.01 * rev, -0.05 * rev)
        da = rev * 0.04
        fiscal.append(dict(year=2025 - k, revenue=rev, gross_profit=rev * gm, operating_income=oi, net_income=ni,
                           cfo=ni * conv + da, capex=rev * 0.04, total_assets=ta, current_assets=ca, current_liabilities=ca / cr,
                           total_liabilities=tl, equity=eq, retained_earnings=eq * 0.3, long_term_debt=tl * 0.35,
                           total_debt=tl * 0.45, cash_st=ca * 0.4, shares_m=1000 * (1 + dil) ** k, da=da))
    f0 = fiscal[0]
    ttm = dict(revenue=f0["revenue"] * (1 + gr / 2), gross_profit=f0["gross_profit"] * (1 + gr / 2),
               operating_income=f0["operating_income"] * (1 + gr / 2), net_income=f0["net_income"] * (1 + gr / 2),
               ebitda=(f0["operating_income"] + f0["da"]) * (1 + gr / 2), cfo=f0["cfo"], fcf=f0["cfo"] - f0["capex"])
    ttm["eps"] = ttm["net_income"] / f0["shares_m"]
    pe = float(np.clip(np.exp(rng.normal(np.log(18), 0.4)), 6, 60))
    mcap = max(ttm["net_income"], 0.01 * ttm["revenue"]) * pe
    ev = mcap + f0["total_debt"] - f0["cash_st"]
    # precios: GBM con drift ligado a momentum latente
    mom_latent = 0.08 * q + 0.10 * rng.normal()
    sig = float(np.clip(0.22 + 0.08 * rng.normal(), 0.1, 0.7))
    r = rng.normal((mom_latent - 0.5 * sig ** 2) / 252, sig / np.sqrt(252), n)
    px = 50 * np.exp(np.cumsum(r))
    days = [(dt.date.fromisoformat(as_of) - dt.timedelta(days=int((n - j) * 1.45))).isoformat() for j in range(n)]
    shares_out = mcap / px[-1]
    d = dict(ticker=f"SYN{i:02d}", name=f"Sintética {i:02d}", sector=SECTORS[i % len(SECTORS)], currency="USD", as_of=as_of,
             price=float(px[-1]), source="SINTÉTICO (inventado)", fiscal=fiscal, ttm=ttm,
             market=dict(market_cap_m=mcap, enterprise_value_m=ev, shares_out_m=shares_out, pe=pe,
                         forward_pe=pe / (1 + max(gr, -0.5)), forward_eps=ttm["eps"] * (1 + gr),
                         beta=float(np.clip(1 + 0.3 * rng.normal(), 0.4, 2.0)),
                         analyst_target=float(px[-1] * (1 + 0.08 + 0.08 * rng.normal())),
                         analyst_consensus=str(rng.choice(["Buy", "Hold", "Hold", "Sell"])),
                         eps_growth_3y=float(np.clip(gr + 0.03 * rng.normal(), -0.05, 0.3)),
                         revenue_growth_3y=gr),
             price_history=[[a, float(b)] for a, b in zip(days, px)],
             events=[{"date": (dt.date.fromisoformat(as_of) + dt.timedelta(days=int(rng.integers(2, 90)))).isoformat(),
                      "type": "earnings", "confirmed": False}])
    return d


def synthetic_universe(n=50, seed=42, hist_days=260):
    rng = np.random.default_rng(seed)
    return [Snapshot(make_company(i + 1, rng, n=hist_days)) for i in range(n)]
