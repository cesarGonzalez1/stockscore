# Metodología del scorecard

## Flujo
`Snapshot (datos)` → `métricas crudas` → `puntaje 0-100 por métrica` → `pilar = media ponderada` → `total = media ponderada de pilares (según perfil)` → `vetos/alertas` → `nota A-F y señal` → `SQLite` → `ranking / top-N`.

## Puntaje por métrica
Mapa lineal entre `low` (0 pts) y `high` (100 pts) del `config/default.yaml`; se invierte si menor es mejor. Es **absoluto** (no relativo al universo), así que una empresa mantiene su nota aunque agregues más empresas.
Faltantes: el peso de la métrica faltante se redistribuye entre las demás del pilar y el pilar muestra su **cobertura**. Si la cobertura total < 70% → señal "DATOS INCOMPLETOS".

## Pilares y métricas
| Pilar | Métricas (peso) |
|---|---|
| Valor | FCF yield (2), earnings yield (1), EV/EBIT (1), PEG (1), holgura de crecimiento = crecimiento base esperado − crecimiento implícito en el precio (2), margen vs DCF (1.5) |
| Calidad | Piotroski (2), Altman Z'' (1), ROIC (2), gross profitability (1), margen operativo (1), FCF/utilidad (1), accruals (1), tendencia de margen (1), deuda neta/EBITDA (1) |
| Crecimiento | CAGR ingresos 3a, CAGR utilidad 3a, ingresos TTM vs FY, EPS adelantado vs TTM, crec. EPS 3a de analistas |
| Tendencia | momentum (2), precio vs SMA200 (1.5), SMA50 vs SMA200 (1), pendiente t-stat (1), fuerza relativa vs SPY (1.5) |
| Riesgo | volatilidad (1.5), máx. drawdown (1), beta (1), P(swing) (1) |
| Catalizadores | upside a precio objetivo, consenso de analistas, earnings en ventana 3-30 días |

Perfiles (pesos de pilares): **swing** = valor .15, calidad .20, crecimiento .15, tendencia .30, riesgo .10, catalizadores .10. **investor** = valor .30, calidad .30, crecimiento .20, tendencia .10, riesgo .10.
Los pesos y rangos son **priors razonados, no ajustados a datos**. Cámbialos en el YAML y corre `validate` para ver cuánto mueven el ranking.

## DCF y DCF inverso
FCF TTM, crecimiento inicial *g* que se desvanece linealmente a *g terminal* (3%) en 10 años, descontado a 9%. `implied_growth` se despeja por bisección para que el valor presente iguale el EV de mercado. `base_growth` = promedio acotado (−5%…15%) del crecimiento EPS/ingresos a 3 años de analistas (o CAGR histórico si faltan). `growth_headroom = base − implícito`: positivo ⇒ el mercado descuenta menos de lo que se espera. Hay rejilla de sensibilidad (tasa × crecimiento) en `show`.

## Vetos y alertas
- **Veto** (tope de 49 puntos y señal EVITAR): Altman Z'' < 1.1, Piotroski < 3, pierde dinero y quema caja.
- **Alertas** (no cambian el puntaje): RSI > 75, earnings en ≤ 14 días, precio > 30% sobre el DCF base, ventana de precios < 120 días, tendencia rota, cobertura baja.
- **Señal**: CANDIDATA (total ≥ 70 y tendencia ≥ 60), VIGILAR (≥ 60), NO POR AHORA, EVITAR, DATOS INCOMPLETOS.

## Validación incluida (`stockscore validate`)
1. **Correlación de Spearman y solape top-N** contra Piotroski, Altman Z'', Magic Formula, momentum y FCF yield (benchmarks independientes).
2. **Estabilidad de pesos**: 200 perturbaciones de ±50% de los pesos de pilares; mide correlación de ranking y cuántos del top-N se mantienen.
3. **Chequeo contra valores reportados**: Piotroski/Altman calculados vs los de stockanalysis.com.
4. **45 pruebas unitarias** sin internet (fórmulas, DCF inverso, renormalización, persistencia, top-10 de 50, forward, backtest, plan, diario, flujo semanal, proveedor Yahoo con módulo falso).

