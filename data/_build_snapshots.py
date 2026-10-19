"""Construye data/snapshots/{AAPL,NKE,SPY}.json con los datos reales recopilados el 2026-10-09
(stockanalysis.com / S&P Global; cifras en millones USD). Ejecuta: python data/_build_snapshots.py <volcado_precios.txt>
"""
import json, re, sys, pathlib, datetime as dt

OUT = pathlib.Path(__file__).parent / "snapshots"
KEYS = ["year","revenue","gross_profit","operating_income","net_income","cfo","capex","total_assets",
        "current_assets","current_liabilities","total_liabilities","equity","retained_earnings",
        "long_term_debt","total_debt","cash_st","shares_m","da"]
AAPL_FY = [
 [2025,416161,195201,133050,112010,111482,12715,359241,147957,165631,285508,73733,-14264,78328,112377,54697,14773,11698],
 [2024,391035,180683,123216,93736,118254,9447,364980,152987,176392,308030,56950,-19154,85750,119059,65171,15117,11445],
 [2023,383285,169148,114301,96995,110543,10959,352583,143566,145308,290437,62146,-214,95281,123930,61555,15550,11519],
 [2022,394328,170782,119437,99803,122151,10708,352755,135405,153982,302083,50672,-3068,98959,132480,48304,15943,11104],
 [2021,365817,152836,108949,94680,104038,11085,351002,134836,125481,287912,63090,5562,109106,136522,62639,16427,11284]]
NKE_FY = [
 [2026,46398,20065,4182,3108,2868,684,38410,24603,12547,23545,14865,-155,5952,11043,9027,1483,747],
 [2025,46309,19790,3702,3219,3698,430,36579,23362,10566,23366,13213,-727,7964,11016,9151,1476,775],
 [2024,51362,22951,6754,5700,7429,812,38110,25382,10593,23680,14430,965,7934,11983,11582,1503,796],
 [2023,51217,22292,5915,5070,5841,969,37531,25202,9256,23527,14004,1358,8927,12144,10675,1532,703],
 [2022,46710,21479,6675,6046,5188,758,40321,28213,10730,25040,15281,3476,8920,12627,12997,1571,840]]

def parse_prices(txt, msg_ids):
    """Extrae filas 'Mon D, YYYY | o | h | l | close' de las secciones '===== N' indicadas."""
    out = {}
    for sec in re.split(r"^===== ", txt, flags=re.M):
        head = sec.split("\n", 1)[0].strip()
        if head not in msg_ids: continue
        for m in re.finditer(r"^\| (\w{3} \d{1,2}, \d{4}) \| [\d.,]+ \| [\d.,]+ \| [\d.,]+ \| ([\d.,]+) \|", sec, flags=re.M):
            d = dt.datetime.strptime(m.group(1), "%b %d, %Y").date().isoformat()
            out[d] = float(m.group(2).replace(",", ""))
    return sorted(out.items())

def fy(rows): return [dict(zip(KEYS, r)) for r in rows]

def main(path):
    txt = open(path).read()
    aapl_px = parse_prices(txt, {"679", "697"})
    nke_px = parse_prices(txt, {"700"})
    spy_px = parse_prices(txt, {"705"})
    base = {"currency": "USD", "as_of": "2026-10-09",
            "source": "stockanalysis.com (S&P Global MI) leído 2026-10-09; millones USD; precios diarios ventana corta (~50 días)"}
    aapl = {**base, "ticker": "AAPL", "name": "Apple Inc.", "sector": "Technology", "price": 336.64,
        "fiscal": fy(AAPL_FY),
        "ttm": {"revenue":466823,"gross_profit":227123,"operating_income":154859,"net_income":128930,
                "ebitda":167960,"cfo":146720,"fcf":136680,"eps":8.72},
        "market": {"market_cap_m":4910000,"enterprise_value_m":4850000,"shares_out_m":14590,"pe":39.05,
                   "forward_pe":36.96,"forward_eps":round(336.64/36.96,3),"beta":1.07,"ret_52w":0.3045,
                   "sma50":322.39,"sma200":290.74,"rsi14":56.17,"analyst_target":328.09,
                   "analyst_consensus":"Buy","analyst_count":44,"eps_growth_3y":0.1321,
                   "revenue_growth_3y":0.1114,"dividend_yield":0.0032},
        "price_history": aapl_px,
        "events": [{"date":"2026-11-02","type":"earnings","confirmed":True,"note":"Resultados FQ4, después del cierre"}],
        "reported_scores": {"piotroski": 8, "altman": 10.93}}
    nke = {**base, "ticker": "NKE", "name": "NIKE, Inc.", "sector": "Consumer Discretionary", "price": 34.71,
        "fiscal": fy(NKE_FY),
        "ttm": {"revenue":45891,"gross_profit":19920,"operating_income":4143,"net_income":3093,
                "ebitda":4890,"cfo":2780,"fcf":2110,"eps":2.09},
        "market": {"market_cap_m":51560,"enterprise_value_m":54310,"shares_out_m":1490,"pe":16.64,
                   "forward_pe":25.71,"forward_eps":round(34.71/25.71,3),"beta":1.10,"ret_52w":-0.4976,
                   "sma50":38.15,"sma200":48.01,"rsi14":37.75,"analyst_target":38.04,
                   "analyst_consensus":"Hold","analyst_count":42,"eps_growth_3y":0.1192,
                   "revenue_growth_3y":-0.0079,"dividend_yield":0.0473},
        "price_history": nke_px,
        "events": [],
        "notes": "Última earnings: 2026-10-01 (precio -3.6% al día siguiente). Próxima fecha no confirmada.",
        "reported_scores": {"piotroski": 5, "altman": 4.14}}
    spy = {**base, "ticker": "SPY", "name": "SPDR S&P 500 ETF", "sector": "Benchmark", "price": spy_px[-1][1],
        "fiscal": [], "ttm": {}, "market": {"ret_52w": 0.1691, "beta": 1.0}, "price_history": spy_px, "events": []}
    for s in (aapl, nke, spy):
        (OUT / f"{s['ticker']}.json").write_text(json.dumps(s, ensure_ascii=False, indent=1))
        print(s["ticker"], len(s["price_history"]), "precios", s["price_history"][0][0], "->", s["price_history"][-1][0])

if __name__ == "__main__":
    main(sys.argv[1])
