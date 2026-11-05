"""Người "gây ra" một tệp kết quả không phải nhân viên — máy quét Drive (chặng 4).

`TepKetQuaService.tai_len` nhận `identity` là nhân viên đang bấm. Máy quét Drive chạy
trong tiến trình nền, không có ai bấm: nó đưa `MayQuet` vào chỗ đó. Cột người tải để
NULL (`tep_ket_qua_nguon_hop_le` ép: NULL thì nguồn phải là DRIVE), sự kiện ghi
`actor_type = SYSTEM`. Không tạo nhân viên giả trong bảng staff.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class MayQuet:
    clinic_id: str
    staff_id: None = None

    def co_vai(self, _vai: Iterable[object]) -> bool:
        """Máy không có vai nào — không tự "cho phép gửi" như bác sĩ tải."""
        return False
