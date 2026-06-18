# Degiro Tools

CLI para inversores en Degiro: cálculo fiscal IRPF, valoración de cartera y análisis de
composición de ETFs.

Python 3.11+ · [uv](https://docs.astral.sh/uv/) · `uv sync`

## Uso

```bash
uv run degiro-tools tax Account.csv                          # IRPF (FIFO)
uv run degiro-tools portfolio holdings/Portfolio.xlsx        # Valoración actual
uv run degiro-tools holdings holdings/Portfolio.xlsx         # Top holdings reales
uv run degiro-tools overlap holdings/Portfolio.xlsx          # Solapamiento entre ETFs
uv run degiro-tools sectors holdings/Portfolio.xlsx          # Distribución sectorial
uv run degiro-tools geography holdings/Portfolio.xlsx        # Distribución geográfica
```

Los 4 últimos requieren `--config holdings.json` (default) con los ficheros de holdings.

## Setup de holdings

1. Descarga los holdings de cada ETF desde la web del proveedor (iShares `.xls`, Vanguard
   `.xlsx`)
2. Colócalos en `holdings/`
3. Crea `holdings.json`:

```json
{
  "IE00B4L5Y983": "holdings/msci_world.xls",
  "IE00BK5BQX27": "holdings/vanguard_europe.xlsx"
}
```

## Opciones

| Flag              | Descripción                                 |
| ----------------- | ------------------------------------------- |
| `--config <path>` | JSON de holdings (default: `holdings.json`) |
| `--export <path>` | Exporta resultado a CSV                     |
| `--no-tax`        | Omite estimación IRPF (solo `tax`)          |
| `-v`              | Traceback completo                          |

## Notas

- `holdings/` y `holdings.json` están en `.gitignore` (datos personales)
- Precios vía Yahoo Finance (requiere internet)
- Soporta columnas en español e inglés automáticamente
