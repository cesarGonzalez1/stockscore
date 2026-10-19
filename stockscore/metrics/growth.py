from ..models import div, cagr


def compute(snap, cfg, bench, m):
    out, notes = {}, []
    f0, f3 = snap.fy(0), snap.fy(3)
    if f0 and f3:
        out["rev_cagr_3y"] = cagr(f0["revenue"], f3["revenue"], 3)
        out["ni_cagr_3y"] = cagr(f0["net_income"], f3["net_income"], 3)
    t = snap.ttm
    if f0 and t.get("revenue"):
        out["rev_ttm_growth"] = div(t["revenue"], f0["revenue"]) - 1 if f0["revenue"] else None
        notes.append("rev_ttm_growth = TTM vs último año fiscal (no es interanual puro; mezcla 1-3 trimestres nuevos)")
    fe, ee = snap.market.get("forward_eps"), t.get("eps")
    if fe and ee and ee > 0:
        out["fwd_eps_growth"] = fe / ee - 1
    out["analyst_eps_growth_3y"] = snap.market.get("eps_growth_3y")
    return out, notes
