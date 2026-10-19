"""Flujo semanal: bajar datos → puntuar → guardar corrida → cambios de posición → forward de corridas viejas."""
import datetime as dt
import pandas as pd
from .scoring import score_universe
from .ranking import to_frame, top_n, rank_changes, diversify
from .forward import forward_report, format_forward


def auto_label(today=None):
    y, w, _ = (today or dt.date.today()).isocalendar()
    return f"{y}-W{w:02d}"


def run_weekly(tickers, fetch_fn, store, cfg, price_fn=None, label=None, top=10, out=print, today=None, forward_min_days=7):
    """fetch_fn(ticker)->Snapshot|None. Devuelve dict con resultados para pruebas."""
    label = label or auto_label(today)
    snaps, failed, bench = [], [], None
    for t in tickers + ["SPY"]:
        try:
            s = fetch_fn(t)
        except Exception as e:
            failed.append((t, str(e)[:80])); continue
        if s is None:
            failed.append((t, "sin datos")); continue
        if t == "SPY":
            bench = s
        else:
            snaps.append(s)
    out(f"Datos: {len(snaps)}/{len(tickers)} empresas. Fallidas: {', '.join(t for t, _ in failed) or 'ninguna'}")
    res_by_profile, rids = {}, {}
    for prof in ("swing", "investor"):
        res = score_universe(snaps, cfg, prof, bench)
        rid = store.save_run(res, prof, cfg["_hash"], label)
        prev = store.previous_run(prof, rid)
        new_df = store.ranking(rid)
        out(f"\n== {prof.upper()} · corrida #{rid} · {label} ==")
        show = new_df.head(top)[["rank", "ticker", "total", "grade", "signal"]].copy()
        if prev:
            ch = rank_changes(store.ranking(prev), new_df).set_index("ticker")
            show["Δpuesto"] = [ch.loc[t, "d_rank"] if t in ch.index and pd.notna(ch.loc[t, "d_rank"]) else None for t in show.ticker]
            show["Δpuntos"] = [round(ch.loc[t, "d_total"], 1) if t in ch.index and pd.notna(ch.loc[t, "d_total"]) else None for t in show.ticker]
        out(show.round(1).to_string(index=False))
        div = diversify(new_df, n=top, max_per_sector=3)
        if list(div.ticker) != list(new_df.head(top).ticker):
            out(f"-- {prof.upper()} diversificado (máx 3 por sector; el ranking guardado no cambia) --")
            out(div[["rank", "ticker", "sector", "total", "signal", "rank_puro"]].round(1).to_string(index=False))
        full = store.ranking(rid, only_eligible=False)
        excl = [t for t in full.ticker if t not in set(new_df.ticker)]
        if excl:
            out(f"(Excluidas del ranking por DATOS INCOMPLETOS: {', '.join(excl)} — evaluación parcial, no comparable; ver 'show' de cada una)")
        res_by_profile[prof], rids[prof] = res, rid
    if price_fn is not None:
        ref = (today or dt.date.today()) - dt.timedelta(days=forward_min_days)
        old = [r for r in store.runs().itertuples() if r.profile == "swing" and r.id != rids["swing"] and pd.Timestamp(r.ts).date() <= ref]
        if old:
            out("\n" + format_forward(forward_report(store, old[-1].id, price_fn, top=top, today=today)))
        else:
            out("\n(Forward: aún no hay una corrida swing de hace ≥ 7 días para evaluar.)")
    return dict(label=label, runs=rids, failed=failed, results=res_by_profile)
