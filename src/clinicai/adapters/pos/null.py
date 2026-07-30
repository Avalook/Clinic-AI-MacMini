"""The adapter used when no POS is connected — which is the normal case.

ADR-0010 keeps the integration optional. This adapter implements the port for
local composition, but the relay treats it as unavailable and dead-letters the
row. A no-op must never be reported as a successful external delivery.
"""

from __future__ import annotations

import structlog

from clinicai.ports.pos import PosCatalogItem, PosInvoice, PosStockMovement

logger = structlog.get_logger()


class NullPosAdapter:
    """Accepts everything, forwards nothing."""

    name = "none"

    async def push_invoice(self, invoice: PosInvoice) -> str | None:
        logger.debug(
            "pos_invoice_discarded",
            adapter=self.name,
            reference=invoice.clinic_reference,
        )
        return None

    async def void_invoice(self, clinic_reference: str) -> None:
        logger.debug(
            "pos_void_discarded", adapter=self.name, reference=clinic_reference
        )

    async def push_stock_movement(self, movement: PosStockMovement) -> str | None:
        logger.debug(
            "pos_stock_discarded",
            adapter=self.name,
            reference=movement.clinic_reference,
        )
        return None

    async def pull_catalog(self) -> list[PosCatalogItem]:
        return []
