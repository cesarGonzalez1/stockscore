# stockscore — evaluar, rankear, validar y dar seguimiento a acciones

Puntúa cada empresa 0-100 en **valor, calidad, crecimiento, tendencia, riesgo y catalizadores**; da nota A-F, alertas y señal; guarda cada corrida en SQLite; mide **hacia adelante** si el ranking sirve; calcula **stop, objetivo y tamaño de posición**; y lleva un **diario de operaciones**.

> Herramienta para **descartar y priorizar**, no para predecir. No es asesoría financiera.

## Instalación (Mac, Python 3.12; el 3.14 rompe pandas)
```bash
cd stockscore
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest -q                      # debe dar: 45 passed (no necesita internet ni scipy)
```
Si mueves la carpeta, borra `.venv` y créalo otra vez (guarda rutas fijas).

## Rutina semanal (la que importa)
```bash
source .venv/bin/activate
python -m stockscore.cli weekly --universe config/universe_50.txt     # ~10-15 min (pausas para que Yahoo no te frene)
```
En un solo paso: baja datos → puntúa swing e investor → guarda la corrida (etiqueta `AAAA-Wss`) → muestra el top 10 con **cambio de puesto y de puntos** vs la corrida anterior → evalúa con el **forward** la corrida de hace ≥ 7 días.
Después, para lo que te interese:
```bash
python -m stockscore.cli top --n 10 --sector Technology
python -m stockscore.cli show CVX                    # reporte individual + sensibilidad DCF + vetos/alertas
python -m stockscore.cli compare AAPL NKE CVX        # lado a lado
python -m stockscore.cli news CVX                    # titulares recientes (Yahoo) para revisar el catalizador
python -m stockscore.cli plan CVX --capital 10000 --fx 18.5 --currency MXN --risk 0.01
```

## Todos los comandos
| Comando | Para qué |
|---|---|
| `fetch T1 T2 … [--period 5y] [--skip-fresh]` | Baja datos de Yahoo a `data/snapshots/` (reintenta si Yahoo limita; `--skip-fresh` reanuda sin repetir los de hoy). `--period 5y` da más historia para el backtest. |
| `score --universe f` | Puntúa y guarda ranking (ambos perfiles). `--label nombre` |
| `weekly --universe f` | Todo el flujo semanal (arriba). |
| `top --n 10 [--sector S] [--run N]` | Top-N de lo guardado. |
| `show T` / `compare T1 T2 …` | Reporte individual / lado a lado. |
| `history T` | Cómo ha cambiado el puesto y puntaje de una empresa entre corridas. |
| `forward [--run N]` | **Validación hacia adelante**: rendimiento del top-N guardado vs resto y vs SPY a 1/2/4/8/12 semanas, con IC. |
| `backtest --universe f` | (mejor con `config/universe_150.txt` y `--period 5y`) Backtest **solo de precio** (momentum/tendencia) sin mirada al futuro. |
| `validate --universe f [--profile investor]` | Correlación y solape con Piotroski/Altman/Magic Formula/momentum + estabilidad de pesos. |
| `plan T --capital X [--fx 18.5 --currency MXN --risk 0.01]` | Stop por volatilidad, objetivo, riesgo/beneficio, probabilidad necesaria vs simulada, tamaño de posición por riesgo fijo. |
| `journal open/close/list/stats` | Diario de operaciones (papel por defecto, `--real` para reales): R, % de aciertos, ¿el puntaje ayudó? |
| `export --universe f --xlsx out/r.xlsx` | Excel con ranking, métricas, alertas. |
| `news T` | Titulares recientes. |
| `demo` | Demo offline con fixtures + 48 empresas sintéticas. |

## Universos
`config/universe_50.txt` (50 grandes) y `config/universe_150.txt` (~150). Más empresas = más poder estadístico para `backtest`, `validate` y `forward`:
```bash
python -m stockscore.cli fetch $(grep -v '^#' config/universe_150.txt) --period 5y --skip-fresh   # ~40 min; si se corta, repite el mismo comando
python -m stockscore.cli backtest --universe config/universe_150.txt
```

## Cómo usar el forward (la validación que de verdad cuenta)
1. Cada semana corre `weekly` (o `score --label …`). Cada corrida queda guardada con su fecha.
2. Después de 4 semanas: `python -m stockscore.cli forward --run N`. Entrada = primer cierre **posterior** a la señal.
3. Mira **IC > 0 de forma repetida** (el puntaje ordena bien) y **top vs SPY**. Una corrida sola no prueba nada; con 8-12 corridas empieza a haber evidencia.
Si el top-10 no le gana de forma consistente a SPY ni al resto, el sistema no aporta edge: ajusta pesos (`config/default.yaml`) o úsalo solo como filtro de riesgo.

## Cómo usar `plan` y `journal` (disciplina de swing)
```bash
python -m stockscore.cli plan CVX --capital 10000 --fx 18.5 --currency MXN
python -m stockscore.cli journal open CVX --entry 160.5 --stop 152 --target 173 --shares 0.8 --thesis "resultados + tendencia"
python -m stockscore.cli journal list        # P&L y R de abiertas (con el último precio bajado) y cerradas
python -m stockscore.cli journal close 1 --exit 171
python -m stockscore.cli journal stats       # % aciertos, R promedio, ¿ganadoras tenían mayor puntaje?
```
`plan` te dice cuánto comprar para perder como máximo X% del capital si toca el stop, y avisa si hay earnings cerca, si el riesgo/beneficio es malo o si la probabilidad simulada de llegar al objetivo es menor que la que necesitas.
Empieza en **papel** (sin `--real`) hasta tener ≥ 30 operaciones cerradas.

## Universos
`config/universe_50.txt` (50 grandes, rápido) y `config/universe_150.txt` (~150, varios sectores: más poder estadístico para el backtest y el forward; el `fetch` tarda ~30-40 min, usa `--resume` si se corta). Algunos tickers pueden fallar en Yahoo: se saltan y se avisa.

## Estructura
`stockscore/` metrics (valuation, quality, growth, trend, risk, catalysts) · scoring · ranking · storage (SQLite) · forward · backtest · plan · journal · workflow · validate · report · export · providers (snapshot, yfinance) · `config/default.yaml` (rangos y pesos editables) · `docs/` · `tests/` (con fixtures propios) · `data/snapshots/` (tus datos).

## Límites honestos
- Sin backtest de rentabilidad de **fundamentales** (faltan datos point-in-time): lo único limpio es el forward y el backtest de precio.
- Backtest de precio: sesgo de supervivencia, ~1 año de señales, periodos que se solapan. Indicio, no prueba.
- Bancos/seguros: evaluación **parcial** (sin EV/FCF/ROIC/Altman/DCF); energía/materiales: alerta de **ciclicidad**.
- Yahoo no siempre da el crecimiento esperado de analistas; si falta, el DCF usa el EPS adelantado y el crecimiento de ingresos reciente (acotados), y lo anota.
- Pesos y rangos son criterio razonado, no calibrado con retornos.
- `plan` y el diario son calculadoras de disciplina, no señales de compra.
