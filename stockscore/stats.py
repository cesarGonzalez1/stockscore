import numpy as np
import pandas as pd


def spearman(a, b) -> float:
    """Correlación de Spearman sin scipy: Pearson sobre rangos (alineado por índice)."""
    d = pd.concat([pd.Series(a), pd.Series(b)], axis=1, keys=["a", "b"]).dropna()
    if len(d) < 3:
        return float("nan")
    ra, rb = d["a"].rank(), d["b"].rank()
    if ra.std() == 0 or rb.std() == 0:
        return float("nan")
    return float(np.corrcoef(ra, rb)[0, 1])


def tstat(x) -> float:
    x = pd.Series(x).dropna()
    if len(x) < 3 or x.std(ddof=1) == 0:
        return float("nan")
    return float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x))))
