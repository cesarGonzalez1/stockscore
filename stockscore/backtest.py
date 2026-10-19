"""Backtest SOLO de señales de PRECIO (momentum/tendencia): usa únicamente datos pasados en cada fecha, sin fundamentales,
así que no tiene sesgo de mirada al futuro. Aun así: sesgo de supervivencia (universo = empresas que hoy existen/grandes),
muestra corta (~2 años en Yahoo) y periodos solapados. Resultado = indicio, no prueba."""
import numpy as np
import pandas as pd
from .metrics.trend import slope_tstat
from .scoring import metric_score
from .stats import spearman, tstat


def price_frame(snaps) -> pd.DataFrame:
    cols = {s.ticker: s.closes() for s in snaps if len(s.closes()) > 0}
    return pd.DataFrame(cols).sort_index().ffill(limit=3).dropna(how="all")


def trend_signals(c: pd.Series, cfg) -> dict | None:
    """Señales con precios hasta hoy (c termina en la fecha de decisión). Misma lógica del pilar de tendencia, sin fuerza relativa."""
    if len(c) < 253:
        return None
    sig = {"mom": c.iloc[-22] / c.iloc[-253] - 1, "vs_sma200": c.iloc[-1] / c.iloc[-200:].mean() - 1,
           "sma50_vs_200": c.iloc[-50:].mean() / c.iloc[-200:].mean() - 1, "slope_t": slope_tstat(c)}
    specs = {sp["metric"]: sp for sp in cfg["pillars"]["trend"]}
    num = den = 0.0
    for k, v in sig.items():
        sc = metric_score(v, specs[k]) if v is not None else None
        if sc is not None:
            num += specs[k]["weight"] * sc; den += specs[k]["weight"]
    sig["trend_score"] = num / den if den else None
    return sig


def run_price_backtest(snaps, cfg, horizon=21, step=21, top=10) -> dict:
    P = price_frame(snaps)
    rows = []
    for i in range(252, len(P) - horizon, step):
        sig = {}
        for t in P.columns:
            s = P[t].iloc[: i + 1].dropna()
            r = trend_signals(s, cfg) if len(s) >= 253 and P[t].iloc[i] == P[t].iloc[i] else None
            if r:
                sig[t] = r
        if len(sig) < 8:
            continue
        df = pd.DataFrame(sig).T
        df["fwd"] = P.iloc[i + horizon] / P.iloc[i] - 1
        df = df.dropna(subset=["fwd", "trend_score"])
        k = min(top, max(3, len(df) // 5))
        topk, botk = df.nlargest(k, "trend_score"), df.nsmallest(k, "trend_score")
        rows.append(dict(fecha=P.index[i].date(), n=len(df), ic_mom=spearman(df["mom"], df["fwd"]),
                         ic_vs_sma200=spearman(df["vs_sma200"], df["fwd"]), ic_trend=spearman(df["trend_score"], df["fwd"]),
                         top=topk["fwd"].mean(), universo=df["fwd"].mean(), fondo=botk["fwd"].mean()))
    res = pd.DataFrame(rows)
    summ = {"periodos": len(res), "horizonte_dias": horizon, "step": step}
    if len(res):
        for c in ("ic_mom", "ic_vs_sma200", "ic_trend"):
            summ[c] = dict(media=float(res[c].mean()), t=tstat(res[c]), pct_pos=float((res[c] > 0).mean()))
        ex = res["top"] - res["universo"]
        summ["top_vs_universo"] = dict(media=float(ex.mean()), t=tstat(ex), pct_gana=float((ex > 0).mean()))
        summ["top_vs_fondo"] = float((res["top"] - res["fondo"]).mean())
    return {"detalle": res, "resumen": summ}


def format_backtest(r) -> str:
    s = r["resumen"]
    if not s["periodos"]:
        return "Sin datos suficientes: se necesitan ≥ 8 empresas con ≥ 273 cierres diarios."
    L = [f"Backtest de PRECIO · {s['periodos']} rebalanceos · horizonte {s['horizonte_dias']} días hábiles",
         "IC = correlación (Spearman) entre señal y retorno posterior; t≥2 sugiere que no es azar.", ""]
    for k, lab in (("ic_mom", "Momentum 12-1"), ("ic_vs_sma200", "Precio vs SMA200"), ("ic_trend", "Pilar tendencia (compuesto)")):
        v = s[k]; L.append(f"  {lab:<30} IC medio {v['media']:+.3f}  t={v['t']:+.1f}  periodos con IC>0: {v['pct_pos']:.0%}")
    v = s["top_vs_universo"]
    L += ["", f"  Top por tendencia vs universo: {v['media']:+.2%} por periodo (t={v['t']:+.1f}, gana {v['pct_gana']:.0%} de las veces)",
          f"  Top vs fondo (peores): {s['top_vs_fondo']:+.2%} por periodo", "",
          f"LÍMITES: sesgo de supervivencia (solo empresas que hoy existen), {s['periodos']} rebalanceos ≈ {s['periodos'] * s['horizonte_dias'] / 252:.1f} años"
          + ("" if s.get("step", s["horizonte_dias"]) >= s["horizonte_dias"] else ", periodos que se solapan") + ", empresas muy correlacionadas entre sí, sin costos ni impuestos. Indicio, no prueba."]
    return "\n".join(L)
