from . import valuation, quality, growth, trend, risk, catalysts


def compute_all(snap, cfg, bench=None) -> tuple[dict, list]:
    """Calcula todas las métricas crudas. Devuelve (metrics, notes). Las notas explican fallbacks/limitaciones."""
    m, notes = {}, []
    for mod in (growth, quality, valuation, trend, risk, catalysts):  # orden: valuation usa growth
        out, n = mod.compute(snap, cfg, bench, m)
        m.update(out)
        notes += n
    if snap.is_financial:
        for k in ("fcf_yield", "ev_ebit", "ev_ebitda", "net_debt_ebitda", "roic", "gross_profitability", "fcf_conversion",
                  "altman_z", "altman_z2", "implied_growth", "base_growth", "growth_headroom", "dcf_value_ps", "dcf_mos",
                  "accruals", "op_margin", "margin_trend", "peg"):
            if k in m:
                m[k] = None
        notes.append("Financiera (banco/seguro): EV, FCF, ROIC, Altman y DCF no aplican; se usan P/E, valor en libros y ROE. Evaluación PARCIAL")
    return m, notes