## Límites conocidos (honestos)
- **No hay backtest de rentabilidad**: se necesitan fundamentales point-in-time y deslistadas; con datos gratis sería engañoso. Lo único backtesteable de forma limpia es la parte de **precio** (tendencia/momentum); queda como siguiente paso.
- Snapshots Apple/Nike traen solo ~50 cierres diarios → volatilidad/drawdown/pendiente/swing poco fiables (el sistema lo avisa). Con Yahoo (2 años) se corrige.
- `swing_prob` usa deriva CAPM supuesta: mide "capacidad de moverse", no pronostica. Peso bajo.
- Altman Z'' castiga a empresas con recompras masivas (Apple cae en zona gris por utilidades retenidas negativas).
- FCF incluye add-back de SBC; en tecnológicas el DCF queda algo optimista.
- Yahoo no entrega crecimiento EPS a 3 años de analistas: esas métricas quedan vacías (baja cobertura) salvo que las completes en el JSON.
- Esto es una herramienta de **descartar y priorizar**, no una orden de compra. No es asesoría financiera.

---
# Ampliaciones (v2)

## Tratamiento de casos especiales
- **Financieras** (industria con *bank, insurance, capital markets, mortgage*): EV, FCF, ROIC, Altman, DCF, margen operativo y PEG se marcan "no aplica"; se usan P/E, valor en libros/precio y ROE. La cobertura baja y puede salir "DATOS INCOMPLETOS": es intencional. No se veta a un banco por Altman.
- **Sectores cíclicos** (Energy, Basic Materials): se añade alerta; el FCF y EPS TTM dependen del ciclo y el DCF/valor pueden verse irrealmente buenos o malos.
- **Crecimiento base del DCF**: promedio de [crecimiento EPS de analistas, crecimiento de ingresos de analistas, EPS adelantado vs TTM, ingresos TTM vs FY], cada uno acotado a [−5%, tope]. El CAGR histórico solo se usa si no hay ninguno. Aviso: el EPS adelantado de Yahoo puede ser *non-GAAP* frente a un TTM GAAP (infla el crecimiento): por eso se acota.
- **swing_prob** pesa 0.5: con volatilidad alta (>35%) se satura (~42%) y deja de discriminar.

## Forward test (`forward`)
Para una corrida guardada: entrada = primer cierre posterior a la fecha de datos; retorno a 1/2/4/8/12 semanas del top-N, del resto y de SPY; `IC` = Spearman entre puntaje y retorno posterior; `% top gana a SPY`. Los horizontes sin datos aparecen como *pendientes*. Es la única prueba sin mirada al futuro; se vuelve concluyente tras muchas corridas (8-12+).

## Backtest de precio (`backtest`)
En cada fecha (cada 21 días hábiles desde el día 252) calcula momentum 12-1, precio vs SMA200, SMA50 vs SMA200 y pendiente t con **solo datos pasados**, arma el pilar de tendencia y mide IC y rendimiento 21 días después del top vs universo vs fondo. Con Yahoo (2 años) son ~12 rebalanceos: indicio, no prueba (supervivencia, solapamiento, sin costos).

## Plan de operación (`plan`)
Stop = 1.5 × volatilidad semanal (acotado 3%-12%); objetivo por defecto +8%; riesgo/beneficio = objetivo/stop; probabilidad de acierto necesaria = stop/(stop+objetivo); simulación GBM con deriva CAPM; tamaño = (capital × riesgo%) / (precio × stop × fx), recortado al máximo por posición (25%). Capital y tipo de cambio se pasan por comando y **no se guardan**.

## Diario (`journal`)
R = (salida − entrada) / (entrada − stop). Estadísticas: % de aciertos, R promedio, factor de ganancia, puntaje medio de ganadoras vs perdedoras (≥ 4 cerradas). Con < 30 cerradas son ruido.
