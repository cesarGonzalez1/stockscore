from ..models import div


def piotroski(snap):
    """Piotroski F-Score (9 señales) con el último año fiscal vs el anterior. None si faltan datos."""
    a, b = snap.fy(0), snap.fy(1)
    if not a or not b:
        return None, {}
    c = snap.fy(2)
    ta_avg0 = (a["total_assets"] + b["total_assets"]) / 2
    ta_avg1 = (b["total_assets"] + c["total_assets"]) / 2 if c else b["total_assets"]
    roa0, roa1 = a["net_income"] / ta_avg0, b["net_income"] / ta_avg1
    def ratio(x, y):
        return x / y if y else None

    def gt(x, y):
        return (x is not None and y is not None) and x > y

    def lt(x, y):
        return (x is not None and y is not None) and x < y

    sig = {
        "ROA>0": a["net_income"] > 0,
        "CFO>0": a["cfo"] > 0,
        "ΔROA>0": roa0 > roa1,
        "CFO>NI": a["cfo"] > a["net_income"],
        "ΔApalancamiento<0": lt(a["long_term_debt"] / ta_avg0, b["long_term_debt"] / ta_avg1),
        "ΔLiquidez>0": gt(ratio(a["current_assets"], a["current_liabilities"]), ratio(b["current_assets"], b["current_liabilities"])),
        "Sin dilución": a["shares_m"] <= b["shares_m"],
        "ΔMargen bruto>0": gt(ratio(a["gross_profit"], a["revenue"]), ratio(b["gross_profit"], b["revenue"])),
        "ΔRotación activos>0": a["revenue"] / ta_avg0 > b["revenue"] / ta_avg1,
    }
    return sum(sig.values()), sig


def altman(snap):
    """Devuelve (Z original, Z'' no-manufactureras) con balance anual + capitalización actual."""
    f = snap.fy(0)
    if not f:
        return None, None
    ta, tl = f["total_assets"], f.get("total_liabilities") or 0
    wc = f["current_assets"] - f["current_liabilities"]
    x1, x2, x3 = wc / ta, f["retained_earnings"] / ta, f["operating_income"] / ta
    x5 = f["revenue"] / ta
    mve = snap.market_cap
    z = None
    if not tl or tl <= 0:   # sin pasivos (o dato faltante): no definido
        return None, None
    if mve:
        z = 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * (mve / tl) + 1.0 * x5
    z2 = 6.56 * x1 + 3.26 * x2 + 6.72 * x3 + 1.05 * (f["equity"] / tl)
    return z, z2


def compute(snap, cfg, bench, m):
    out, notes = {}, []
    f0, f3 = snap.fy(0), snap.fy(3) or snap.fy(len(snap.fiscal) - 1)
    t = snap.ttm
    tax = cfg["assumptions"]["tax_rate"]
    if f0:
        p, sig = piotroski(snap)
        out["piotroski"] = p
        out["_piotroski_signals"] = sig
        z, z2 = altman(snap)
        out["altman_z"], out["altman_z2"] = z, z2
        out["gross_profitability"] = div(f0["gross_profit"], f0["total_assets"])
        ic = f0["equity"] + f0["total_debt"] - f0["cash_st"]
        ebit = t.get("operating_income") or f0["operating_income"]
        out["roic"] = ebit * (1 - tax) / ic if ic > 0 else None
        if ic <= 0:
            notes.append("Capital invertido <= 0: ROIC no definido")
        ni_ttm = t.get("net_income") if t.get("net_income") is not None else f0["net_income"]
        out["roe"] = ni_ttm / f0["equity"] if f0["equity"] and f0["equity"] > 0 else None
        out["op_margin"] = div(ebit, t.get("revenue") or f0["revenue"])
        avg_ta = ((f0["total_assets"] + snap.fy(1)["total_assets"]) / 2) if snap.fy(1) else f0["total_assets"]
        out["accruals"] = (f0["net_income"] - f0["cfo"]) / avg_ta
        if f3 and f3 is not f0:
            if f0["revenue"] and f3["revenue"]:
                out["margin_trend"] = f0["operating_income"] / f0["revenue"] - f3["operating_income"] / f3["revenue"]
        ebitda = t.get("ebitda")
        out["net_debt_ebitda"] = div(f0["total_debt"] - f0["cash_st"], ebitda) if ebitda else None
        if out["net_debt_ebitda"] is not None and out["net_debt_ebitda"] < 0:
            out["net_debt_ebitda"] = 0.0  # caja neta = lo mejor
    out["fcf_conversion"] = div(t.get("fcf"), t.get("net_income")) if (t.get("net_income") or 0) > 0 else None
    notes.append("Altman Z'' usa fiscal anual; el Z original (altman_z) usa capitalización actual y difiere de sitios que usan TTM")
    return out, notes
