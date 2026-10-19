# Research: cómo se estima el valor de una empresa y si su precio puede subir

Resumen de los métodos más usados por analistas y académicos, y de la evidencia (y sus límites). Fecha: 2026-10-09.

## 1. ¿Cuánto vale la empresa? (valor "real" o intrínseco)

| Método | Idea | Quién lo usa | Debilidad |
|---|---|---|---|
| **DCF** (flujo de caja descontado) | Valor = flujos futuros de caja traídos a valor presente con costo de capital | Damodaran (NYU), bancos, Morningstar (DCF de 3 etapas: explícita, desvanecimiento hasta que ROIC → costo de capital, perpetuidad) | Muy sensible a crecimiento y tasa (±1 pt de tasa mueve el valor 15-25%) |
| **DCF inverso** (expectations investing, Mauboussin/Rappaport) | En vez de adivinar el futuro, se despeja **qué crecimiento está ya descontado en el precio** y se compara con lo plausible | Gestores value y growth | Requiere decidir qué es "plausible" |
| **Múltiplos relativos** | P/E, EV/EBIT, EV/EBITDA, P/FCF, FCF yield frente a pares/historia | Todo el mercado | Compara contra un mercado que puede estar caro/barato completo |
| **Valoración por opciones / contingente** | Para empresas jóvenes o con recursos naturales | Damodaran | Poco útil para large caps maduras |
| **Moat + incertidumbre** (Morningstar) | Ventaja competitiva durable (marca, costos de cambio, red, costo, escala) y rango de resultados → estrellas vs fair value | Morningstar | Cualitativo; no automatizable sin analista |

Conclusión práctica: no existe "el" valor real; se usa un **rango** (DCF con sensibilidad) y se contrasta con múltiplos y con lo que el precio ya descuenta.

## 2. ¿Es buena empresa? (calidad y salud financiera)

- **Piotroski F-Score (2000)**: 9 señales binarias (rentabilidad, apalancamiento/liquidez, eficiencia operativa). Diseñado para acciones baratas (alto book-to-market); hoy se usa como filtro general.
- **Altman Z (1968)** y **Z'' (1995, no manufactureras)**: probabilidad de quiebra. Z'' < 1.1 zona de peligro, 1.1-2.6 gris, > 2.6 segura. Penaliza empresas con capital de trabajo negativo y utilidades retenidas negativas por recompras (caso Apple) → señal gris "falsa".
- **Gross profitability** (Novy-Marx 2013), **ROIC**, **conversión FCF/utilidad**, **accruals de Sloan (1996)**: calidad de resultados; accruals altos predicen peores retornos.
- **Magic Formula** (Greenblatt): ranking combinado de EBIT/EV (barata) y ROIC (buena).
- **QMJ – Quality Minus Junk** (Asness, Frazzini, Pedersen): rentable + crece + segura + paga bien a accionistas.

## 3. ¿Está en buen o mal momento? (matemática de precio)

- **Momentum 12-1 meses** (Jegadeesh & Titman 1993): ganadores de los últimos 12 meses (sin el último mes) tienden a seguir ganando 3-12 meses. Es la anomalía más replicada, pero con *crashes* en rebotes de mercado.
- **Tendencia con media móvil 10 meses / SMA200** (Faber 2007): estar sobre la media filtra las caídas largas.
- **Cruce SMA50/SMA200**, **pendiente de regresión del log-precio con t-stat**: miden fuerza y limpieza de la tendencia.
- **Fuerza relativa vs el índice** (SPY).
- **RSI**: no se usa para puntuar (evidencia débil); solo como **alerta** de sobrecompra.
- **Volatilidad, drawdown, beta**: riesgo realizado.
- **Probabilidad de swing**: simulación (GBM) de P(+X% antes que −Y% en H días). Con deriva CAPM supuesta, mide más bien "capacidad de moverse" que un pronóstico.
- **Eventos**: PEAD (la deriva posterior a resultados), revisiones de estimaciones (Zacks), cercanía de earnings (catalizador y riesgo binario).

## 4. Lo que la evidencia NO permite prometer

1. **Decaimiento post-publicación**: McLean & Pontiff (J. Finance 2016) hallan que el retorno de una anomalía cae ~26% fuera de muestra y ~58% tras publicarse.
2. **Data snooping**: con cientos de factores, muchos "funcionan" por azar; por eso se usa pocos y con sustento económico.
3. **Sesgos de backtest con datos gratis**: sin fundamentales *point-in-time* ni empresas deslistadas hay sesgo de supervivencia y de mirada al futuro. Un backtest de fundamentales con Yahoo **no es confiable**.
4. **Momentum crashes** y concentración de varios factores en small caps (menos líquidas).
5. Ningún score predice una operación individual de 1-3 meses: **solo desplaza probabilidades** y ayuda a descartar. Eso es lo que este sistema pretende.

## 5. Decisiones de diseño derivadas

- Pocos factores con sustento: valor (FCF yield, EV/EBIT, DCF inverso), calidad (Piotroski, ROIC, accruals…), crecimiento, tendencia (momentum), riesgo.
- DCF inverso como métrica central de valor: compara lo que el precio exige vs lo que los analistas esperan.
- Perfil **swing** (peso a tendencia/catalizadores) y perfil **investor** (peso a valor/calidad).
- Alertas explícitas en vez de "magia": earnings cercanos, sobrecompra, ventana de datos corta, precio muy sobre DCF.
- Validación contra scores clásicos y prueba de estabilidad de pesos; **no** se afirma rentabilidad sin backtest *point-in-time*.

## Fuentes
- Damodaran, Valuation (NYU Stern): https://pages.stern.nyu.edu/~adamodar/
- Morningstar, Equity Research Methodology (DCF 3 etapas, moat, incertidumbre) — documento consultado en la sesión.
- Piotroski, J. (2000). *Value Investing…*, Journal of Accounting Research.
- Altman, E. (1968), *J. Finance*; Altman (1995) Z'' para no manufactureras.
- Jegadeesh & Titman (1993), *J. Finance*. Faber (2007), *A Quantitative Approach to Tactical Asset Allocation*.
- Novy-Marx (2013), *The Other Side of Value: The Gross Profitability Premium*, JFE. Sloan (1996), *Accounting Review*.
- Asness, Frazzini, Pedersen, *Quality Minus Junk*. Greenblatt, *The Little Book That Beats the Market*.
- McLean & Pontiff (2016), *Does Academic Research Destroy Stock Return Predictability?*, J. Finance.
- Mauboussin & Rappaport, *Expectations Investing*.
- Datos de Apple/Nike/SPY: https://stockanalysis.com/stocks/aapl/ · https://stockanalysis.com/stocks/nke/ (S&P Global Market Intelligence), leídos 2026-10-09.
