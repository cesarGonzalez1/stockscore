"""Plan de operación swing: stop por volatilidad, objetivo, riesgo/beneficio y tamaño de posición por riesgo fijo.
Es una calculadora de disciplina (cuánto arriesgar), NO una señal de compra."""
import math
from .metrics.risk import swing_probability


def trade_plan(snap, result, cfg, capital, risk_pct=0.01, fx=1.0, max_position_pct=0.25, stop_mult=1.5, target_pct=None):
    """capital: en tu moneda (p. ej. MXN). fx: unidades de tu moneda por 1 USD (MXN→ usa ~ tipo de cambio). risk_pct: fracción del capital que aceptas perder."""
    a = cfg["assumptions"]
    px = snap.price
    vol = result.metrics.get("vol_ann")
    if not px or not vol:
        raise ValueError("Sin precio o volatilidad: baja datos con 'fetch' (se necesitan ≥30 cierres)")
    weekly_sigma = vol / math.sqrt(52)
    stop_pct = min(0.12, max(0.03, stop_mult * weekly_sigma))
    tgt = target_pct or a["swing"]["target"]
    risk_amt = capital * risk_pct
    risk_per_share = px * fx * stop_pct
    shares = risk_amt / risk_per_share
    pos_value = shares * px * fx
    cap_value = capital * max_position_pct
    capped = pos_value > cap_value
    if capped:
        shares, pos_value = cap_value / (px * fx), cap_value
    beta = result.metrics.get("beta") or 1.0
    mu = a["risk_free"] + beta * a["equity_premium"]
    pu, pdn, _ = swing_probability(vol, mu, tgt, stop_pct, a["swing"]["horizon_days"], a["swing"]["sims"], a["swing"]["seed"])
    rr = tgt / stop_pct
    be = stop_pct / (stop_pct + tgt)   # prob. mínima de acierto para no perder en promedio
    plan = dict(ticker=snap.ticker, precio=px, stop_pct=stop_pct, stop=px * (1 - stop_pct), objetivo_pct=tgt, objetivo=px * (1 + tgt),
                riesgo_beneficio=rr, prob_acierto_necesaria=be, prob_sim_objetivo=pu, prob_sim_stop=pdn,
                acciones=shares, valor_posicion=pos_value, pct_capital=pos_value / capital,
                perdida_max=shares * px * fx * stop_pct, limitado_por_tamano_max=capped, dias_a_earnings=result.metrics.get("days_to_earnings"),
                puntaje=result.total, senal=result.signal)
    return plan


def format_plan(p, moneda="MXN") -> str:
    L = [f"PLAN SWING · {p['ticker']} · puntaje {p['puntaje']:.1f} · señal {p['senal']}",
         f"  Precio ref.: {p['precio']:.2f}   Stop: {p['stop']:.2f} (−{p['stop_pct']:.1%}, ≈1.5× volatilidad semanal)   Objetivo: {p['objetivo']:.2f} (+{p['objetivo_pct']:.0%})",
         f"  Riesgo/beneficio: {p['riesgo_beneficio']:.2f}   Necesitas acertar ≥ {p['prob_acierto_necesaria']:.0%} para no perder en promedio",
         f"  Simulación (42 días, deriva CAPM): toca objetivo primero {p['prob_sim_objetivo']:.0%} · toca stop primero {p['prob_sim_stop']:.0%}",
         f"  Posición: {p['acciones']:.3f} acciones = {p['valor_posicion']:,.0f} {moneda} ({p['pct_capital']:.0%} del capital) · pérdida máxima si toca stop ≈ {p['perdida_max']:,.0f} {moneda}"]
    if p["limitado_por_tamano_max"]:
        L.append("  (tamaño recortado al máximo por posición)")
    d = p["dias_a_earnings"]
    if d is not None and d <= 14:
        L.append(f"  ⚠ Earnings en {d} días: puede abrir con gap y saltarse el stop. Considera esperar o reducir tamaño.")
    if p["riesgo_beneficio"] < 1.5:
        L.append("  ⚠ Riesgo/beneficio < 1.5: el stop por volatilidad es ancho frente al objetivo; busca otro objetivo o descarta.")
    if p["prob_sim_objetivo"] < p["prob_acierto_necesaria"]:
        L.append("  ⚠ La probabilidad simulada de llegar al objetivo es menor que la necesaria: matemáticamente desfavorable con estos parámetros.")
    if p["senal"] in ("EVITAR", "NO POR AHORA", "DATOS INCOMPLETOS"):
        L.append(f"  ⚠ Señal del sistema: {p['senal']}. Este plan es solo aritmética de riesgo; el scorecard NO respalda esta operación hoy.")
    L.append("  (Calculadora de disciplina: no es recomendación ni garantiza resultado.)")
    return "\n".join(L)
