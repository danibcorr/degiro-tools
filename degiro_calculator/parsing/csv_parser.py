# Standard libraries
import csv
import re
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

# Own modules
from ..domain.models import Operacion, TipoOperacion
from .columns import (
    DESCRIPCION_COL,
    DIVISA_COL,
    FECHA_COL,
    HORA_COL,
    ID_ORDEN_COL,
    ISIN_COL,
    VARIACION_COL,
)

OPERATION_REGEX = re.compile(r"^(Compra|Venta)\s+(\d+)\s+.*@([\d.,]+)\s+\w+")
FEE_DESCRIPTIONS: tuple[str, ...] = (
    "Costes de transacción",
    "Comisión",
    "Tasa",
    "Impuesto",
    "Spanish Transaction Tax",
    "Transaction Tax",
)


def to_decimal(texto: str) -> Decimal:
    """
    Convierte un importe en formato europeo ('1.234,56') a Decimal.

    Args:
        texto: Cadena con el importe a convertir. Vacía si no aplica.

    Returns:
        Valor Decimal equivalente, o ``Decimal(0)`` si la cadena está vacía.
    """

    return Decimal(texto.replace(".", "").replace(",", ".")) if texto else Decimal(0)


def parse_date(texto: str) -> date:
    """
    Parsea fechas en formato ``dd-mm-yyyy`` o ``dd-mm-yy``.

    Args:
        texto: Cadena con la fecha a parsear.

    Returns:
        Objeto ``date`` correspondiente.

    Raises:
        ValueError: Si la cadena no coincide con ninguno de los formatos admitidos.
    """

    for fmt in ("%d-%m-%Y", "%d-%m-%y"):
        try:
            return datetime.strptime(texto, fmt).date()

        except ValueError:
            continue

    raise ValueError(f"Fecha no reconocida: {texto}")


def group_key(row: list[str]) -> object | None:
    """
    Devuelve la clave de agrupación de la fila o ``None`` si debe ignorarse.

    Usa el ID Orden si existe; si no, agrupa por ``(fecha, hora, ISIN)``.

    Args:
        row: Fila bruta del CSV como lista de strings.

    Returns:
        Clave de agrupación (ID Orden o tupla) o ``None`` si la fila se descarta.
    """

    id_orden = row[ID_ORDEN_COL] if len(row) > ID_ORDEN_COL else ""
    if id_orden:
        return id_orden

    isin = row[ISIN_COL]
    if isin:
        return (row[FECHA_COL], row[HORA_COL], isin)

    return None


def read_operation_groups(
    path: Path,
) -> tuple[dict[object, list[dict[str, str]]], Decimal]:
    """
    Agrupa las filas del CSV por operación y suma las comisiones de conectividad.

    Args:
        path: Ruta al fichero CSV exportado desde Degiro.

    Returns:
        Tupla con:
            - Diccionario clave → lista de filas (dicts con campos normalizados).
            - Total absoluto de comisiones de conectividad con el mercado (EUR).
    """

    groups: dict[object, list[dict[str, str]]] = defaultdict(list)
    comisiones_conectividad = Decimal(0)

    with path.open(encoding="utf-8-sig", newline="") as csv_file:
        for row in csv.reader(csv_file):
            if not row or row[FECHA_COL] == "Fecha":
                continue

            descripcion = row[DESCRIPCION_COL]
            if "Comisión de conectividad con el mercado" in descripcion:
                comisiones_conectividad += abs(to_decimal(row[VARIACION_COL]))
                continue

            key = group_key(row)
            if key is None:
                continue

            groups[key].append(
                {
                    "fecha": row[FECHA_COL],
                    "hora": row[HORA_COL],
                    "isin": row[ISIN_COL],
                    "desc": descripcion,
                    "var": row[VARIACION_COL],
                    "div": row[DIVISA_COL],
                }
            )

    return groups, comisiones_conectividad


def resolve_eur_amount(header: dict[str, str], rows: list[dict[str, str]]) -> Decimal:
    """
    Obtiene el contravalor EUR real de una operación.

    Prioriza la fila ``Cambio de Divisa`` en EUR; si no existe y el header ya está
    en EUR, usa su variación directamente.

    Args:
        header: Fila que contiene la descripción de la operación.
        rows: Filas del grupo de la operación.

    Returns:
        Contravalor en EUR (signo incluido) como ``Decimal``.

    Raises:
        ValueError: Si la operación no dispone de contravalor EUR reconocible.
    """

    cambio_eur = next(
        (r for r in rows if "Cambio de Divisa" in r["desc"] and r["div"] == "EUR"),
        None,
    )
    if cambio_eur is not None:
        return to_decimal(cambio_eur["var"])

    if header["div"] == "EUR":
        return to_decimal(header["var"])

    raise ValueError(
        f"Sin contravalor EUR para operación {header['fecha']} "
        f"{header['hora']} {header['isin']}"
    )


