"""Validación HACIA ADELANTE: ¿el top-N de una corrida guardada rindió más que el resto y que SPY después?
Es la única validación limpia (sin sesgo de mirada al futuro). Solo es concluyente tras varias corridas y semanas."""
from __future__ import annotations
import datetime as dt
import pandas as pd
from .stats import spearman

HORIZONS = (1, 2, 4, 8, 12)   # semanas


def forward_report(store, run_id, price_fn, horizons=HORIZONS, top=10, today=None) -> dict:
    info = store.run_info(run_id)
    if not info:
        raise ValueError(f"corrida {run_id} no existe")
    rk = store.ranking(run_id)
    as_of = pd.Timestamp(info["as_of"])
    tickers = list(rk.ticker)
    px = price_fn(tickers + ["SPY"], (as_of - pd.Timedelta(days=7)).date())
    px = px.copy(); px.index = pd.to_datetime(px.index)
    after = px[px.index > as_of]
    out = {"info": info, "horizons": pd.DataFrame(), "picks": pd.DataFrame(), "status": "ok"}
    if after.empty:
        out["status"] = "Aún no hay cierres posteriores a la corrida: espera al menos un día hábil"
        return out
    entry_date, entry = after.index[0], after.iloc[0]       # entrada = primer cierre DESPUÉS de la señal (realista)
    last_date = px.index[-1]
    top_t = list(rk.head(top).ticker)
    rows = []
    for h in horizons:
        target = entry_date + pd.Timedelta(weeks=h)
        if last_date < target - pd.Timedelta(days=3):
            rows.append(dict(semanas=h, estado=f"pendiente ({(target - last_date).days} días)"))
            continue
        pt = px[px.index <= target].iloc[-1]
        ret = (pt / entry - 1).drop(labels=["SPY"], errors="ignore")
        spy = float(pt["SPY"] / entry["SPY"] - 1) if "SPY" in px and entry.get("SPY") == entry.get("SPY") else float("nan")
        r_top, r_all = ret.reindex(top_t).dropna(), ret.dropna()
        rest = r_all.drop(labels=[t for t in top_t if t in r_all.index])
        sc = rk.set_index("ticker")["total"]
        rows.append(dict(semanas=h, estado="listo", n_top=len(r_top), top_prom=r_top.mean(), resto_prom=rest.mean() if len(rest) else float("nan"),
                         universo=r_all.mean(), spy=spy, top_vs_spy=r_top.mean() - spy,
                         top_vs_resto=r_top.mean() - rest.mean() if len(rest) else float("nan"),
                         pct_top_gana_spy=float((r_top > spy).mean()) if len(r_top) else float("nan"),
                         ic_spearman=spearman(sc.reindex(r_all.index), r_all)))
    out["horizons"] = pd.DataFrame(rows)
    last = px.iloc[-1]
    picks = rk.head(top)[["rank", "ticker", "total"]].copy()
    picks["ret_a_hoy"] = [float(last[t] / entry[t] - 1) if t in px and entry.get(t) == entry.get(t) else float("nan") for t in picks.ticker]
    out["picks"] = picks
    out["entry_date"], out["last_date"] = entry_date.date(), last_date.date()
    return out


def format_forward(rep) -> str:
    i = rep["info"]
    L = [f"FORWARD de corrida #{i['id']} (perfil={i['profile']}, etiqueta='{i['label']}', datos al {i['as_of']})"]
    if rep["status"] != "ok":
        return "\n".join(L + [rep["status"]])
    L.append(f"Entrada: cierre del {rep['entry_date']} · último dato: {rep['last_date']}")
    h = rep["horizons"]
    for _, r in h.iterrows():
        if r["estado"] != "listo":
            L.append(f"  {int(r['semanas']):>2} sem: {r['estado']}")
        else:
            L.append(f"  {int(r['semanas']):>2} sem: top {r['top_prom']:+.1%} | resto {r['resto_prom']:+.1%} | SPY {r['spy']:+.1%} | "
                     f"top−SPY {r['top_vs_spy']:+.1%} | top gana a SPY {r['pct_top_gana_spy']:.0%} | IC {r['ic_spearman']:+.2f} (n={int(r['n_top'])})")
    L += ["", "Picks (retorno desde la entrada hasta hoy):", rep["picks"].round(3).to_string(index=False), "",
          "Lectura: IC>0 sostenido en muchas corridas = el puntaje ordena bien. Una sola corrida NO prueba nada."]
    return "\n".join(L)
