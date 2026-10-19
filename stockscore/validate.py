"""Validación del scorecard: (1) contra scores clásicos independientes, (2) estabilidad ante perturbación de pesos,
(3) chequeo contra Piotroski/Altman reportados por fuentes. NO es un backtest de rentabilidad (ver docs/METHODOLOGY.md)."""
import numpy as np
import pandas as pd
from .metrics import compute_all
from .scoring import score_from_metrics
from .stats import spearman


def benchmarks(snaps, cfg, bench=None) -> pd.DataFrame:
    rows = []
    for s in snaps:
        m, _ = compute_all(s, cfg, bench)
        ey = 1 / m["ev_ebit"] if m.get("ev_ebit") else None
        rows.append(dict(ticker=s.ticker, piotroski=m.get("piotroski"), altman_z2=m.get("altman_z2"), roic=m.get("roic"),
                         ebit_ev=ey, mom=m.get("mom"), fcf_yield=m.get("fcf_yield")))
    df = pd.DataFrame(rows).set_index("ticker")
    df["magic_formula"] = (df["ebit_ev"].rank() + df["roic"].rank()) / 2   # Greenblatt: mayor = mejor
    return df


def correlations(results, bench_df) -> pd.DataFrame:
    tot = pd.Series({r.ticker: r.total for r in results})
    out = []
    for col in ["piotroski", "altman_z2", "magic_formula", "mom", "fcf_yield"]:
        x = pd.concat([tot, bench_df[col]], axis=1, keys=["t", "b"]).dropna()
        out.append(dict(benchmark=col, n=len(x), spearman=spearman(x["t"], x["b"])))
    return pd.DataFrame(out)


def topn_overlap(results, bench_df, n=10) -> pd.DataFrame:
    mine = {r.ticker for r in sorted(results, key=lambda r: -r.total)[:n]}
    out = []
    for col in ["piotroski", "altman_z2", "magic_formula", "mom"]:
        theirs = set(bench_df[col].dropna().sort_values(ascending=False).head(n).index)
        out.append(dict(benchmark=col, n=n, overlap=len(mine & theirs), overlap_pct=len(mine & theirs) / n))
    return pd.DataFrame(out)


def weight_stability(snaps, cfg, profile="swing", n_runs=200, jitter=0.5, top_n=10, seed=0, bench=None) -> dict:
    """Perturba pesos de pilares ±jitter (multiplicativo) y mide cuánto cambia el ranking. Alta estabilidad = ranking no depende de pesos arbitrarios."""
    rng = np.random.default_rng(seed)
    pre = [(s, *compute_all(s, cfg, bench)) for s in snaps]
    base_w = cfg["profiles"][profile]
    base = pd.Series({s.ticker: score_from_metrics(s, m, nt, cfg, profile).total for s, m, nt in pre})
    base_top = set(base.sort_values(ascending=False).head(top_n).index)
    rhos, keeps = [], []
    for _ in range(n_runs):
        w = {k: v * rng.uniform(1 - jitter, 1 + jitter) for k, v in base_w.items()}
        sc = pd.Series({s.ticker: score_from_metrics(s, m, nt, cfg, profile, weights=w).total for s, m, nt in pre})
        rhos.append(spearman(base, sc))
        keeps.append(len(base_top & set(sc.sort_values(ascending=False).head(top_n).index)) / top_n)
    return dict(runs=n_runs, jitter=jitter, spearman_mean=float(np.mean(rhos)), spearman_min=float(np.min(rhos)),
                topn_kept_mean=float(np.mean(keeps)), topn_kept_min=float(np.min(keeps)))


def reported_check(snaps, cfg) -> pd.DataFrame:
    rows = []
    for s in snaps:
        if not s.reported:
            continue
        m, _ = compute_all(s, cfg)
        rows.append(dict(ticker=s.ticker, piotroski_calc=m.get("piotroski"), piotroski_sitio=s.reported.get("piotroski"),
                         altman_z_calc=None if m.get("altman_z") is None else round(m["altman_z"], 2),
                         altman_z2_calc=None if m.get("altman_z2") is None else round(m["altman_z2"], 2),
                         altman_sitio=s.reported.get("altman")))
    return pd.DataFrame(rows)
