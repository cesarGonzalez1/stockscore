import pandas as pd


def to_frame(results) -> pd.DataFrame:
    rows = []
    for r in results:
        row = {"elegible": r.signal != "DATOS INCOMPLETOS", "ticker": r.ticker, "name": r.name, "sector": r.sector, "total": r.total, "grade": r.grade,
               "signal": r.signal, "coverage": r.coverage, "vetoes": len(r.vetoes), "warnings": len(r.warnings)}
        for p, v in r.pillars.items():
            row[p] = None if v["score"] is None else round(v["score"], 1)
        rows.append(row)
    df = pd.DataFrame(rows).sort_values("total", ascending=False).reset_index(drop=True)
    df.insert(0, "rank", df.index + 1)
    df["percentile"] = (1 - (df["rank"] - 1) / max(len(df), 1)) * 100
    return df


def top_n(results, n=10, sector=None, profile_min_coverage=0.0, exclude_vetoed=False, only_eligible=True):
    """Top-N. Por defecto EXCLUYE las de 'DATOS INCOMPLETOS' (evaluación parcial no comparable, p. ej. bancos)."""
    df = to_frame(results)
    if only_eligible:
        df = df[df.elegible]
    if sector:
        df = df[df.sector == sector]
    if exclude_vetoed:
        df = df[df.vetoes == 0]
    df = df[df.coverage >= profile_min_coverage].head(n).copy()
    df["rank"] = range(1, len(df) + 1)
    return df


def rank_changes(old: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    m = new[["ticker", "rank", "total"]].merge(old[["ticker", "rank", "total"]], on="ticker", suffixes=("", "_prev"), how="left")
    m["d_rank"] = m["rank_prev"] - m["rank"]   # positivo = subió
    m["d_total"] = m["total"] - m["total_prev"]
    return m


def diversify(df: pd.DataFrame, n=10, max_per_sector=3) -> pd.DataFrame:
    """Top-N con tope por sector (solo para mostrar/decidir; el ranking guardado y el forward test no cambian).
    Recorre de mayor a menor puntaje y se salta las que ya llenaron su sector."""
    keep, cnt = [], {}
    for i, r in df.iterrows():
        if cnt.get(r["sector"], 0) >= max_per_sector:
            continue
        cnt[r["sector"]] = cnt.get(r["sector"], 0) + 1
        keep.append(i)
        if len(keep) >= n:
            break
    out = df.loc[keep].copy()
    out["rank_puro"] = out["rank"]
    out["rank"] = range(1, len(out) + 1)
    return out