def build_operacion_from_group(rows: list[dict[str, str]]) -> list[Operacion]:
    """
    Construye una o más ``Operacion`` a partir de las filas agrupadas.

    Cuando una orden tiene ejecuciones parciales (varias filas de compra/venta
    con el mismo ID Orden), genera una operación por cada ejecución y reparte
    las comisiones proporcionalmente por cantidad de acciones.

    Args:
        rows: Filas del CSV pertenecientes a una misma operación.

    Returns:
        Lista de operaciones normalizadas (vacía si el grupo no contiene filas
        de compra/venta reconocibles).

    Raises:
        ValueError: Si no puede resolverse el contravalor EUR o la fecha.
    """

    headers = [r for r in rows if OPERATION_REGEX.match(r["desc"])]
    if not headers:
        return []

    comision_total = sum(
        (
            to_decimal(r["var"])
            for r in rows
            if any(k in r["desc"] for k in FEE_DESCRIPTIONS)
        ),
        Decimal(0),
    )

    if len(headers) == 1:
        header = headers[0]
        match = OPERATION_REGEX.match(header["desc"])
        assert match is not None
        contravalor = resolve_eur_amount(header, rows)
        return [
            Operacion(
                fecha=parse_date(header["fecha"]),
                hora=header["hora"],
                isin=header["isin"],
                producto=header["desc"].split("@")[0].split(" ", 2)[2].strip(),
                tipo=TipoOperacion(match.group(1)),
                cantidad=int(match.group(2)),
                contravalor_eur=contravalor,
                comision_eur=comision_total,
            )
        ]

    # Ejecuciones parciales: repartir comisiones y cambio de divisa por cantidad
    total_qty = sum(
        int(OPERATION_REGEX.match(h["desc"]).group(2))  # type: ignore[union-attr]
        for h in headers
    )

    # Cambio de divisa del grupo (si existe, se reparte proporcionalmente)
    cambio_eur_total = next(
        (
            to_decimal(r["var"])
            for r in rows
            if "Cambio de Divisa" in r["desc"] and r["div"] == "EUR"
        ),
        None,
    )

    ops: list[Operacion] = []
    for header in headers:
        match = OPERATION_REGEX.match(header["desc"])
        assert match is not None
        qty = int(match.group(2))
        ratio = Decimal(qty) / Decimal(total_qty)

        if cambio_eur_total is not None:
            contravalor = cambio_eur_total * ratio
        elif header["div"] == "EUR":
            contravalor = to_decimal(header["var"])
        else:
            raise ValueError(
                f"Sin contravalor EUR para operación {header['fecha']} "
                f"{header['hora']} {header['isin']}"
            )

        ops.append(
            Operacion(
                fecha=parse_date(header["fecha"]),
                hora=header["hora"],
                isin=header["isin"],
                producto=header["desc"].split("@")[0].split(" ", 2)[2].strip(),
                tipo=TipoOperacion(match.group(1)),
                cantidad=qty,
                contravalor_eur=contravalor,
                comision_eur=comision_total * ratio,
            )
        )

    return ops


def parse_csv(path: Path) -> tuple[list[Operacion], Decimal]:
    """
    Parsea un extracto CSV de Degiro.

    Agrupa filas por ID Orden (o por (Fecha, Hora, ISIN) si no hay ID) para obtener
    el contravalor EUR real del broker (fila 'Cambio de Divisa' en EUR) y las
    comisiones asociadas.

    Args:
        path: Ruta al fichero CSV exportado desde Degiro (Estado de cuenta).

    Returns:
        Tupla con:
            - Lista de operaciones de compra/venta normalizadas, ordenadas por
              fecha y hora.
            - Total (absoluto) de comisiones de conectividad con el mercado (en EUR).

    Raises:
        ValueError: Si una operación no tiene contravalor EUR o la fecha no es válida.
    """

    groups, comisiones_conectividad = read_operation_groups(path)

    ops: list[Operacion] = []
    for rows in groups.values():
        ops.extend(build_operacion_from_group(rows))

    ops.sort(key=lambda o: (o.fecha, o.hora))
    return ops, comisiones_conectividad
