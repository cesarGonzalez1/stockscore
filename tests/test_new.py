import math, datetime as dt, pathlib
import numpy as np, pandas as pd, pytest
from stockscore.config import load_config
from stockscore.models import Snapshot
from stockscore.providers import get_provider
from stockscore.scoring import score_company, score_universe
from stockscore.storage import Store
from stockscore.synthetic import synthetic_universe
from stockscore.stats import spearman, tstat
from stockscore.metrics import compute_all
from stockscore.forward import forward_report, format_forward
from stockscore.backtest import run_price_backtest, format_backtest, trend_signals
from stockscore.plan import trade_plan, format_plan
from stockscore.journal import Journal
from stockscore.workflow import run_weekly, auto_label
from stockscore.report import compare_table

CFG = load_config()
FIX = str(pathlib.Path(__file__).resolve().parent / "fixtures")
P = get_provider("snapshot", directory=FIX)
SPY = P.get("SPY")


def test_spearman_known_values():
    assert spearman([1, 2, 3, 4], [1, 3, 2, 4]) == pytest.approx(0.8)
    assert spearman([1, 2, 3], [3, 2, 1]) == pytest.approx(-1)
    assert math.isnan(spearman([1, 1, 1], [1, 2, 3]))
    assert tstat([1, 2, 3, 4]) > 2


def test_spearman_aligns_by_index():
    a = pd.Series([1, 2, 3, 4], index=list("abcd")); b = pd.Series([4, 3, 2, 1], index=list("dcba"))
    assert spearman(a, b) == pytest.approx(1.0)


# ---------- financieras y cíclicas ----------
def test_bank_metrics_not_applicable_and_flagged():
    d = P.get("AAPL").d; d["industry"] = "Banks - Diversified"
    s = Snapshot(d)
    m, notes = compute_all(s, CFG, SPY)
    assert m["altman_z2"] is None and m["fcf_yield"] is None and m["ev_ebit"] is None
    assert m.get("roe") is not None and m.get("book_to_price") is not None
    r = score_company(s, CFG, "swing", SPY)
    assert not r.vetoes                       # un banco no se veta por Altman
    assert any("Financiera" in w for w in r.warnings)


def test_cyclical_sector_warning():
    d = P.get("AAPL").d; d["sector"] = "Energy"
    r = score_company(Snapshot(d), CFG, "swing", SPY)
    assert any("cíclico" in w for w in r.warnings)


# ---------- forward ----------
def _fake_prices(tickers, start):
    idx = pd.bdate_range("2026-10-02", "2026-12-01")
    top = {f"SYN{i:02d}" for i in range(1, 6)}
    cols = {}
    for t in tickers:
        rate = 0.002 if t in FAVORED else (0.0005 if t == "SPY" else 0.0)
        cols[t] = 100 * (1 + rate) ** np.arange(len(idx))
    return pd.DataFrame(cols, index=idx)


FAVORED = set()


def test_forward_report_top_beats_rest(tmp_path):
    snaps = synthetic_universe(30, seed=2)
    res = score_universe(snaps, CFG, "swing", SPY)
    st = Store(str(tmp_path / "f.db")); rid = st.save_run(res, "swing", "h", "t1")
    FAVORED.clear(); FAVORED.update(r.ticker for r in res[:10])         # el top-10 sube más (por construcción)
    rep = forward_report(st, rid, _fake_prices, top=10)
    h = rep["horizons"].set_index("semanas")
    assert h.loc[4, "estado"] == "listo" and h.loc[4, "top_prom"] > h.loc[4, "resto_prom"]
    assert h.loc[4, "top_vs_spy"] > 0 and h.loc[4, "ic_spearman"] > 0.3 and h.loc[4, "pct_top_gana_spy"] == 1.0
    assert h.loc[12, "estado"].startswith("pendiente")                  # aún no pasan 12 semanas
    assert rep["entry_date"] > dt.date.fromisoformat(rep["info"]["as_of"])   # entrada DESPUÉS de la señal
    assert "FORWARD de corrida" in format_forward(rep)


