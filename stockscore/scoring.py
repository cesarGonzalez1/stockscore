from __future__ import annotations
from .config import load_config
from .metrics import compute_all
from .models import Result, Snapshot


def metric_score(x, spec):
    """Mapa lineal 0-100 entre low y high; None si no hay dato."""
    if x is None:
        return None
    lo, hi = spec["low"], spec["high"]
    frac = (x - lo) / (hi - lo) if spec["higher_better"] else (hi - x) / (hi - lo)
    return 100.0 * max(0.0, min(1.0, frac))


def score_pillars(metrics, cfg):
    """-> (pillars{name:{score,coverage}}, metric_scores)"""
    pillars, mscores = {}, {}
    for pname, specs in cfg["pillars"].items():
        wsum = wavail = acc = 0.0
        for sp in specs:
            w = sp["weight"]
            s = metric_score(metrics.get(sp["metric"]), sp)
            wsum += w
            if s is not None:
                mscores[sp["metric"]] = s
                acc += w * s
                wavail += w
        pillars[pname] = {"score": acc / wavail if wavail else None, "coverage": wavail / wsum if wsum else 0.0}
    return pillars, mscores


def combine(pillars, weights):
    """Media ponderada de pilares disponibles (renormaliza pesos). -> (total, coverage)"""
    tot_w = sum(weights.values())
    acc = av = 0.0
    for p, w in weights.items():
        sc = pillars.get(p, {}).get("score")
        if sc is not None and w > 0:
            acc += w * sc
            av += w * pillars[p]["coverage"]  # cobertura ponderada por completitud interna
    wsum_pos = sum(w for p, w in weights.items() if w > 0 and pillars.get(p, {}).get("score") is not None)
    total = acc / wsum_pos if wsum_pos else 0.0
    coverage = av / tot_w if tot_w else 0.0
    return total, coverage


def grade_of(total, cfg):
    g = cfg["grades"]
    for letter in ("A", "B", "C", "D"):
        if total >= g[letter]:
            return letter
    return "F"


def is_cyclical(snap, cfg):
    """Cíclica por sector (energía, materiales) o por industria (semiconductores)."""
    we = cfg["warnings"]
    ind = (snap.industry or "").lower()
    return snap.sector in we.get("cyclical_sectors", []) or any(k in ind for k in we.get("cyclical_industries", []))


def flags(metrics, cfg, snap=None):
    v, w = [], []
    ve, we = cfg["vetoes"], cfg["warnings"]
    z2, pf = metrics.get("altman_z2"), metrics.get("piotroski")
    if z2 is not None and z2 < ve["altman_z2_min"]:
        v.append(f"Zona de quiebra: Altman Z''={z2:.2f} < {ve['altman_z2_min']}")
    if pf is not None and pf < ve["piotroski_min"]:
        v.append(f"Calidad contable muy baja: Piotroski {pf}")
    if metrics.get("fcf_yield") is not None and metrics["fcf_yield"] < 0 and (metrics.get("earnings_yield") or 0) < 0:
        v.append("Pierde dinero y quema caja")
    if (metrics.get("rsi14") or 0) > we["rsi_overbought"]:
        w.append(f"RSI {metrics['rsi14']:.0f}: sobrecomprada (entrada tardía)")
    d = metrics.get("days_to_earnings")
    if d is not None and d <= we["earnings_soon_days"]:
        w.append(f"Earnings en {d} días: evento binario, el gap puede pasar tu stop")
    if metrics.get("dcf_mos") is not None and metrics["dcf_mos"] < we["dcf_far_above"]:
        w.append(f"Precio {abs(metrics['dcf_mos']):.0%} por encima del DCF base: depende de que el mercado siga pagando múltiplo")
    if metrics.get("hist_days", 999) < cfg["assumptions"]["short_history_days"]:
        w.append(f"Ventana de precios corta ({metrics.get('hist_days')} días): vol/swing/pendiente poco fiables")
    if metrics.get("vs_sma200") is not None and metrics["vs_sma200"] < 0 and (metrics.get("mom") or 0) < 0:
        w.append("Tendencia rota: bajo SMA200 y momentum negativo")
    if (metrics.get("mom") or 0) > we.get("parabolic_return", 1.5):
        w.append(f"Movimiento parabólico: {metrics['mom']:+.0%} en 12 meses; el momentum extremo suele revertirse")
    if (metrics.get("op_margin") or 0) > we.get("extreme_op_margin", 0.60):
        w.append(f"Margen operativo {metrics['op_margin']:.0%}: verifica el dato; si es real, probablemente es pico de ciclo")
    if snap is not None:
        if snap.sector in we.get("cyclical_sectors", []):
            w.append(f"Sector cíclico ({snap.sector}): FCF/EPS TTM dependen del precio de la materia prima; DCF y valor poco fiables")
        elif is_cyclical(snap, cfg):
            w.append(f"Industria cíclica ({snap.industry}): múltiplos bajos en el pico del ciclo engañan; señal limitada a VIGILAR")
        if snap.is_financial:
            w.append("Financiera: evaluación parcial (sin EV/FCF/ROIC/Altman); no compares su puntaje con no financieras")
    return v, w


def signal_of(total, pillars, vetoes, cov, cfg, cyclical=False):
    if vetoes:
        return "EVITAR"
    t = pillars.get("trend", {}).get("score") or 0
    if cov < cfg["warnings"]["min_coverage"]:
        return "DATOS INCOMPLETOS"
    if total >= 70 and t >= 60:
        if cyclical and cfg["warnings"].get("cyclical_cap_signal", True):
            return "VIGILAR"   # puntaje alto en cíclicas no está respaldado: exige revisión manual
        return "CANDIDATA"
    if total >= 60:
        return "VIGILAR"
    return "NO POR AHORA"


def score_from_metrics(snap, metrics, notes, cfg, profile="swing", weights=None) -> Result:
    weights = weights or cfg["profiles"][profile]
    pillars, mscores = score_pillars(metrics, cfg)
    total, cov = combine(pillars, weights)
    vetoes, warns = flags(metrics, cfg, snap)
    if cov < cfg["warnings"]["min_coverage"]:
        warns.append(f"Cobertura de datos {cov:.0%} < {cfg['warnings']['min_coverage']:.0%}")
    if vetoes:
        total = min(total, cfg["vetoes"]["veto_cap"])
    return Result(snap.ticker, snap.name, snap.sector, profile, round(total, 2), grade_of(total, cfg), round(cov, 3),
                  signal_of(total, pillars, vetoes, cov, cfg, is_cyclical(snap, cfg)), pillars, metrics, mscores, vetoes, warns, notes,
                  snap.as_of.isoformat())


def score_company(snap: Snapshot, cfg=None, profile="swing", bench=None) -> Result:
    cfg = cfg or load_config()
    metrics, notes = compute_all(snap, cfg, bench)
    return score_from_metrics(snap, metrics, notes, cfg, profile)


def score_universe(snaps, cfg=None, profile="swing", bench=None):
    """Puntúa una lista de Snapshots; devuelve lista de Result ordenada de mayor a menor."""
    cfg = cfg or load_config()
    res = []
    for s in snaps:
        try:
            res.append(score_company(s, cfg, profile, bench))
        except Exception as e:   # un ticker con datos raros no debe tumbar todo el ranking
            import sys
            print(f"! {s.ticker}: omitida ({type(e).__name__}: {e})", file=sys.stderr)
    return sorted(res, key=lambda r: -r.total)
