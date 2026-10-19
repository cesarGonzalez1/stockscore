import datetime as dt
from ..models import div

CONSENSUS = {"strong buy": 5, "buy": 4, "outperform": 4, "hold": 3, "neutral": 3, "underperform": 2, "sell": 2, "strong sell": 1}


def compute(snap, cfg, bench, m):
    out, notes = {}, []
    a = cfg["assumptions"]
    out["analyst_upside"] = div(snap.market.get("analyst_target"), snap.price) - 1 if snap.market.get("analyst_target") and snap.price else None
    cs = snap.market.get("analyst_consensus")
    if cs:
        out["consensus_score"] = CONSENSUS.get(str(cs).lower())
    days = None
    for e in snap.events:
        if e.get("type") == "earnings":
            d = (dt.date.fromisoformat(e["date"]) - snap.as_of).days
            if d >= 0 and (days is None or d < days):
                days = d
    out["days_to_earnings"] = days
    lo, hi = a["earnings_window_days"]
    out["event_in_window"] = 1.0 if (days is not None and lo <= days <= hi) else 0.0
    if days is None:
        notes.append("Sin fecha de earnings conocida (event_in_window=0)")
    return out, notes
