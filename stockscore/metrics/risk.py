import numpy as np


def swing_probability(sigma_ann, mu_ann, target, stop, horizon, sims=4000, seed=7):
    """P(tocar +target antes que -stop dentro de `horizon` días hábiles) con GBM. Retorna (p_up, p_stop, p_neither)."""
    rng = np.random.default_rng(seed)
    dt = 1 / 252
    z = rng.standard_normal((sims, horizon))
    logret = (mu_ann - 0.5 * sigma_ann ** 2) * dt + sigma_ann * np.sqrt(dt) * z
    path = np.exp(np.cumsum(logret, axis=1)) - 1
    up, dn = path >= target, path <= -stop
    first_up = np.where(up.any(1), up.argmax(1), horizon + 1)
    first_dn = np.where(dn.any(1), dn.argmax(1), horizon + 1)
    p_up = float(np.mean(first_up < first_dn))
    p_dn = float(np.mean(first_dn < first_up))
    return p_up, p_dn, 1 - p_up - p_dn


def compute(snap, cfg, bench, m):
    out, notes = {}, []
    a = cfg["assumptions"]
    c = snap.closes().iloc[-a.get("risk_window_days", 504):]
    n = len(c)
    out["beta"] = snap.market.get("beta")
    if n >= 30:
        r = np.log(c).diff().dropna()
        vol = float(r.std(ddof=1) * np.sqrt(252))
        out["vol_ann"] = vol
        out["max_drawdown"] = float((c / c.cummax() - 1).min())
        beta = out["beta"] if out["beta"] is not None else 1.0
        mu = a["risk_free"] + beta * a["equity_premium"]
        s = a["swing"]
        pu, pd_, _ = swing_probability(vol, mu, s["target"], s["stop"], s["horizon_days"], s["sims"], s["seed"])
        out["swing_prob"], out["swing_stop_prob"] = pu, pd_
        notes.append(f"Vol/DD/swing_prob calculados con {n} cierres ({'ventana corta: poco fiables' if n < a['short_history_days'] else 'ok'}); drift CAPM supuesto")
    else:
        notes.append("Sin historial de precios suficiente (<30): sin volatilidad ni swing_prob")
    return out, notes
