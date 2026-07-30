"""KiotViet adapter — the door ADR-0010 asked to leave open.

Deliberately NOT a speculative HTTP client. Nobody here has KiotViet
credentials or a sandbox, and an unverified client written from documentation
is worse than none: it looks finished, it is wired into the relay, and the day
someone enables it the clinic finds out in front of patients which endpoints
were guessed wrong.

So this adapter carries the parts that are knowable now — configuration,
naming, and the shape of the mapping — and refuses loudly rather than
pretending. Turning it on without finishing it dead-letters the outbox row with
a clear reason instead of silently dropping money.

To finish it you need, per clinic:
  * ``retailer`` (the shop name in the KiotViet URL),
  * ``client_id`` / ``client_secret`` for the public API,
  * a branch id, and the mapping from ClinicAI ``service_code`` to KiotViet
    product codes.

Put them in ``clinic.settings -> 'pos'`` (see ``clinicai.services.pos_config``),
never in code, because they differ per tenant.
"""

from __future__ import annotations

import structlog

from clinicai.ports.pos import (
    PosCatalogItem,
    PosDeliveryError,
    PosInvoice,
    PosStockMovement,
)

logger = structlog.get_logger()

_UNFINISHED = (
    "Adapter KiotViet chưa hoàn thiện: cần retailer + client_id/client_secret + "
    "branch_id và bảng ánh xạ mã dịch vụ. Xem docs/adr/0010."
)


class KiotVietPosAdapter:
    """Configured but not yet implemented. Fails closed, never silently."""

    name = "kiotviet"

    def __init__(
        self,
        *,
        retailer: str,
        client_id: str,
        client_secret: str,
        branch_id: str | None = None,
    ) -> None:
        self.retailer = retailer
        self._client_id = client_id
        self._client_secret = client_secret
        self.branch_id = branch_id

    def _refuse(self, action: str, reference: str) -> PosDeliveryError:
        logger.error(
            "pos_adapter_unfinished",
            adapter=self.name,
            action=action,
            reference=reference,
            retailer=self.retailer,
        )
        # Not retryable: five more attempts will fail identically. Straight to
        # the dead-letter state, where somebody will see it.
        return PosDeliveryError(_UNFINISHED, retryable=False)

    async def push_invoice(self, invoice: PosInvoice) -> str | None:
        raise self._refuse("push_invoice", invoice.clinic_reference)

    async def void_invoice(self, clinic_reference: str) -> None:
        raise self._refuse("void_invoice", clinic_reference)

    async def push_stock_movement(self, movement: PosStockMovement) -> str | None:
        raise self._refuse("push_stock_movement", movement.clinic_reference)

    async def pull_catalog(self) -> list[PosCatalogItem]:
        raise self._refuse("pull_catalog", "-")
