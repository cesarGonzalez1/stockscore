from .metrics.valuation import sensitivity_grid

LABELS = {
 "fcf_yield": "FCF yield", "earnings_yield": "Earnings yield", "ev_ebit": "EV/EBIT", "peg": "PEG", "growth_headroom": "Holgura crecimiento (esperado − implícito)",
 "dcf_mos": "Margen vs DCF", "book_to_price": "Valor en libros / precio", "roe": "ROE", "piotroski": "Piotroski (0-9)", "altman_z2": "Altman Z''", "roic": "ROIC", "gross_profitability": "Gross profitability (GP/Activos)",
 "op_margin": "Margen operativo", "fcf_conversion": "FCF/Utilidad", "accruals": "Accruals (Sloan)", "margin_trend": "Tendencia margen op. (3a)",
 "net_debt_ebitda": "Deuda neta/EBITDA", "rev_cagr_3y": "Ingresos CAGR 3a", "ni_cagr_3y": "Utilidad CAGR 3a", "rev_ttm_growth": "Ingresos TTM vs FY",
 "fwd_eps_growth": "EPS adelantado vs TTM", "analyst_eps_growth_3y": "Crec. EPS 3a analistas", "mom": "Momentum", "vs_sma200": "Precio vs SMA200",
 "sma50_vs_200": "SMA50 vs SMA200", "slope_t": "Pendiente (t-stat 60d)", "rel_strength": "Fuerza relativa vs SPY", "vol_ann": "Volatilidad anual",
 "max_drawdown": "Máx. drawdown (ventana)", "beta": "Beta", "swing_prob": "P(+objetivo antes que −stop)", "analyst_upside": "Upside a precio objetivo",
 "consensus_score": "Consenso (1-5)", "event_in_window": "Earnings en ventana"}
PCT = {"book_to_price","roe","fcf_yield","earnings_yield","dcf_mos","roic","gross_profitability","op_margin","accruals","margin_trend","rev_cagr_3y","ni_cagr_3y",
       "rev_ttm_growth","fwd_eps_growth","analyst_eps_growth_3y","mom","vs_sma200","sma50_vs_200","rel_strength","vol_ann","max_drawdown",
       "swing_prob","analyst_upside","growth_headroom","implied_growth","base_growth"}


def fmt(k, v):
    if v is None: return "—"
    if k in PCT: return f"{v:+.1%}" if k in {"dcf_mos","mom","vs_sma200","sma50_vs_200","rel_strength","analyst_upside","growth_headroom","margin_trend","rev_ttm_growth","fwd_eps_growth"} else f"{v:.1%}"
    return f"{v:.2f}"


def company_report(r, snap=None, cfg=None) -> str:
    L = [f"{'='*72}", f"{r.ticker} — {r.name}  [{r.sector}]  perfil={r.profile}  datos al {r.as_of}", f"{'='*72}",
         f"PUNTAJE {r.total:.1f}/100  nota {r.grade}  señal: {r.signal}  cobertura datos {r.coverage:.0%}", "", "Pilares:"]
    for p, v in r.pillars.items():
        bar = "█" * int((v["score"] or 0) / 5)
        L.append(f"  {p:<10} {('—' if v['score'] is None else f'{v['score']:5.1f}')}  {bar:<20} (cobertura {v['coverage']:.0%})")
    L += ["", "Métricas (valor → puntaje 0-100):"]
    for k, lab in LABELS.items():
        if k in r.metrics or k in r.metric_scores:
            sc = r.metric_scores.get(k)
            L.append(f"  {lab:<44} {fmt(k, r.metrics.get(k)):>9}   {'—' if sc is None else f'{sc:5.0f}'}")
    ig, gb = r.metrics.get("implied_growth"), r.metrics.get("base_growth")
    if ig is not None:
        L += ["", f"DCF inverso: el precio actual exige crecimiento inicial de FCF ≈ {ig:.1%}/año (se desvanece a g terminal). "
              f"Crecimiento base esperado ≈ {gb:.1%}" if gb is not None else ""]
    if r.metrics.get("dcf_value_ps"):
        L.append(f"Valor DCF base por acción ≈ {r.metrics['dcf_value_ps']:.2f}")
    if snap is not None and cfg is not None and snap.ttm.get("fcf", 0) and snap.ttm["fcf"] > 0:
        g = sensitivity_grid(snap, cfg)
        gs = list(next(iter(g.values())).keys())
        L += ["", "Sensibilidad valor/acción (filas=tasa descuento, columnas=crec. inicial FCF):", "         " + "".join(f"{x:>9.0%}" for x in gs)]
        for rr, row in g.items():
            L.append(f"  {rr:>5.0%}  " + "".join(f"{row[x]:>9.1f}" for x in gs))
    if r.vetoes: L += ["", "VETOS:"] + [f"  ✗ {x}" for x in r.vetoes]
    if r.warnings: L += ["", "ALERTAS:"] + [f"  ! {x}" for x in r.warnings]
    if r.notes: L += ["", "Notas de método:"] + [f"  · {x}" for x in dict.fromkeys(r.notes)]
    return "\n".join(L)


def compare_table(results) -> str:
    """Tabla lado a lado de pilares y métricas clave para 2+ empresas."""
    keys = [("total", "PUNTAJE"), ("grade", "Nota"), ("signal", "Señal")]
    cols = [r.ticker for r in results]
    L = [f"{'':<36}" + "".join(f"{c:>12}" for c in cols)]
    L.append(f"{'PUNTAJE':<36}" + "".join(f"{r.total:>12.1f}" for r in results))
    L.append(f"{'Nota / señal':<36}" + "".join(f"{r.grade + ' ' + r.signal[:8]:>12}" for r in results))
    L.append("-" * (36 + 12 * len(cols)))
    for p in ("value", "quality", "growth", "trend", "risk", "catalysts"):
        L.append(f"{'Pilar ' + p:<36}" + "".join(f"{('—' if r.pillars[p]['score'] is None else format(r.pillars[p]['score'], '.1f')):>12}" for r in results))
    L.append("-" * (36 + 12 * len(cols)))
    for k in ("fcf_yield", "ev_ebit", "dcf_mos", "piotroski", "altman_z2", "roic", "op_margin", "rev_ttm_growth", "mom", "vs_sma200",
              "rel_strength", "vol_ann", "beta", "analyst_upside"):
        L.append(f"{LABELS.get(k, k):<36}" + "".join(f"{fmt(k, r.metrics.get(k)):>12}" for r in results))
    L.append("-" * (36 + 12 * len(cols)))
    L.append(f"{'Vetos / alertas':<36}" + "".join(f"{str(len(r.vetoes)) + ' / ' + str(len(r.warnings)):>12}" for r in results))
    return "\n".join(L)
