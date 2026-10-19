"""Prueba el proveedor de Yahoo SIN red, con un módulo `yfinance` falso que imita el formato real (filas = conceptos, columnas = fechas)."""
import sys, types
import numpy as np, pandas as pd, pytest
from stockscore.config import load_config
from stockscore.scoring import score_company

CFG = load_config()


def _frames():
    cols = [pd.Timestamp(f"{y}-09-30") for y in (2025, 2024, 2023, 2022)]
    def df(rows): return pd.DataFrame({c: [v * (1 - 0.05 * i) * 1e6 for v in vals] for i, (c, vals) in enumerate(zip(cols, [list(rows.values())] * 4))}, index=list(rows))
    inc = df({"Total Revenue": 1000, "Gross Profit": 450, "Operating Income": 250, "Net Income": 200})
    bal = df({"Total Assets": 2000, "Current Assets": 800, "Current Liabilities": 500, "Total Liabilities Net Minority Interest": 1100,
              "Stockholders Equity": 900, "Retained Earnings": 300, "Long Term Debt": 400, "Total Debt": 450,
              "Cash Cash Equivalents And Short Term Investments": 300, "Ordinary Shares Number": 100})
    cf = df({"Operating Cash Flow": 260, "Capital Expenditure": -60})
    return inc, bal, cf


class FakeTicker:
    def __init__(self, sym):
        self.sym = sym
        self.info = {"quoteType": "ETF" if sym == "ETFX" else "EQUITY", "shortName": sym, "sector": "Technology", "industry": "Software",
                     "currency": "USD", "marketCap": 50e9, "enterpriseValue": 51e9, "sharesOutstanding": 500e6, "trailingPE": 20, "forwardPE": 18,
                     "forwardEps": 3.0, "beta": 1.1, "targetMeanPrice": 120.0, "recommendationKey": "strong_buy", "numberOfAnalystOpinions": 30,
                     "totalRevenue": 1.1e9, "grossProfits": 5e8, "operatingMargins": 0.25, "netIncomeToCommon": 2.2e8, "ebitda": 3e8,
                     "freeCashflow": 2e8, "trailingEps": 2.5, "dividendYield": 0.01, "fiftyDayAverage": 100.0, "twoHundredDayAverage": 95.0}
        self.calendar = {"Earnings Date": [pd.Timestamp("2026-11-05").date()]}
        self.growth_estimates = pd.DataFrame({"stockTrend": [0.12, 0.10]}, index=["+1y", "LTG"])
        self.news = [{"content": {"title": "Nuevo formato", "pubDate": "2026-10-09T12:00:00Z", "provider": {"displayName": "Reuters"},
                                  "canonicalUrl": {"url": "http://a"}}}, {"title": "Formato viejo", "providerPublishTime": 1760000000, "publisher": "AP", "link": "http://b"}]
        self.quarterly_cashflow = pd.DataFrame({pd.Timestamp("2026-06-30"): [70e6, -15e6], pd.Timestamp("2026-03-31"): [65e6, -15e6],
                                                pd.Timestamp("2025-12-31"): [60e6, -15e6], pd.Timestamp("2025-09-30"): [60e6, -15e6]},
                                               index=["Operating Cash Flow", "Capital Expenditure"])

    def history(self, period="2y", auto_adjust=False):
        idx = pd.bdate_range(end="2026-10-09", periods=500)
        r = np.random.default_rng(1).normal(0.0006, 0.012, 500)
        return pd.DataFrame({"Close": 100 * np.exp(np.cumsum(r))}, index=idx)

    @property
    def financials(self):
        if self.info["quoteType"] == "ETF": raise RuntimeError("ETF: no se debe pedir financials")
        return _frames()[0]

    @property
    def balance_sheet(self): return _frames()[1]

    @property
    def cashflow(self): return _frames()[2]


@pytest.fixture
def fake_yf(monkeypatch):
    m = types.ModuleType("yfinance"); m.Ticker = FakeTicker
    def download(tk, start=None, **kw):
        idx = pd.bdate_range(start=start, periods=30)
        return pd.DataFrame({("Close", t): 100 + np.arange(30.0) for t in tk}, index=idx)
    m.download = download
    monkeypatch.setitem(sys.modules, "yfinance", m)
    return m


def test_provider_builds_scorable_snapshot(tmp_path, fake_yf):
    from stockscore.providers.yfinance_provider import YFinanceProvider
    s = YFinanceProvider(str(tmp_path)).get("FAKE")
    assert len(s.fiscal) == 4 and s.fy(0)["total_assets"] == 2000 and s.fy(0)["capex"] == 60 and s.fy(0)["shares_m"] == 100
    assert s.industry == "Software" and s.market["eps_growth_3y"] == pytest.approx(0.10)     # LTG de analistas capturado
    assert s.ttm["fcf"] == pytest.approx(195) and s.events[0]["date"] == "2026-11-05"
    assert (tmp_path / "FAKE.json").exists()
    r = score_company(s, CFG, "swing")
    assert 0 <= r.total <= 100 and r.coverage > 0.8


def test_provider_etf_skips_fundamentals_quietly(tmp_path, fake_yf):
    from stockscore.providers.yfinance_provider import YFinanceProvider
    s = YFinanceProvider(str(tmp_path)).get("ETFX")
    assert s.fiscal == [] and len(s.closes()) == 500


def test_provider_retry_recovers(tmp_path, fake_yf, monkeypatch):
    from stockscore.providers import yfinance_provider as yp
    calls = {"n": 0}
    orig = yp.YFinanceProvider.get
    def flaky(self, t, save=True):
        calls["n"] += 1
        if calls["n"] < 3: raise RuntimeError("429")
        return orig(self, t, save)
    monkeypatch.setattr(yp.YFinanceProvider, "get", flaky)
    monkeypatch.setattr("time.sleep", lambda s: None)
    assert yp.YFinanceProvider(str(tmp_path)).get_with_retry("FAKE", retries=2).ticker == "FAKE" and calls["n"] == 3


def test_news_both_yfinance_formats(fake_yf):
    from stockscore.providers.yfinance_provider import yahoo_news
    n = yahoo_news("FAKE")
    assert n[0][1] == "Nuevo formato" and n[0][2] == "Reuters" and n[1][1] == "Formato viejo" and n[1][3] == "http://b"


def test_yahoo_prices_shape(fake_yf):
    from stockscore.providers.yfinance_provider import yahoo_prices
    df = yahoo_prices(["A", "B"], "2026-10-01")
    assert list(df.columns) == ["A", "B"] and len(df) == 30


def test_cli_fetch_skip_fresh(tmp_path, fake_yf, capsys):
    from stockscore import cli
    d = str(tmp_path)
    cli.main(["--db", str(tmp_path / "x.db"), "--dir", d, "fetch", "FAKE", "--no-bench", "--pause", "0"])
    assert "ok FAKE" in capsys.readouterr().out
    # sin datos de hoy suficientes (fake trae 500 precios, as_of=hoy) -> se salta
    cli.main(["--db", str(tmp_path / "x.db"), "--dir", d, "fetch", "FAKE", "--no-bench", "--pause", "0", "--skip-fresh"])
    assert "salto FAKE" in capsys.readouterr().out
