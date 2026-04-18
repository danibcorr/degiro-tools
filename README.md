# degiro-calculator

Calculadora en Python para estimar el IRPF (España) de ganancias/pérdidas patrimoniales a
partir de un extracto CSV de Degiro («Estado de cuenta»).

Aplica FIFO por ISIN usando el contravalor **EUR real** del broker (filas
`Cambio de Divisa` en EUR), imputa comisiones al coste o a la transmisión y estima la
cuota por tramos de la base del ahorro.

Requiere Python 3.11+. Dependencia de runtime única:
[rich](https://github.com/Textualize/rich).

## Instalación

**Binario standalone** (sin Python): descarga el archivo para tu plataforma desde
[Releases](https://github.com/danibcorr/degiro-calculator/releases) (`linux-x86_64`,
`windows-x86_64.exe`, `macos-aarch64`). En Linux/macOS:
`chmod +x degiro-calc-*`. En macOS, si Gatekeeper bloquea el binario:
`xattr -d com.apple.quarantine degiro-calc-macos-*`.

**Desde fuentes** con [uv](https://docs.astral.sh/uv/):

```bash
uv sync                     # runtime
uv sync --group pipeline    # + ruff/mypy/complexipy/pytest
```

## Uso

```bash
uv run degiro-calc Account.csv          # desde fuentes
./degiro-calc-linux-x86_64 Account.csv  # binario standalone
```

Opciones: `--no-tax` (omite estimación IRPF), `-v/--verbose` (traceback completo),
`--version`.

La salida usa colores y paneles de rich (verde G/P positivo, rojo negativo). Al redirigir
a archivo, rich emite texto plano automáticamente.

## Normativa aplicada

Ley 35/2006 del IRPF
([BOE-A-2006-20764](https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764)):

- **Art. 35.1.b** — gastos inherentes a la adquisición suman al coste.
- **Art. 35.2** — gastos satisfechos por el transmitente restan del valor de transmisión.
- **Art. 37.2** — valores homogéneos transmitidos por FIFO.
- **Art. 66** — tipos progresivos de la base imponible del ahorro (estimación de cuota).

## Limitaciones

- No cubre dividendos, intereses ni retenciones.
- No aplica la regla de los dos meses (recompra) de valores homogéneos.
- No gestiona splits ni operaciones corporativas complejas.
- La cuota IRPF es una **estimación aislada**: la real depende del conjunto de tu base
  del ahorro.
- Las comisiones de conectividad se reportan aparte, no se imputan al coste FIFO.
