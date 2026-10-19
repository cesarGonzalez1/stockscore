from ..models import div


def project_pv(fcf0, g, r, g_term, years):
    """Valor presente de flujos con crecimiento que se desvanece linealmente de g a g_term + valor terminal."""
    total, f = 0.0, fcf0
    for t in range(1, years + 1):
        gt = g_term + (g - g_term) * (years - t + 1) / years
        f *= 1 + gt
        total += f / (1 + r) ** t
    tv = f * (1 + g_term) / (r - g_term) / (1 + r) ** years
    return total + tv


def implied_growth(fcf0, target_value, r, g_term, years, lo=-0.30, hi=0.80):
    """DCF inverso: crecimiento inicial (que se desvanece) que justifica el precio actual. Bisección."""
    if fcf0 is None or fcf0 <= 0 or target_value is None or target_value <= 0:
        return None
    if project_pv(fcf0, lo, r, g_term, years) > target_value:
        return lo
    if project_pv(fcf0, hi, r, g_term, years) < target_value:
        return hi
    for _ in range(80):
        mid = (lo + hi) / 2
        if project_pv(fcf0, mid, r, g_term, years) < target_value:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def dcf_value_per_share(snap, fcf0, g, a):
    ev_iv = project_pv(fcf0, g, a["discount_rate"], a["terminal_growth"], a["dcf_years"])
    net_cash = (snap.market_cap - snap.enterprise_value) if (snap.market_cap and snap.enterprise_value) else 0
    return (ev_iv + net_cash) / snap.shares_m


def sensitivity_grid(snap, cfg, growths=(0.04, 0.08, 0.12, 0.16), rates=(0.08, 0.09, 0.10)):
    """Valor intrínseco por acción para una rejilla (crecimiento inicial x tasa de descuento)."""
    a = dict(cfg["assumptions"])
    fcf0 = normalized_ttm(snap, cfg)[0].get("fcf")
    grid = {}
    for r in rates:
        a["discount_rate"] = r
        grid[r] = {g: dcf_value_per_share(snap, fcf0, g, a) for g in growths}
    return grid


def _avg(vals):
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None


def normalized_ttm(snap, cfg):
    """Sectores cíclicos (energía, materiales): FCF/utilidad/EBIT de un solo año dependen del precio de la materia
    prima. Se usa el promedio de TTM + hasta 3 años fiscales (4 puntos) para no premiar el pico del ciclo."""
    t = dict(snap.ttm)
    if snap.sector not in cfg["warnings"].get("cyclical_sectors", []):
        return t, False
    fy = snap.fiscal[:3]
    def fcf_fy(f):
        return f["cfo"] - abs(f["capex"]) if f.get("cfo") is not None and f.get("capex") is not None else None
    for key, getter in (("fcf", fcf_fy), ("net_income", lambda f: f.get("net_income")),
                        ("operating_income", lambda f: f.get("operating_income")),
                        ("ebitda", lambda f: (f["operating_income"] + (f.get("da") or 0)) if f.get("operating_income") is not None else None)):
        v = _avg([t.get(key)] + [getter(f) for f in fy])
        if v is not None:
            t[key] = v
    return t, True


def compute(snap, cfg, bench, m):
    out, notes = {}, []
    a = cfg["assumptions"]
    t, norm = normalized_ttm(snap, cfg)
    mc, ev, px = snap.market_cap, snap.enterprise_value, snap.price
    if norm:
        notes.append("Sector cíclico: FCF, utilidad y EBIT = promedio de TTM + 3 años fiscales (normalizado al ciclo)")
    fcf = t.get("fcf")
    out["fcf_yield"] = div(fcf, mc)
    out["earnings_yield"] = div(t.get("net_income"), mc)
    out["ev_ebit"] = div(ev, t.get("operating_income")) if (t.get("operating_income") or 0) > 0 else None
    out["ev_ebitda"] = div(ev, t.get("ebitda")) if (t.get("ebitda") or 0) > 0 else None
    f0 = snap.fy(0)
    out["book_to_price"] = div(f0["equity"], mc) if (f0 and f0["equity"] and f0["equity"] > 0) else None
    out["pe"] = snap.market.get("pe")
    out["forward_pe"] = snap.market.get("forward_pe")
    eg = snap.market.get("eps_growth_3y")
    pe = snap.market.get("forward_pe") or snap.market.get("pe")
    out["peg"] = pe / (eg * 100) if (pe and eg and eg > 0) else None

    # DCF inverso y DCF directo
    if fcf and fcf > 0 and ev:
        ig = implied_growth(fcf, ev, a["discount_rate"], a["terminal_growth"], a["dcf_years"])
        out["implied_growth"] = ig
        mk = snap.market
        # Estimadores de crecimiento esperado (prospectivos primero). Cada uno se acota a [-5%, tope] para que
        # un EPS adelantado distorsionado (non-GAAP vs GAAP) no infle el DCF. El CAGR histórico solo si no hay otro.
        raw = [mk.get("eps_growth_3y"), mk.get("revenue_growth_3y"), m.get("fwd_eps_growth"), m.get("rev_ttm_growth")]
        cands = [max(-0.05, min(a["growth_cap"], x)) for x in raw if x is not None]
        if not cands and m.get("rev_cagr_3y") is not None:
            cands = [max(-0.05, min(a["growth_cap"], m["rev_cagr_3y"]))]
            notes.append("Sin estimaciones prospectivas: crecimiento base = CAGR histórico de ingresos (conservador)")
        if cands:
            gb = sum(cands) / len(cands)
            out["base_growth"] = gb
            out["growth_headroom"] = gb - ig
            ivps = dcf_value_per_share(snap, fcf, gb, a)
            out["dcf_value_ps"] = ivps
            out["dcf_mos"] = ivps / px - 1 if px else None
        notes.append("DCF parte de FCF TTM (incluye SBC como ingreso: sobrestima FCF en tecnológicas); supuestos r/g en config")
    else:
        notes.append("FCF TTM <= 0 o sin EV: DCF y DCF inverso no aplican")
    return out, notes
