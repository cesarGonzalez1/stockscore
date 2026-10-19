import argparse, sys, time
from pathlib import Path
import pandas as pd
from .config import load_config, ROOT
from .providers import get_provider
from .scoring import score_universe, score_company
from .storage import Store
from .ranking import to_frame, top_n, diversify
from .report import company_report, compare_table
from .synthetic import synthetic_universe
from . import validate as V

pd.set_option("display.width", 220); pd.set_option("display.max_columns", 40)


def read_universe(path):
    return [l.split("#")[0].strip().upper() for l in Path(path).read_text().splitlines() if l.split("#")[0].strip()]


def load_snaps(a):
    if a.source == "synthetic":
        return synthetic_universe(a.n_synth, seed=a.seed, hist_days=getattr(a, "hist_days", 260)), None
    prov = get_provider(a.source, **({"directory": a.dir} if a.source == "snapshot" else {"cache_dir": a.dir}))
    tickers = [t.upper() for t in a.tickers] if a.tickers else (read_universe(a.universe) if a.universe else getattr(prov, "available", lambda: [])())
    bench = prov.get("SPY") if a.source == "snapshot" else prov.get(a.bench)
    snaps = []
    for t in tickers:
        if t == "SPY": continue
        try:
            s = prov.get(t)
        except Exception as e:
            print(f"! {t}: {e}", file=sys.stderr); continue
        if s is None: print(f"! {t}: sin snapshot (corre 'fetch {t}')", file=sys.stderr); continue
        snaps.append(s)
    return snaps, bench


def pending_tickers(tickers, directory, today=None):
    """Tickers cuyo snapshot NO tiene ya fecha de hoy (para reanudar un fetch largo)."""
    import json, datetime as dt
    today = (today or dt.date.today()).isoformat()
    out = []
    for t in tickers:
        f = Path(directory) / f"{t}.json"
        try:
            if json.loads(f.read_text()).get("as_of") == today and json.loads(f.read_text()).get("fiscal") is not None and f.stat().st_size > 2000:
                continue
        except Exception:
            pass
        out.append(t)
    return out


def cmd_fetch(a):
    prov = get_provider("yfinance", cache_dir=a.dir, years_history=a.period)
    names = [t.upper() for t in (a.tickers or [])] + (read_universe(a.universe) if a.universe else [])
    if not names: sys.exit("Indica tickers o --universe archivo")
    if a.resume:
        todo = pending_tickers(names, a.dir)
        for t in names:
            if t not in todo:
                print(f"salto {t}: ya descargado hoy")
        print(f"Reanudando: {len(names) - len(todo)} ya estaban al día, faltan {len(todo)}")
        names = todo
    tickers = names + ([] if a.no_bench else [a.bench])
    for t in dict.fromkeys(tickers):
        try:
            s = prov.get_with_retry(t); print(f"ok {t}: {len(s.fiscal)} años fiscales, {len(s.closes())} precios")
        except Exception as e:
            print(f"ERROR {t}: {str(e)[:120]}")
        time.sleep(a.pause)


def cmd_score(a):
    cfg = load_config(a.config)
    snaps, bench = load_snaps(a)
    store = Store(a.db)
    for p in (["swing", "investor"] if a.profile == "both" else [a.profile]):
        res = score_universe(snaps, cfg, p, bench)
        rid = store.save_run(res, p, cfg["_hash"], a.label)
        print(f"\n== Ranking perfil={p}  run #{rid}  n={len(res)} ==")
        print(top_n(res, a.top).drop(columns=["name", "percentile"]).round(1).to_string(index=False))


def cmd_top(a):
    st = Store(a.db)
    if not st.latest_run(): sys.exit("BD vacía: corre 'score' primero")
    if a.max_sector:
        df = st.ranking(run_id=a.run, sector=a.sector, only_eligible=not a.all)
        print(diversify(df, n=a.n, max_per_sector=a.max_sector).round(1).to_string(index=False))
    else:
        print(st.ranking(run_id=a.run, n=a.n, sector=a.sector, only_eligible=not a.all).round(1).to_string(index=False))


