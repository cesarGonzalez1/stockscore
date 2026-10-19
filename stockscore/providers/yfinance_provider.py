"""Descarga datos vivos de Yahoo Finance y los convierte al formato Snapshot (y los guarda como JSON).
NOTA: probado solo con datos simulados (el entorno de desarrollo no tiene acceso a Yahoo). Ejecútalo en tu Mac:
  python -m stockscore.cli fetch AAPL NKE SPY
Si Yahoo cambia nombres de filas, ajusta ROWS abajo (una sola tabla)."""
import datetime as dt, json
from pathlib import Path
from ..models import Snapshot

ROWS = {  # clave nuestra -> posibles nombres de fila en yfinance (se prueba en orden)
    "revenue": ["Total Revenue", "Operating Revenue"],
    "gross_profit": ["Gross Profit"],
    "operating_income": ["Operating Income", "EBIT"],
    "net_income": ["Net Income", "Net Income Common Stockholders"],
    "da": ["Reconciled Depreciation", "Depreciation And Amortization"],
    "cfo": ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"],
    "capex": ["Capital Expenditure"],
    "total_assets": ["Total Assets"],
    "current_assets": ["Current Assets"],
    "current_liabilities": ["Current Liabilities"],
    "total_liabilities": ["Total Liabilities Net Minority Interest"],
    "equity": ["Stockholders Equity", "Common Stock Equity"],
    "retained_earnings": ["Retained Earnings"],
    "long_term_debt": ["Long Term Debt", "Long Term Debt And Capital Lease Obligation"],
    "total_debt": ["Total Debt"],
    "cash_st": ["Cash Cash Equivalents And Short Term Investments", "Cash And Cash Equivalents"],
    "shares_m": ["Ordinary Shares Number", "Share Issued"],
}


def pick(df, names, col):
    """Primer valor no-nulo de df.loc[nombre, col]; None si no existe."""
    for n in names:
        if n in df.index:
            v = df.loc[n, col]
            if v == v and v is not None:  # no NaN
                return float(v)
    return None


def build_fiscal(inc, bal, cf):
    out = []
    for col in inc.columns:
        row = {"year": col.year}
        for key, names in ROWS.items():
            for df in (inc, bal, cf):
                if col in df.columns:
                    v = pick(df, names, col)
                    if v is not None:
                        row[key] = v
                        break
        for k in ("revenue", "total_assets", "net_income"):
            if k not in row:
                row = None
                break
        if row is None:
            continue
        row["capex"] = abs(row.get("capex", 0.0))
        for k in ROWS:
            row.setdefault(k, 0.0)
        for k in row:
            if k not in ("year", "shares_m"):
                row[k] = row[k] / 1e6
            elif k == "shares_m":
                row[k] = row[k] / 1e6
        out.append(row)
    return out


def rsi14(closes):
    from ..metrics.trend import rsi_wilder
    return rsi_wilder(closes)


