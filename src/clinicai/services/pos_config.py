"""Which POS a clinic uses, and how to reach it (ADR-0010).

Two levels, on purpose:

* ``POS_ADAPTER`` in the environment is the deployment-wide default, and is the
  switch that lets the whole integration be turned off in one place.
* ``clinic.settings -> 'pos'`` overrides it per tenant, because a multi-tenant
  product cannot assume every clinic uses the same till.

Credentials live in ``clinic.settings``, never in code and never in a column
that ends up in a client-readable view.
"""

from __future__ import annotations

import os
from typing import Any

import structlog

from clinicai.adapters.pos.kiotviet import KiotVietPosAdapter
from clinicai.adapters.pos.null import NullPosAdapter
from clinicai.ports.pos import PosPort

logger = structlog.get_logger()

DEFAULT_ADAPTER = "none"


def configured_adapter_name(settings: dict[str, Any] | None = None) -> str:
    """Adapter for this clinic: its own setting, else the deployment default."""
    per_clinic = ((settings or {}).get("pos") or {}).get("adapter")
    if isinstance(per_clinic, str) and per_clinic.strip():
        return per_clinic.strip().lower()
    return os.environ.get("POS_ADAPTER", DEFAULT_ADAPTER).strip().lower()


def build_adapter(settings: dict[str, Any] | None = None) -> PosPort:
    """Construct the adapter for one clinic.

    Unknown names and missing credentials return the null adapter rather than
    crashing the payment path. The relay recognizes it and dead-letters the
    push; it must never claim an external POS accepted data that was discarded.
    """
    name = configured_adapter_name(settings)

    if name in ("none", "null", ""):
        return NullPosAdapter()

    if name == "kiotviet":
        pos = (settings or {}).get("pos") or {}
        missing = [
            key
            for key in ("retailer", "client_id", "client_secret")
            if not pos.get(key)
        ]
        if missing:
            logger.error(
                "pos_adapter_misconfigured",
                adapter=name,
                missing=missing,
                fallback="none",
            )
            return NullPosAdapter()
        return KiotVietPosAdapter(
            retailer=str(pos["retailer"]),
            client_id=str(pos["client_id"]),
            client_secret=str(pos["client_secret"]),
            branch_id=str(pos["branch_id"]) if pos.get("branch_id") else None,
        )

    logger.error("pos_adapter_unknown", adapter=name, fallback="none")
    return NullPosAdapter()