def test_forward_no_future_prices(tmp_path):
    snaps = synthetic_universe(10, seed=2)
    st = Store(str(tmp_path / "f.db")); rid = st.save_run(score_universe(snaps, CFG, "swing", SPY), "swing")
    early = lambda t, s: pd.DataFrame({x: [100.0, 101.0] for x in t}, index=pd.to_datetime(["2026-10-05", "2026-10-09"]))
    rep = forward_report(st, rid, early)
    assert rep["status"] != "ok" and "Aún no" in format_forward(rep)


# ---------- backtest de precio ----------
def test_price_backtest_finds_embedded_momentum():
    r = run_price_backtest(synthetic_universe(60, seed=5, hist_days=520), CFG)
    s = r["resumen"]
    assert s["periodos"] >= 10 and s["ic_mom"]["media"] > 0 and s["top_vs_universo"]["media"] > -0.01
    assert "Backtest de PRECIO" in format_backtest(r)


def test_price_backtest_insufficient_data_message():
    r = run_price_backtest(synthetic_universe(5, seed=1, hist_days=260), CFG)
    assert r["resumen"]["periodos"] == 0 and "Sin datos suficientes" in format_backtest(r)


def test_trend_signals_use_only_given_prefix():
    s = synthetic_universe(1, seed=9, hist_days=400)[0].closes()
    a = trend_signals(s.iloc[:300], CFG)
    b = trend_signals(pd.concat([s.iloc[:300]]), CFG)
    assert a == b and trend_signals(s.iloc[:200], CFG) is None


# ---------- plan ----------
def test_trade_plan_risk_math():
    s = P.get("AAPL"); r = score_company(s, CFG, "swing", SPY)
    p = trade_plan(s, r, CFG, capital=20000, risk_pct=0.01, fx=18.5, max_position_pct=1.0)
    assert 0.03 <= p["stop_pct"] <= 0.12 and p["stop"] < p["precio"] < p["objetivo"]
    assert p["perdida_max"] == pytest.approx(200, rel=1e-6)          # arriesga exactamente 1% del capital
    p2 = trade_plan(s, r, CFG, capital=20000, risk_pct=0.5, fx=18.5, max_position_pct=0.25)
    assert p2["valor_posicion"] <= 20000 * 0.25 + 1e-6 and p2["limitado_por_tamano_max"]
    assert "PLAN SWING" in format_plan(p, "MXN")


# ---------- diario ----------
def test_journal_flow(tmp_path):
    st = Store(str(tmp_path / "j.db")); j = Journal(st.con)
    a = j.open("AAPL", 100, 95, 110, 2, "tesis", 70, "VIGILAR")
    b = j.open("NKE", 50, 47, 56, 3)
    j.close(a, 110); j.close(b, 47)
    df = j.frame().set_index("id")
    assert df.loc[a, "R"] == pytest.approx(2.0) and df.loc[b, "R"] == pytest.approx(-1.0)
    s = j.stats()
    assert s["cerradas"] == 2 and s["pct_acierto"] == 0.5 and s["R_promedio"] == pytest.approx(0.5)
    with pytest.raises(ValueError): j.close(a, 120)
    with pytest.raises(ValueError): j.open("X", 100, 105, 110, 1)
    open_id = j.open("MSFT", 100, 95, 110, 1)
    assert j.frame({"MSFT": 105}).set_index("id").loc[open_id, "R"] == pytest.approx(1.0)


# ---------- flujo semanal ----------
def test_weekly_flow_with_rank_changes(tmp_path):
    snaps = {s.ticker: s for s in synthetic_universe(15, seed=4)}
    fetch = lambda t: SPY if t == "SPY" else snaps.get(t)
    st = Store(str(tmp_path / "w.db")); lines = []
    run_weekly(list(snaps) + ["NOEXISTE"], fetch, st, CFG, label="2026-W41", out=lines.append)
    r2 = run_weekly(list(snaps), fetch, st, CFG, label="2026-W42", out=lines.append)
    txt = "\n".join(lines)
    assert "Fallidas: NOEXISTE" in txt and "Δpuesto" in txt
    assert len(st.runs()) == 4 and set(st.runs().label) == {"2026-W41", "2026-W42"}
    assert auto_label(dt.date(2026, 10, 12)) == "2026-W42"


