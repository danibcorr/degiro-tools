# degiro-calculator

Calculadora en Python para estimar el IRPF (España) de ganancias/pérdidas patrimoniales a
partir de un extracto CSV exportado desde Degiro («Estado de cuenta»).

Aplica FIFO por ISIN usando el contravalor **EUR real** del broker (filas
`Cambio de Divisa` en EUR), imputa comisiones al coste o a la transmisión y estima la
cuota por tramos de la base del ahorro.

Dependencia de runtime única: [rich](https://github.com/Textualize/rich) para el
formateo del informe por consola.

## Instalación

Este proyecto usa [uv](https://docs.astral.sh/uv/) para gestionar el entorno:

```bash
uv sync                     # instala el paquete en modo editable
uv sync --group pipeline    # incluye ruff/mypy/complexipy/pytest para desarrollo
```

Para ejecutar los tests:

```bash
uv run pytest
```

## Uso

```bash
uv run degiro-calc Account.csv
# equivalente:
uv run python -m degiro_calculator Account.csv
```

Opciones:

- `--no-tax` — omite la estimación de cuota IRPF y la rentabilidad neta.
- `-v`, `--verbose` — muestra el traceback completo en caso de error.
- `--version` — muestra la versión del paquete.

## Normativa aplicada

Ley 35/2006 del IRPF
([BOE-A-2006-20764](https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764)):

- **Art. 35.1.b** — los gastos inherentes a la adquisición suman al coste.
- **Art. 35.2** — los gastos satisfechos por el transmitente restan del valor de
  transmisión.
- **Art. 37.2** — con valores homogéneos se entienden transmitidos los adquiridos primero
  (FIFO).
- **Art. 66** — tipos progresivos de la base imponible del ahorro (estimación de cuota).

## Limitaciones

- No cubre dividendos, intereses ni retenciones (solo ganancias/pérdidas por
  transmisión).
- No aplica la regla de los dos meses (recompra) de valores homogéneos.
- No gestiona splits, contra-splits ni operaciones corporativas complejas.
- La cuota IRPF es una **estimación aislada**: la cuota real depende del conjunto de tu
  base del ahorro (otras GP, dividendos, compensaciones de años anteriores).
- Las comisiones de conectividad con el mercado se reportan aparte; no se imputan al
  coste FIFO.
