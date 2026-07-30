"""Tests for the POS port, its adapters and the boundary around them (W7).

ADR-0010's whole claim is that ClinicAI does not depend on a POS. That claim is
only true if business code cannot reach a vendor, so the last test here is the
one that matters most: it fails if any service imports an adapter.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

import pytest

from clinicai.adapters.pos.kiotviet import KiotVietPosAdapter
from clinicai.adapters.pos.null import NullPosAdapter
from clinicai.ports.pos import PosDeliveryError, PosInvoice, PosPort, PosStockMovement
from clinicai.services.pos_config import build_adapter, configured_adapter_name

SERVICES = Path(__file__).resolve().parents[1] / "clinicai" / "services"


def _invoice() -> PosInvoice:
    return PosInvoice(
        clinic_reference="pay-1",
        kind="dich_vu",
        total_amount=250_000,
        paid_at=datetime.now(timezone.utc),
    )


class TestNullAdapter:
    def test_satisfies_the_port(self) -> None:
        assert isinstance(NullPosAdapter(), PosPort)

    def test_accepts_everything_and_forwards_nothing(self) -> None:
        adapter = NullPosAdapter()
        assert asyncio.run(adapter.push_invoice(_invoice())) is None
        assert (
            asyncio.run(
                adapter.push_stock_movement(
                    PosStockMovement(
                        clinic_reference="mv-1",
                        product_code="P1",
                        quantity=2,
                        direction="out",
                        occurred_at=datetime.now(timezone.utc),
                    )
                )
            )
            is None
        )
        assert asyncio.run(adapter.pull_catalog()) == []


class TestKiotVietAdapter:
    def test_satisfies_the_port(self) -> None:
        adapter = KiotVietPosAdapter(retailer="r", client_id="i", client_secret="s")
        assert isinstance(adapter, PosPort)

    def test_refuses_loudly_rather_than_guessing(self) -> None:
        # An unfinished integration must fail, not appear to succeed. Money has
        # already changed hands by the time this is called.
        adapter = KiotVietPosAdapter(retailer="r", client_id="i", client_secret="s")
        with pytest.raises(PosDeliveryError) as exc:
            asyncio.run(adapter.push_invoice(_invoice()))
        # Not retryable: the next four attempts would fail identically, so the
        # relay should dead-letter it where somebody will see it.
        assert exc.value.retryable is False


class TestConfiguration:
    def test_default_is_no_pos(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("POS_ADAPTER", raising=False)
        assert configured_adapter_name() == "none"
        assert isinstance(build_adapter(), NullPosAdapter)

    def test_clinic_setting_beats_the_deployment_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A multi-tenant product cannot assume every clinic uses the same till.
        monkeypatch.setenv("POS_ADAPTER", "none")
        settings = {
            "pos": {
                "adapter": "kiotviet",
                "retailer": "dr4women",
                "client_id": "id",
                "client_secret": "secret",
            }
        }
        assert configured_adapter_name(settings) == "kiotviet"
        assert isinstance(build_adapter(settings), KiotVietPosAdapter)

    def test_missing_credentials_fall_back_instead_of_crashing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A typo in configuration must not stop the clinic taking money.
        monkeypatch.setenv("POS_ADAPTER", "kiotviet")
        assert isinstance(
            build_adapter({"pos": {"retailer": "only-this"}}), NullPosAdapter
        )

    def test_unknown_adapter_falls_back(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("POS_ADAPTER", "square")
        assert isinstance(build_adapter(), NullPosAdapter)


class TestBoundary:
    def test_no_service_imports_a_vendor(self) -> None:
        # The one test that makes ADR-0010 true rather than aspirational.
        # pos_relay is the seam and is allowed; nothing else may name an adapter.
        offenders = []
        for path in SERVICES.rglob("*.py"):
            if path.name in ("pos_relay.py", "pos_config.py"):
                continue
            if "clinicai.adapters" in path.read_text():
                offenders.append(path.name)
        assert offenders == [], (
            "business services must depend on ports.pos, never on an adapter: "
            f"{offenders}"
        )

    def test_payment_service_only_touches_the_outbox(self) -> None:
        text = (SERVICES / "payment_service.py").read_text()
        assert "pos_outbox" in text, "the payment path must queue the push"
        assert "adapters" not in text
        assert "kiotviet" not in text.lower()