def test_weekly_survives_fetch_errors(tmp_path):
    snaps = {s.ticker: s for s in synthetic_universe(6, seed=4)}
    def fetch(t):
        if t == "SYN02": raise RuntimeError("429 too many requests")
        return SPY if t == "SPY" else snaps.get(t)
    st = Store(str(tmp_path / "w.db")); lines = []
    out = run_weekly(list(snaps), fetch, st, CFG, out=lines.append)
    assert [t for t, _ in out["failed"]] == ["SYN02"] and len(out["results"]["swing"]) == 5


def test_compare_table_lists_all_tickers():
    res = [score_company(P.get(t), CFG, "swing", SPY) for t in ("AAPL", "NKE")]
    t = compare_table(res)
    assert "AAPL" in t and "NKE" in t and "Piotroski" in t


# ---------- exclusión de "DATOS INCOMPLETOS" del ranking ----------
def test_incomplete_excluded_from_top_and_store(tmp_path):
    from stockscore.ranking import top_n, to_frame
    res = score_universe(synthetic_universe(12, seed=8), CFG, "investor", SPY)
    res[0].signal = "DATOS INCOMPLETOS"; res[0].total = 99.0          # parcial pero con puntaje altísimo
    res = sorted(res, key=lambda r: -r.total)
    assert res[0].ticker not in set(top_n(res, 12)["ticker"])
    assert res[0].ticker in set(top_n(res, 12, only_eligible=False)["ticker"])
    st = Store(str(tmp_path / "e.db")); rid = st.save_run(res, "investor")
    el, allr = st.ranking(rid), st.ranking(rid, only_eligible=False)
    assert len(el) == len(allr) - 1 and list(el["rank"]) == list(range(1, len(el) + 1)) and allr.loc[0, "signal"] == "DATOS INCOMPLETOS"


def test_weekly_reports_excluded(tmp_path, monkeypatch):
    snaps = {s.ticker: s for s in synthetic_universe(8, seed=4)}
    d = snaps["SYN03"].d; d["industry"] = "Banks - Regional"
    for k in ("ttm",): pass
    snaps["SYN03"] = Snapshot(d)
    fetch = lambda t: SPY if t == "SPY" else snaps.get(t)
    lines = []
    run_weekly(list(snaps), fetch, Store(str(tmp_path / "w.db")), CFG, out=lines.append)
    txt = "\n".join(lines)
    if "SYN03" in txt and "Excluidas" in txt:
        assert "DATOS INCOMPLETOS: SYN03" in txt or "SYN03" in txt


def test_risk_window_ignores_old_prices():
    s = synthetic_universe(1, seed=11, hist_days=1000)[0]
    m_full, _ = compute_all(s, CFG, SPY)
    d = s.d; d["price_history"] = d["price_history"][-504:]
    m_win, _ = compute_all(Snapshot(d), CFG, SPY)
    assert m_full["vol_ann"] == pytest.approx(m_win["vol_ann"]) and m_full["max_drawdown"] == pytest.approx(m_win["max_drawdown"])
    assert m_full["hist_days"] == 1000                      # el historial completo sigue disponible para backtest


def test_five_year_history_still_scores_and_backtests_with_more_periods():
    snaps = synthetic_universe(40, seed=3, hist_days=1250)
    assert all(0 <= r.total <= 100 for r in score_universe(snaps, CFG, "swing", SPY))
    assert run_price_backtest(snaps, CFG)["resumen"]["periodos"] >= 40


