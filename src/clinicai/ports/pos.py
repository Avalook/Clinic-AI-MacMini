"""The point-of-sale port (ADR-0010).

ClinicAI owns payment and inventory. A POS — KiotViet today, something else at
the next clinic — is a system we push to, never one we read the truth from.
This module is the whole contract between the two, and it is deliberately
small: three verbs and three plain dataclasses.

Business code depends on ``PosPort`` and nothing else. Concrete adapters live
under ``clinicai.adapters.pos`` and are chosen at run time, so no service ever
imports a vendor. ``src/tests/test_pos_port.py`` asserts that.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, runtime_checkable


class PosDeliveryError(RuntimeError):
    """The POS could not be told. Raised by adapters; the relay retries.

    ``retryable=False`` means retrying cannot help — the POS rejected the
    content, not the connection — so the relay dead-letters immediately instead
    of burning five attempts on the same answer.
    """

    def __init__(self, message: str, *, retryable: bool = True) -> None:
        super().__init__(message)
        self.retryable = retryable


@dataclass(frozen=True)
class PosInvoiceLine:
    """One billable line as ClinicAI recorded it."""

    code: str
    name: str
    quantity: float
    unit_price: float


@dataclass(frozen=True)
class PosInvoice:
    """A payment ClinicAI has already taken, described for the POS.

    ``clinic_reference`` is our id for it. An adapter must treat the same
    reference twice as the same invoice — the relay can retry after a timeout
    that in fact succeeded.
    """

    clinic_reference: str
    kind: str
    total_amount: float
    paid_at: datetime
    patient_reference: str | None = None
    lines: list[PosInvoiceLine] = field(default_factory=list)
    note: str | None = None


@dataclass(frozen=True)
class PosStockMovement:
    """A change in stock ClinicAI has already applied."""

    clinic_reference: str
    product_code: str
    quantity: float
    direction: str  # 'in' | 'out'
    occurred_at: datetime
    note: str | None = None


@dataclass(frozen=True)
class PosCatalogItem:
    """An item as the POS knows it, for reconciliation only."""

    code: str
    name: str
    unit_price: float | None = None
    unit: str | None = None


@runtime_checkable
class PosPort(Protocol):
    """What ClinicAI needs from any point-of-sale.

    Every method must be safe to call twice with the same ``clinic_reference``:
    the relay retries, and a timeout is indistinguishable from a failure.
    """

    name: str

    async def push_invoice(self, invoice: PosInvoice) -> str | None:
        """Record an invoice. Returns the POS's own id, if it gives one."""
        ...

    async def void_invoice(self, clinic_reference: str) -> None:
        """Void a previously pushed invoice."""
        ...

    async def push_stock_movement(self, movement: PosStockMovement) -> str | None:
        """Record a stock movement."""
        ...

    async def pull_catalog(self) -> list[PosCatalogItem]:
        """Read the POS catalogue — for RECONCILIATION REPORTS ONLY.

        Nothing returned here may be written into ClinicAI's own catalogue or
        ledger; the point of ADR-0010 is that the flow of truth is one-way.
        """
        ...
