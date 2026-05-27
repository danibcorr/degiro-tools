# Degiro Tools

Herramientas en Python para inversores que usan Degiro:

1. **Tax** — Estima el IRPF (España) de ganancias/pérdidas patrimoniales a partir de un
   extracto CSV de Degiro («Estado de cuenta»). Aplica FIFO por ISIN usando el
   contravalor EUR real del broker, imputa comisiones al coste o a la transmisión y
   estima la cuota por tramos de la base del ahorro.

2. **Portfolio** — Muestra la valoración actual de la cartera en tiempo real con precios
   de Yahoo Finance, clasificación ETF/Acción y porcentaje de cada posición sobre el
   total invertido. Lee el fichero XLSX exportado desde Degiro (Portfolio).

Requiere Python 3.11+.

## Instalación

Con [uv](https://docs.astral.sh/uv/):

```bash
uv sync                     # runtime
uv sync --group pipeline    # + ruff/mypy/complexipy/pytest
```

## Uso

```bash
# Cálculo fiscal desde CSV (Estado de cuenta)
uv run degiro-tools tax Account.csv

# Valoración de cartera desde XLSX (Portfolio)
uv run degiro-tools portfolio Portfolio.xlsx
```

### Subcomando `tax`

```
degiro-tools tax <csv_path> [--no-tax] [-v/--verbose] [--version]
```

- `--no-tax` — Omite la estimación IRPF.
- `-v/--verbose` — Traceback completo en caso de error.

La salida usa colores y paneles de rich (verde G/P positivo, rojo negativo). Al redirigir
a archivo, rich emite texto plano automáticamente.

### Subcomando `portfolio`

```
degiro-tools portfolio <xlsx_path> [-v/--verbose]
```

Muestra una tabla con: producto, ISIN, tipo (ETF/Acción), cantidad, precio actual en €,
importe invertido y porcentaje de la cartera.

## Dependencias

| Paquete                                            | Uso                                         |
| -------------------------------------------------- | ------------------------------------------- |
| [rich](https://github.com/Textualize/rich)         | Renderizado del informe fiscal              |
| [polars](https://pola.rs/)                         | Procesamiento del XLSX de portfolio         |
| [yfinance](https://github.com/ranaroussi/yfinance) | Precios en tiempo real y conversión USD→EUR |
| [openpyxl](https://openpyxl.readthedocs.io/)       | Lectura de ficheros Excel                   |

## Normativa aplicada (subcomando `tax`)

Ley 35/2006 del IRPF
([BOE-A-2006-20764](https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764)):

- **Art. 35.1.b** — gastos inherentes a la adquisición suman al coste.
- **Art. 35.2** — gastos satisfechos por el transmitente restan del valor de transmisión.
- **Art. 37.2** — valores homogéneos transmitidos por FIFO.
- **Art. 66** — tipos progresivos de la base imponible del ahorro (estimación de cuota).

## Limitaciones

### Tax

- No cubre dividendos, intereses ni retenciones.
- No aplica la regla de los dos meses (recompra) de valores homogéneos.
- No gestiona splits ni operaciones corporativas complejas.
- La cuota IRPF es una **estimación aislada**: la real depende del conjunto de tu base
  del ahorro.
- Las comisiones de conectividad se reportan aparte, no se imputan al coste FIFO.

### Portfolio

- Requiere conexión a internet (consulta Yahoo Finance).
- La conversión USD→EUR usa el tipo de cambio del momento de ejecución.
- La clasificación ETF/Acción se basa en el nombre del producto (heurística por
  proveedor).
