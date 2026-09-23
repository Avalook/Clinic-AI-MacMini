"""Quyền theo capability: tài khoản là người, vai chỉ là preset."""

from clinicai.permissions.can import can, doi_quyen, quyen_hieu_luc
from clinicai.permissions.catalogue import KHOI, PRESET, QUYEN, quyen_cua_khoi

__all__ = [
    "KHOI",
    "PRESET",
    "QUYEN",
    "can",
    "doi_quyen",
    "quyen_cua_khoi",
    "quyen_hieu_luc",
]
