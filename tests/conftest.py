# Standard libraries
from datetime import date
from decimal import Decimal

# Own modules
from degiro_calculator import Operacion, TipoOperacion


def _make(  # noqa: PLR0913 - builder de tests
    tipo: TipoOperacion,
    isin: str,
    cantidad: int,
    contravalor: str,
    comision: str,
    dia: int,
) -> Operacion:
    return Operacion(
        fecha=date(2026, 1, dia),
        hora="10:00",
        isin=isin,
        producto="TEST",
        tipo=tipo,
        cantidad=cantidad,
        contravalor_eur=Decimal(contravalor),
        comision_eur=Decimal(comision),
    )


def make_compra(
    isin: str, cantidad: int, contravalor: str, comision: str, dia: int = 1
) -> Operacion:
    """Construye una ``Operacion`` de compra para tests (fecha 2026-01-``dia``)."""

    return _make(TipoOperacion.COMPRA, isin, cantidad, contravalor, comision, dia)


def make_venta(
    isin: str, cantidad: int, contravalor: str, comision: str, dia: int = 1
) -> Operacion:
    """Construye una ``Operacion`` de venta para tests (fecha 2026-01-``dia``)."""

    return _make(TipoOperacion.VENTA, isin, cantidad, contravalor, comision, dia)
