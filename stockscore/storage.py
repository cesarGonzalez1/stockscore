"""Persistencia SQLite: cada corrida (run) guarda el ranking completo para comparar en el tiempo."""
import json, sqlite3, datetime as dt
import pandas as pd

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, profile TEXT, config_hash TEXT, label TEXT, n INTEGER);
CREATE TABLE IF NOT EXISTS scores(run_id INTEGER, ticker TEXT, name TEXT, sector TEXT, rank INTEGER, total REAL, grade TEXT,
  signal TEXT, coverage REAL, pillars TEXT, metrics TEXT, metric_scores TEXT, vetoes TEXT, warnings TEXT, notes TEXT, as_of TEXT,
  PRIMARY KEY(run_id, ticker));
CREATE INDEX IF NOT EXISTS ix_scores_ticker ON scores(ticker);
"""


def _clean(d):
    return {k: v for k, v in d.items() if not k.startswith("_")}


class Store:
    def __init__(self, path="out/stockscore.db"):
        self.con = sqlite3.connect(path)
        self.con.executescript(SCHEMA)

    def save_run(self, results, profile, config_hash="", label="") -> int:
        cur = self.con.execute("INSERT INTO runs(ts,profile,config_hash,label,n) VALUES(?,?,?,?,?)",
                               (dt.datetime.now().isoformat(timespec="seconds"), profile, config_hash, label, len(results)))
        rid = cur.lastrowid
        for i, r in enumerate(sorted(results, key=lambda x: -x.total), 1):
            self.con.execute("INSERT INTO scores VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (rid, r.ticker, r.name, r.sector, i, r.total, r.grade, r.signal, r.coverage, json.dumps(r.pillars),
                 json.dumps(_clean(r.metrics), default=str), json.dumps(r.metric_scores), json.dumps(r.vetoes),
                 json.dumps(r.warnings), json.dumps(r.notes), r.as_of))
        self.con.commit()
        return rid

    def latest_run(self, profile=None, label=None):
        q, a = "SELECT id FROM runs WHERE 1=1", []
        if profile: q += " AND profile=?"; a.append(profile)
        if label: q += " AND label=?"; a.append(label)
        row = self.con.execute(q + " ORDER BY id DESC LIMIT 1", a).fetchone()
        return row[0] if row else None

    def run_info(self, run_id) -> dict | None:
        r = self.con.execute("SELECT id,ts,profile,config_hash,label,n FROM runs WHERE id=?", (run_id,)).fetchone()
        if not r:
            return None
        asof = self.con.execute("SELECT MAX(as_of) FROM scores WHERE run_id=?", (run_id,)).fetchone()[0]
        return dict(id=r[0], ts=r[1], profile=r[2], config_hash=r[3], label=r[4], n=r[5], as_of=asof)

    def previous_run(self, profile, before_id):
        row = self.con.execute("SELECT id FROM runs WHERE profile=? AND id<? ORDER BY id DESC LIMIT 1", (profile, before_id)).fetchone()
        return row[0] if row else None

    def runs(self) -> pd.DataFrame:
        return pd.read_sql("SELECT * FROM runs ORDER BY id", self.con)

    def ranking(self, run_id=None, n=None, sector=None, only_eligible=True) -> pd.DataFrame:
        """Ranking guardado. Por defecto sin las 'DATOS INCOMPLETOS' y con puestos re-numerados."""
        run_id = run_id or self.latest_run()
        df = pd.read_sql("SELECT rank,ticker,name,sector,total,grade,signal,coverage,pillars FROM scores WHERE run_id=? ORDER BY rank",
                         self.con, params=(run_id,))
        pil = df.pop("pillars").apply(json.loads)
        for p in ["value", "quality", "growth", "trend", "risk", "catalysts"]:
            df[p] = pil.apply(lambda d: None if d.get(p, {}).get("score") is None else round(d[p]["score"], 1))
        if only_eligible:
            df = df[df.signal != "DATOS INCOMPLETOS"].copy()
            df["rank"] = range(1, len(df) + 1)
        if sector:
            df = df[df.sector == sector]
        df = df.head(n) if n else df
        return df.reset_index(drop=True)

    def get(self, ticker, run_id=None) -> dict | None:
        run_id = run_id or self.latest_run()
        row = self.con.execute("SELECT * FROM scores WHERE run_id=? AND ticker=?", (run_id, ticker.upper())).fetchone()
        if not row:
            return None
        cols = [c[0] for c in self.con.execute("SELECT * FROM scores LIMIT 0").description]
        d = dict(zip(cols, row))
        for k in ("pillars", "metrics", "metric_scores", "vetoes", "warnings", "notes"):
            d[k] = json.loads(d[k])
        return d

    def history(self, ticker) -> pd.DataFrame:
        return pd.read_sql("SELECT s.run_id, r.ts, r.profile, s.rank, s.total, s.grade, s.signal FROM scores s JOIN runs r ON r.id=s.run_id "
                           "WHERE s.ticker=? ORDER BY s.run_id", self.con, params=(ticker.upper(),))