def _one(a, ticker=None):
    cfg = load_config(a.config)
    prov = get_provider("snapshot", directory=a.dir)
    t = (ticker or a.ticker).upper()
    s, bench = prov.get(t), prov.get("SPY")
    if s is None: sys.exit(f"sin snapshot de {t}: corre 'fetch {t}'")
    return cfg, s, score_company(s, cfg, a.profile, bench)


def cmd_show(a):
    cfg, s, r = _one(a); print(company_report(r, s, cfg))


def cmd_compare(a):
    cfg = load_config(a.config)
    prov = get_provider("snapshot", directory=a.dir); bench = prov.get("SPY")
    res = []
    for t in a.tickers:
        s = prov.get(t.upper())
        if s is None: sys.exit(f"sin snapshot de {t}")
        res.append(score_company(s, cfg, a.profile, bench))
    print(compare_table(res))


def cmd_history(a):
    print(Store(a.db).history(a.ticker).round(1).to_string(index=False))


def cmd_validate(a):
    cfg = load_config(a.config)
    snaps, bench = load_snaps(a)
    res = score_universe(snaps, cfg, a.profile, bench)
    bdf = V.benchmarks(snaps, cfg, bench)
    print(f"(perfil={a.profile}, n={len(res)})")
    print("\n-- Correlación Spearman: mi puntaje vs scores clásicos --"); print(V.correlations(res, bdf).round(3).to_string(index=False))
    print("\n-- Solape top-N con cada benchmark --"); print(V.topn_overlap(res, bdf, min(a.top, len(res))).round(2).to_string(index=False))
    print("\n-- Estabilidad ante perturbación de pesos --"); print(V.weight_stability(snaps, cfg, a.profile, top_n=min(a.top, len(res)), bench=bench))
    rc = V.reported_check(snaps, cfg)
    if len(rc): print("\n-- Piotroski/Altman calculados vs reportados --"); print(rc.to_string(index=False))


def cmd_export(a):
    from .export import to_excel
    cfg = load_config(a.config)
    snaps, bench = load_snaps(a)
    to_excel(score_universe(snaps, cfg, a.profile, bench), a.xlsx); print("guardado", a.xlsx)


def cmd_forward(a):
    from .forward import forward_report, format_forward
    from .providers.yfinance_provider import yahoo_prices
    st = Store(a.db)
    rid = a.run or st.latest_run(profile=a.profile, label=a.label)
    if not rid: sys.exit("No hay corridas guardadas (corre 'score' primero)")
    print(format_forward(forward_report(st, rid, yahoo_prices, top=a.top)))


def cmd_backtest(a):
    from .backtest import run_price_backtest, format_backtest
    cfg = load_config(a.config)
    snaps, _ = load_snaps(a)
    r = run_price_backtest(snaps, cfg, horizon=a.horizon, step=a.step, top=a.top)
    print(format_backtest(r))
    if a.csv: r["detalle"].to_csv(a.csv, index=False); print("detalle →", a.csv)


def cmd_plan(a):
    from .plan import trade_plan, format_plan
    cfg, s, r = _one(a)
    print(company_report(r, s, cfg).split("Métricas")[0].rstrip())
    print()
    print(format_plan(trade_plan(s, r, cfg, a.capital, a.risk, a.fx, a.max_position), a.currency))
    if r.vetoes: print("\nVETOS:", *r.vetoes, sep="\n  ✗ ")
    if r.warnings: print("\nALERTAS:", *r.warnings, sep="\n  ! ")