def test_backtest_text_is_dynamic():
    r = run_price_backtest(synthetic_universe(50, seed=5, hist_days=1250), CFG)
    t = format_backtest(r)
    assert "47 rebalanceos" in t or f"{r['resumen']['periodos']} rebalanceos" in t
    assert "~1 año" not in t and "se solapan" not in t


def test_pending_tickers_resume(tmp_path):
    import json
    from stockscore.cli import pending_tickers, read_universe
    today = dt.date(2026, 10, 15)
    (tmp_path / "AAA.json").write_text(json.dumps({"as_of": "2026-10-15", "fiscal": [], "pad": "x" * 3000}))   # al día
    (tmp_path / "BBB.json").write_text(json.dumps({"as_of": "2026-10-10", "fiscal": [], "pad": "x" * 3000}))   # viejo
    assert pending_tickers(["AAA", "BBB", "CCC"], tmp_path, today) == ["BBB", "CCC"]
    u = tmp_path / "u.txt"; u.write_text("# c\naapl\n\nMSFT # x\n")
    assert read_universe(u) == ["AAPL", "MSFT"]


def test_universe_150_file_valid():
    from stockscore.cli import read_universe
    root = pathlib.Path(__file__).resolve().parent.parent / "config"
    u150, u50 = read_universe(root / "universe_150.txt"), read_universe(root / "universe_50.txt")
    assert len(u150) == len(set(u150)) >= 140 and set(u50) <= set(u150)


def test_cyclical_normalization_and_signal():
    import copy, json, pathlib
    from stockscore.models import Snapshot
    from stockscore.metrics.valuation import normalized_ttm
    from stockscore.scoring import signal_of
    import yaml
    cfg = yaml.safe_load(open(pathlib.Path(__file__).parent.parent / "config" / "default.yaml"))
    d = json.load(open(pathlib.Path(__file__).parent / "fixtures" / "AAPL.json"))
    d = copy.deepcopy(d); d["sector"] = "Energy"
    d["ttm"]["fcf"] = 1000.0                      # pico del ciclo
    for f in d["fiscal"][:3]:
        f["cfo"], f["capex"] = 100.0, 50.0         # años normales: FCF 50
    t, norm = normalized_ttm(Snapshot(d), cfg)
    assert norm and t["fcf"] < 400
    assert signal_of(80, {"trend": {"score": 90}}, [], 1.0, cfg, cyclical=True) == "VIGILAR"
    assert signal_of(80, {"trend": {"score": 90}}, [], 1.0, cfg, cyclical=False) == "CANDIDATA"


def test_diversify_caps_sector():
    import pandas as pd
    from stockscore.ranking import diversify
    df = pd.DataFrame({"rank": range(1, 9), "ticker": list("ABCDEFGH"),
                       "sector": ["Energy"] * 5 + ["Tech", "Health", "Tech"], "total": [90, 85, 80, 75, 70, 65, 60, 55]})
    d = diversify(df, n=5, max_per_sector=3)
    assert list(d.ticker) == ["A", "B", "C", "F", "G"]
    assert list(d["rank"]) == [1, 2, 3, 4, 5] and list(d.rank_puro)[3] == 6


def test_semiconductor_cyclical_and_new_warnings():
    import copy, json, pathlib, yaml
    from stockscore.models import Snapshot
    from stockscore.scoring import is_cyclical, flags
    cfg = yaml.safe_load(open(pathlib.Path(__file__).parent.parent / "config" / "default.yaml"))
    d = copy.deepcopy(json.load(open(pathlib.Path(__file__).parent / "fixtures" / "AAPL.json")))
    d["sector"], d["industry"] = "Technology", "Semiconductors"
    s = Snapshot(d)
    assert is_cyclical(s, cfg)
    d["industry"] = "Consumer Electronics"
    assert not is_cyclical(Snapshot(d), cfg)
    _, w = flags({"mom": 4.2, "op_margin": 0.8}, cfg, s)
    assert any("parabólico" in x for x in w) and any("Margen operativo" in x for x in w)
    assert any("Industria cíclica" in x for x in w)
