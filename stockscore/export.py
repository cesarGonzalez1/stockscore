import pandas as pd
from .ranking import to_frame
from .report import LABELS


def to_excel(results, path, extra: dict | None = None):
    """Exporta ranking, métricas crudas, puntajes por métrica y alertas a un .xlsx."""
    rk = to_frame(results)
    met = pd.DataFrame({r.ticker: {LABELS.get(k, k): v for k, v in r.metrics.items() if not k.startswith("_") and isinstance(v, (int, float))} for r in results}).T
    ms = pd.DataFrame({r.ticker: {LABELS.get(k, k): v for k, v in r.metric_scores.items()} for r in results}).T
    fl = pd.DataFrame([{"ticker": r.ticker, "vetos": " | ".join(r.vetoes), "alertas": " | ".join(r.warnings)} for r in results])
    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        rk.to_excel(xw, sheet_name="Ranking", index=False)
        met.to_excel(xw, sheet_name="Metricas_crudas")
        ms.to_excel(xw, sheet_name="Puntajes_metricas")
        fl.to_excel(xw, sheet_name="Alertas", index=False)
        for name, df in (extra or {}).items():
            df.to_excel(xw, sheet_name=name[:31], index=False)
        for ws in xw.book.worksheets:
            ws.freeze_panes = "B2"
            for col in ws.columns:
                ws.column_dimensions[col[0].column_letter].width = min(40, max(10, max(len(str(c.value or "")) for c in col) + 2))