def cmd_journal(a):
    from .journal import Journal
    st = Store(a.db); j = Journal(st.con)
    if a.jcmd == "open":
        d = st.get(a.ticker) if st.latest_run() else None
        tid = j.open(a.ticker, a.entry, a.stop, a.target, a.shares, a.thesis, d["total"] if d else None, d["signal"] if d else None, paper=not a.real)
        print(f"operación #{tid} abierta ({'real' if a.real else 'papel'}). Puntaje al entrar: {d['total'] if d else 'sin corrida guardada'}")
    elif a.jcmd == "close":
        j.close(a.id, a.exit, note=a.note); print(f"operación #{a.id} cerrada")
    else:
        prices = {}
        prov = get_provider("snapshot", directory=a.dir)
        for t in pd.read_sql("SELECT DISTINCT ticker FROM trades WHERE status='open'", st.con).ticker:
            s = prov.get(t)
            if s: prices[t] = s.price
        if a.jcmd == "list":
            df = j.frame(prices)
            print(df[["id", "ticker", "opened", "status", "entry", "stop", "target", "last", "ret", "R", "score_at_entry", "paper"]].round(3).to_string(index=False) if len(df) else "Sin operaciones")
        else:
            for k, v in j.stats().items(): print(f"  {k}: {round(v, 3) if isinstance(v, float) else v}")


def cmd_news(a):
    from .providers.yfinance_provider import yahoo_news
    for when, title, src, url in yahoo_news(a.ticker.upper(), a.n):
        print(f"{when}  {title}  [{src}]\n    {url}")


def cmd_weekly(a):
    from .workflow import run_weekly
    from .providers.yfinance_provider import yahoo_prices
    cfg = load_config(a.config)
    prov = get_provider("yfinance", cache_dir=a.dir, years_history=a.period)

    tickers = read_universe(a.universe)
    total, n = len(tickers) + 1, [0]

    def fetch(t):
        n[0] += 1
        print(f"[{n[0]}/{total}] bajando {t}...", flush=True)
        s = prov.get_with_retry(t); time.sleep(a.pause); return s
    run_weekly(read_universe(a.universe), fetch, Store(a.db), cfg, price_fn=yahoo_prices, label=a.label or None, top=a.top)


