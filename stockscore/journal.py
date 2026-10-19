"""Diario de operaciones (papel o real): registra tesis, entrada/stop/objetivo, y mide R, % de aciertos y si el puntaje ayudó."""
import datetime as dt
import pandas as pd

SCHEMA = """
CREATE TABLE IF NOT EXISTS trades(id INTEGER PRIMARY KEY AUTOINCREMENT, ticker TEXT, opened TEXT, entry REAL, stop REAL, target REAL,
  shares REAL, thesis TEXT, score_at_entry REAL, signal_at_entry TEXT, status TEXT DEFAULT 'open', closed TEXT, exit REAL, note TEXT, paper INTEGER DEFAULT 1);
"""


class Journal:
    def __init__(self, con):
        self.con = con
        con.executescript(SCHEMA)

    def open(self, ticker, entry, stop, target, shares, thesis="", score=None, signal=None, opened=None, paper=True) -> int:
        if stop >= entry:
            raise ValueError("Para una compra el stop debe estar debajo de la entrada")
        cur = self.con.execute("INSERT INTO trades(ticker,opened,entry,stop,target,shares,thesis,score_at_entry,signal_at_entry,paper) VALUES(?,?,?,?,?,?,?,?,?,?)",
                               (ticker.upper(), opened or dt.date.today().isoformat(), entry, stop, target, shares, thesis, score, signal, int(paper)))
        self.con.commit()
        return cur.lastrowid

    def close(self, trade_id, exit_price, closed=None, note=""):
        r = self.con.execute("SELECT status FROM trades WHERE id=?", (trade_id,)).fetchone()
        if not r:
            raise ValueError(f"operación {trade_id} no existe")
        if r[0] == "closed":
            raise ValueError(f"operación {trade_id} ya estaba cerrada")
        self.con.execute("UPDATE trades SET status='closed', exit=?, closed=?, note=? WHERE id=?",
                         (exit_price, closed or dt.date.today().isoformat(), note, trade_id))
        self.con.commit()

    def frame(self, prices: dict | None = None) -> pd.DataFrame:
        df = pd.read_sql("SELECT * FROM trades ORDER BY id", self.con)
        if df.empty:
            return df
        df["last"] = df.apply(lambda r: r["exit"] if r["status"] == "closed" else (prices or {}).get(r["ticker"]), axis=1)
        risk = df["entry"] - df["stop"]
        df["ret"] = df["last"] / df["entry"] - 1
        df["R"] = (df["last"] - df["entry"]) / risk
        df["pnl"] = (df["last"] - df["entry"]) * df["shares"]
        return df

    def stats(self) -> dict:
        df = self.frame()
        c = df[df.status == "closed"] if len(df) else df
        if c.empty:
            return {"cerradas": 0}
        w = c[c.R > 0]
        out = {"cerradas": len(c), "aciertos": len(w), "pct_acierto": len(w) / len(c), "R_promedio": float(c.R.mean()),
               "R_mejor": float(c.R.max()), "R_peor": float(c.R.min()),
               "expectativa_R": float(c.R.mean()),
               "factor_ganancia": float(w.R.sum() / -c[c.R <= 0].R.sum()) if (c.R <= 0).any() and (c[c.R <= 0].R.sum() != 0) else None}
        s = c.dropna(subset=["score_at_entry"])
        if len(s) >= 4:
            out["puntaje_prom_ganadoras"] = float(s[s.R > 0].score_at_entry.mean()) if (s.R > 0).any() else None
            out["puntaje_prom_perdedoras"] = float(s[s.R <= 0].score_at_entry.mean()) if (s.R <= 0).any() else None
        out["nota"] = "Con <30 operaciones cerradas las estadísticas son ruido; úsalas para aprender, no para concluir."
        return out