class YFinanceProvider:
    def __init__(self, cache_dir="data/snapshots", years_history="2y"):
        self.cache = Path(cache_dir)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.period = years_history

    def fetch_dict(self, ticker):
        import yfinance as yf
        t = yf.Ticker(ticker)
        info = t.info or {}
        hist = t.history(period=self.period, auto_adjust=False)["Close"].dropna()
        qtype = (info.get("quoteType") or "").upper()
        fiscal = [] if qtype in ("ETF", "INDEX", "MUTUALFUND") else build_fiscal(t.financials, t.balance_sheet, t.cashflow)
        price = float(hist.iloc[-1])
        ttm_fcf = ttm_cfo = None
        try:
            q = t.quarterly_cashflow
            cfo4 = q.loc["Operating Cash Flow"].iloc[:4].sum()
            cap4 = q.loc["Capital Expenditure"].iloc[:4].sum()
            ttm_cfo, ttm_fcf = cfo4 / 1e6, (cfo4 + cap4) / 1e6
        except Exception:
            pass
        ret52 = float(hist.iloc[-1] / hist.iloc[-253] - 1) if len(hist) >= 253 else None
        events = []
        try:
            if qtype in ("ETF", "INDEX", "MUTUALFUND"):
                raise RuntimeError("sin calendario de resultados")
            cal = t.calendar
            ed = cal.get("Earnings Date") if isinstance(cal, dict) else None
            if ed:
                events.append({"date": str(ed[0]), "type": "earnings", "confirmed": False, "note": "Yahoo calendar"})
        except Exception:
            pass
        eps_g = None
        try:  # mejor esfuerzo: crecimiento esperado a largo plazo de analistas (nombres cambian según versión de yfinance)
            if qtype in ("ETF", "INDEX", "MUTUALFUND"):
                raise RuntimeError("ETF")
            ge = t.growth_estimates
            for row in ("+5y", "LTG"):
                for col in ("stock", "stockTrend"):
                    if row in ge.index and col in ge.columns and ge.loc[row, col] == ge.loc[row, col]:
                        eps_g = float(ge.loc[row, col]); break
                if eps_g is not None: break
        except Exception:
            pass
        mc = info.get("marketCap")
        g = lambda k, s=1.0: (info[k] / s) if info.get(k) is not None else None
        return {
            "ticker": ticker.upper(), "name": info.get("shortName", ticker), "sector": info.get("sector", "?"), "industry": info.get("industry", ""),
            "currency": info.get("currency", "USD"), "as_of": dt.date.today().isoformat(), "price": price,
            "source": "yfinance", "fiscal": fiscal,
            "ttm": {"revenue": g("totalRevenue", 1e6), "gross_profit": g("grossProfits", 1e6),
                    "operating_income": (info.get("operatingMargins") or 0) * (info.get("totalRevenue") or 0) / 1e6 or None,
                    "net_income": g("netIncomeToCommon", 1e6), "ebitda": g("ebitda", 1e6), "cfo": ttm_cfo, "fcf": ttm_fcf or g("freeCashflow", 1e6),
                    "eps": info.get("trailingEps")},
            "market": {"market_cap_m": mc / 1e6 if mc else None, "enterprise_value_m": g("enterpriseValue", 1e6),
                       "shares_out_m": g("sharesOutstanding", 1e6), "pe": info.get("trailingPE"), "forward_pe": info.get("forwardPE"),
                       "forward_eps": info.get("forwardEps"), "beta": info.get("beta"), "ret_52w": ret52,
                       "sma50": info.get("fiftyDayAverage"), "sma200": info.get("twoHundredDayAverage"),
                       "rsi14": rsi14(hist), "analyst_target": info.get("targetMeanPrice"),
                       "analyst_consensus": (info.get("recommendationKey") or "").replace("_", " "),
                       "analyst_count": info.get("numberOfAnalystOpinions"),
                       "eps_growth_3y": eps_g, "dividend_yield": info.get("dividendYield")},
            "price_history": [[d.date().isoformat(), float(v)] for d, v in hist.items()],
            "events": events,
        }

    def get(self, ticker, save=True):
        d = self.fetch_dict(ticker)
        if save:
            (self.cache / f"{ticker.upper()}.json").write_text(json.dumps(d, ensure_ascii=False, indent=1))
        return Snapshot(d)


    def get_with_retry(self, ticker, retries=2, pause=2.0):
        import time
        last = None
        for i in range(retries + 1):
            try:
                return self.get(ticker)
            except Exception as e:  # Yahoo limita por velocidad: esperar y reintentar
                last = e
                time.sleep(pause * (i + 1))
        raise last


def yahoo_prices(tickers, start):
    """Cierres diarios desde `start` (DataFrame fecha x ticker). Para forward test."""
    import yfinance as yf
    import pandas as pd
    tk = list(dict.fromkeys(tickers))
    df = yf.download(tk, start=str(start), progress=False, auto_adjust=False, group_by="column", threads=False)
    close = df["Close"]
    if isinstance(close, pd.Series):
        close = close.to_frame(tk[0])
    close.index = pd.to_datetime(close.index).tz_localize(None)
    return close.dropna(how="all")


def yahoo_news(ticker, limit=8):
    """Titulares recientes [(fecha, titular, fuente, url)]. Soporta ambos formatos de yfinance."""
    import yfinance as yf
    out = []
    for it in (yf.Ticker(ticker).news or [])[:limit]:
        c = it.get("content") or {}
        title = c.get("title") or it.get("title")
        when = c.get("pubDate") or it.get("providerPublishTime")
        if isinstance(when, (int, float)):
            when = dt.datetime.fromtimestamp(when).isoformat(timespec="minutes")
        src = (c.get("provider") or {}).get("displayName") or it.get("publisher", "")
        url = (c.get("canonicalUrl") or {}).get("url") or it.get("link", "")
        if title:
            out.append((str(when or "")[:16], title, src, url))
    return out