def cmd_demo(a):
    """AAPL+NKE reales (fixtures) y 50 sintéticas; guarda corridas en la BD."""
    cfg = load_config(a.config)
    prov = get_provider("snapshot", directory=a.dir); bench = prov.get("SPY")
    real = [s for s in (prov.get("AAPL"), prov.get("NKE")) if s]
    if len(real) < 2: sys.exit("demo requiere AAPL y NKE en data/snapshots")
    store = Store(a.db)
    for p in ("swing", "investor"):
        r = score_universe(real, cfg, p, bench); store.save_run(r, p, cfg["_hash"], "reales")
        print(f"\n== REALES perfil={p} =="); print(to_frame(r).drop(columns=["name", "percentile"]).round(1).to_string(index=False))
    r = score_universe(real + synthetic_universe(48, seed=a.seed), cfg, "swing", bench); store.save_run(r, "swing", cfg["_hash"], "demo50")
    print("\n== TOP 10 de 50 (2 reales + 48 sintéticas SYN) perfil=swing =="); print(top_n(r, 10).drop(columns=["name", "percentile"]).round(1).to_string(index=False))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="stockscore")
    ap.add_argument("--config"); ap.add_argument("--db", default="out/stockscore.db")
    ap.add_argument("--dir", default=str(ROOT / "data" / "snapshots"))
    sub = ap.add_subparsers(dest="cmd", required=True)

    def src(p):
        p.add_argument("--source", default="snapshot", choices=["snapshot", "yfinance", "synthetic"])
        p.add_argument("--tickers", nargs="*"); p.add_argument("--universe")
        p.add_argument("--profile", default="swing"); p.add_argument("--bench", default="SPY")
        p.add_argument("--n-synth", type=int, default=50); p.add_argument("--seed", type=int, default=42)
        p.add_argument("--hist-days", type=int, default=260); p.add_argument("--top", type=int, default=10)

    p = sub.add_parser("fetch", help="bajar datos de Yahoo"); p.add_argument("tickers", nargs="*"); p.add_argument("--universe"); p.add_argument("--resume", "--skip-fresh", dest="resume", action="store_true", help="saltar los que ya se bajaron hoy (reanudar)"); p.add_argument("--bench", default="SPY")
    p.add_argument("--no-bench", action="store_true"); p.add_argument("--period", default="2y", help="historial de precios: 2y, 5y, 10y"); p.add_argument("--pause", type=float, default=1.0); p.set_defaults(f=cmd_fetch)
    p = sub.add_parser("score", help="puntuar y guardar ranking"); src(p); p.add_argument("--label", default=""); p.set_defaults(f=cmd_score, profile="both")
    p = sub.add_parser("top", help="top-N de lo guardado"); p.add_argument("--n", type=int, default=10); p.add_argument("--run", type=int); p.add_argument("--sector"); p.add_argument("--all", action="store_true", help="incluir DATOS INCOMPLETOS"); p.add_argument("--max-sector", type=int, default=0, help="tope de empresas por sector en el top"); p.set_defaults(f=cmd_top)
    p = sub.add_parser("show", help="reporte individual"); p.add_argument("ticker"); p.add_argument("--profile", default="swing"); p.set_defaults(f=cmd_show)
    p = sub.add_parser("compare", help="comparar 2+ empresas lado a lado"); p.add_argument("tickers", nargs="+"); p.add_argument("--profile", default="swing"); p.set_defaults(f=cmd_compare)
    p = sub.add_parser("history"); p.add_argument("ticker"); p.set_defaults(f=cmd_history)
    p = sub.add_parser("validate", help="validar contra scores clásicos y estabilidad"); src(p); p.set_defaults(f=cmd_validate)
    p = sub.add_parser("export", help="Excel"); src(p); p.add_argument("--xlsx", default="out/ranking.xlsx"); p.set_defaults(f=cmd_export)
    p = sub.add_parser("forward", help="¿el top-N guardado rindió más que el resto y SPY?"); p.add_argument("--run", type=int); p.add_argument("--profile", default="swing")
    p.add_argument("--label"); p.add_argument("--top", type=int, default=10); p.set_defaults(f=cmd_forward)
    p = sub.add_parser("backtest", help="backtest de señales de PRECIO"); src(p); p.add_argument("--horizon", type=int, default=21); p.add_argument("--step", type=int, default=21)
    p.add_argument("--csv"); p.set_defaults(f=cmd_backtest)
    p = sub.add_parser("plan", help="stop, objetivo y tamaño de posición"); p.add_argument("ticker"); p.add_argument("--capital", type=float, required=True)
    p.add_argument("--risk", type=float, default=0.01, help="fracción del capital a arriesgar (0.01=1%%)"); p.add_argument("--fx", type=float, default=1.0, help="tu moneda por 1 USD")
    p.add_argument("--currency", default="USD"); p.add_argument("--max-position", type=float, default=0.25); p.add_argument("--profile", default="swing"); p.set_defaults(f=cmd_plan)
    p = sub.add_parser("journal", help="diario de operaciones"); js = p.add_subparsers(dest="jcmd", required=True)
    q = js.add_parser("open"); q.add_argument("ticker"); q.add_argument("--entry", type=float, required=True); q.add_argument("--stop", type=float, required=True)
    q.add_argument("--target", type=float, required=True); q.add_argument("--shares", type=float, required=True); q.add_argument("--thesis", default=""); q.add_argument("--real", action="store_true")
    q = js.add_parser("close"); q.add_argument("id", type=int); q.add_argument("--exit", type=float, required=True); q.add_argument("--note", default="")
    js.add_parser("list"); js.add_parser("stats"); p.set_defaults(f=cmd_journal)
    p = sub.add_parser("news", help="titulares recientes (Yahoo)"); p.add_argument("ticker"); p.add_argument("--n", type=int, default=8); p.set_defaults(f=cmd_news)
    p = sub.add_parser("weekly", help="flujo semanal completo"); p.add_argument("--universe", required=True); p.add_argument("--label", default=""); p.add_argument("--top", type=int, default=10)
    p.add_argument("--pause", type=float, default=1.0); p.add_argument("--period", default="2y"); p.set_defaults(f=cmd_weekly)
    p = sub.add_parser("demo"); p.add_argument("--seed", type=int, default=42); p.set_defaults(f=cmd_demo)
    a = ap.parse_args(argv)
    Path(a.db).parent.mkdir(parents=True, exist_ok=True)
    a.f(a)


if __name__ == "__main__":
    main()
