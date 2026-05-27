# Standard libraries
from collections import deque
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum


class TipoOperacion(StrEnum):
    """
    Tipo de operación bursátil reconocido por el parser.

    Hereda de ``str`` para mantener compatibilidad con comparaciones directas
    contra literales ``"Compra"``/``"Venta"`` en renderizados existentes.
    """

    COMPRA = "Compra"
    VENTA = "Venta"


@dataclass(frozen=True)
class Operacion:
    """
    Operación normalizada de compra o venta en EUR reales del broker.

    Attributes:
        fecha: Fecha de la operación.
        hora: Hora en formato ``HH:MM``.
        isin: Identificador ISIN del instrumento.
        producto: Nombre descriptivo del producto.
        tipo: ``TipoOperacion.COMPRA`` o ``TipoOperacion.VENTA``.
        cantidad: Número de unidades.
        contravalor_eur: Contravalor en EUR (signo incluido).
        comision_eur: Comisiones imputables a la operación (signo incluido).
    """

    fecha: date
    hora: str
    isin: str
    producto: str
    tipo: TipoOperacion
    cantidad: int
    contravalor_eur: Decimal
    comision_eur: Decimal


@dataclass(frozen=True)
class Venta:
    """
    Venta casada contra lotes FIFO con coste de adquisición imputado.

    Attributes:
        fecha: Fecha de la venta.
        isin: Identificador ISIN del instrumento.
        producto: Nombre descriptivo del producto.
        cantidad: Unidades vendidas.
        coste_adq: Coste de adquisición FIFO imputado en EUR.
        valor_trans: Valor de transmisión neto de comisiones en EUR.
        gp: Ganancia o pérdida patrimonial (``valor_trans - coste_adq``).
    """

    fecha: date
    isin: str
    producto: str
    cantidad: int
    coste_adq: Decimal
    valor_trans: Decimal
    gp: Decimal


@dataclass
class Lote:
    """
    Lote de compra pendiente de consumir por FIFO.

    Es mutable: la cantidad se decrementa a medida que las ventas lo consumen.

    Attributes:
        cantidad: Unidades pendientes en el lote.
        coste_unit: Coste unitario en EUR (incluye la comisión de compra).
        fecha: Fecha de la compra original.
    """

    cantidad: int
    coste_unit: Decimal
    fecha: date


@dataclass(frozen=True)
class TramoCuota:
    """
    Tramo de la base del ahorro (art. 66 LIRPF) con la base y cuota aplicadas.

    Attributes:
        desde: Límite inferior del tramo en EUR.
        hasta: Límite superior del tramo en EUR, o ``None`` si es el último.
        tipo: Tipo impositivo aplicado (p. ej. ``0.19``).
        base: Base imponible cubierta en este tramo en EUR.
        cuota: Cuota resultante (``base * tipo``) en EUR.
    """

    desde: Decimal
    hasta: Decimal | None
    tipo: Decimal
    base: Decimal
    cuota: Decimal


@dataclass(frozen=True)
class InformeData:
    """
    Agregados precomputados del informe, desacoplados del formato de salida.

    Contiene toda la información necesaria para renderizar el informe en
    cualquier formato (stdout, JSON, Excel) sin recalcular.

    Attributes:
        ventas: Ventas casadas por FIFO.
        total_gp: Suma de ganancia/pérdida patrimonial del ejercicio.
        cuota_irpf: Desglose por tramos o ``None`` si ``incluir_tax`` es ``False``
            o si ``total_gp <= 0``.
        comisiones_conectividad: Total absoluto de comisiones de conectividad.
        rentabilidad_neta: Rentabilidad tras impuestos y gastos de custodia, o
            ``None`` si no procede (``incluir_tax`` ``False`` o ``total_gp <= 0``).
        lotes_pendientes: Cartera abierta tras aplicar FIFO.
        incluir_tax: Indica si el informe debe renderizar el bloque IRPF.
    """

    ventas: list[Venta]
    total_gp: Decimal
    cuota_irpf: list[TramoCuota] | None
    comisiones_conectividad: Decimal
    rentabilidad_neta: Decimal | None
    lotes_pendientes: dict[str, deque[Lote]]
    incluir_tax: bool
