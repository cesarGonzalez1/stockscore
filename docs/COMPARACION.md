# Comparación: este scorecard vs scorecards ya creados (Apple vs Nike, datos 2026-10-09)

## Resultados en las dos empresas reales
| Sistema | Apple (AAPL) | Nike (NKE) | ¿Quién gana? |
|---|---|---|---|
| **Este scorecard – swing** | **64.9** (C, "vigilar") | **27.0** (F) | Apple |
| **Este scorecard – investor** | **56.5** (D) | **36.0** (F) | Apple (brecha menor) |
| Piotroski F (calculado, fiscal anual) | 8 (el sitio reporta 8 ✔) | 4 (el sitio reporta 5 ✘) | Apple |
| Altman Z'' (no manufactureras) | 2.31 zona gris | 3.44 segura | Nike |
| Altman Z original (sitio, TTM) | 10.93 (mi cálculo fiscal: 12.58) | 4.14 (mi cálculo: 3.25) | Apple |
| Magic Formula (EBIT/EV y ROIC) | EBIT/EV 3.2%, ROIC 93% | EBIT/EV 7.6%, ROIC 19% | Empate en un universo de 2 (solo es útil con ≥30 empresas) |
| Momentum 12m (Jegadeesh-Titman) | +30% | −50% | Apple |
| Consenso de analistas | Buy (44), objetivo −2.5% bajo precio | Hold (42), objetivo +9.6% | Nike en upside / Apple en consenso |
| DCF base propio (r 9%, g terminal 3%) | 226.8 vs 336.6 (−33%) | 20.6 vs 34.7 (−41%) | Ambas caras vs DCF |
| DCF inverso (crecimiento exigido) | 19.4%/año vs 10.2% esperado | 12.0%/año vs 1.3% esperado | Ambas exigen más de lo esperado |

**Lectura:** Apple queda arriba por **calidad (88 vs 48) + tendencia (78 vs 0)**, no por precio. En el pilar *valor* Nike sale mejor (40 vs 16). Es decir: Apple = empresa excelente pero cara; Nike = barata pero con negocio y precio deteriorándose ("cuchillo cayendo"). Para un swing de 1-3 meses el sistema prefiere tendencia; para inversión larga la brecha se achica y **ninguna** pasa a "candidata".
Diferencias con el sitio (Piotroski NKE 4 vs 5, Altman): el sitio usa TTM/trimestres; yo uso el último año fiscal vs el anterior. Es normal, y se reporta tal cual en `validate`.

## Cómo se compara el método con los scorecards conocidos
| Scorecard | Qué mide | Automatizable con datos gratis | Qué aporta mi sistema que ellos no |
|---|---|---|---|
| Piotroski F | Calidad contable (9 señales binarias) | Sí | Lo incluye como una métrica más, no como veredicto |
| Altman Z / Z'' | Riesgo de quiebra | Sí | Lo usa como **veto**, no como puntaje central |
| Magic Formula | Barata + buen ROIC (ranking) | Sí | Añade crecimiento, tendencia, riesgo y catalizadores |
| QMJ (AQR) | Calidad: rentable, crece, segura, paga | Parcial | Misma idea de calidad; sin rankeo cross-section |
| Morningstar | DCF 3 etapas + moat + incertidumbre | No (propietario/cualitativo) | DCF simple + **DCF inverso** y rejilla de sensibilidad |
| Zacks Rank | Revisiones de estimaciones (EPS) | No (requiere histórico de estimaciones) | No replicado; punto abierto |
| Análisis técnico clásico | Medias, RSI | Sí | Tendencia por momentum/SMA/t-stat; RSI solo alerta |

**Dónde es más débil mi scorecard:** (1) pesos y rangos son priors no calibrados con retornos; (2) no hay revisiones de estimaciones (el factor tipo Zacks tiene evidencia propia); (3) sin backtest point-in-time; (4) ventana de precios corta en los snapshots de prueba.

## Validación estadística
**A) 50 empresas REALES (Yahoo, 12-oct-2026, versión anterior sin ROE/valor en libros):**
| Perfil | Spearman vs Piotroski / Altman / Magic Formula / momentum / FCF yield | Solape top-10 (Piotroski / Altman / Magic / momentum) | Estabilidad de pesos (±50%) |
|---|---|---|---|
| swing | 0.24 / 0.34 / **0.05** / **0.64** / **0.04** | 5 / 3 / 3 / 4 | Spearman medio 0.96 (mín 0.80); top-10 se mantiene 8.2/10 (mín 6) |
| investor | 0.25 / 0.34 / **0.45** / 0.06 / **0.49** | 1 / 4 / 6 / 2 | Spearman medio 0.94 (mín 0.78); top-10 se mantiene 8.2/10 (mín 6) |
Lectura: el perfil **swing se parece a momentum** (0.64) y casi no distingue baratas de caras; el **investor sí sigue valor** (Magic 0.45, FCF 0.49) y casi ignora momentum. Es el comportamiento diseñado. Con solo 50 empresas casi todas grandes y muy parecidas, los puestos 5-12 no son distinguibles con confianza.

**B) Universo sintético** (50 empresas inventadas; solo prueba la mecánica): swing: Magic 0.77, FCF 0.59, momentum 0.49, Altman 0.32, Piotroski 0.14; investor: Magic 0.83, FCF 0.75, momentum 0.13. Estabilidad 0.97 (mín 0.90). **No indica calidad predictiva.**

**C) Lo que falta para saber si predice:** el **forward** (varias semanas de corridas guardadas) y el backtest de precio sobre tus 50 reales: `python -m stockscore.cli backtest --universe config/universe_50.txt`.
