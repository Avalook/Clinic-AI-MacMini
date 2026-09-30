"""Đưa một tài khoản thử về GÓI LEGO CŨ của vai (trước mở full lego 30/09/2026).

Từ migration 20260930100000 mọi tài khoản nội bộ mới có gần đủ mọi khối, nên bài
kiểm "người KHÔNG có lego X thì bị chặn" phải tự dựng người ấy: quản lý thu bớt
lego trên /phan-quyen là về đúng tình huống này. Hàm này thu (revoke, có vết)
mọi dòng cấp phạm vi toàn phòng khám có khối nằm NGOÀI gói mẫu cũ của vai
(`catalogue.PRESET_TRUOC_MO_FULL`). Quyền theo lịch (`v_quyen_thuc_te`) không bị
đụng — bài kiểm lịch vẫn xếp ca như cũ.
"""

from __future__ import annotations

from typing import Any

from clinicai.api.identity import StaffIdentity
from clinicai.permissions import cache
from clinicai.permissions.catalogue import PRESET_TRUOC_MO_FULL


async def ve_goi_mau_cu(pool_hoac_conn: Any, *ai: StaffIdentity) -> None:
    for nguoi in ai:
        giu = list(PRESET_TRUOC_MO_FULL.get(nguoi.vai_goc.value, ()))
        await pool_hoac_conn.execute(
            "UPDATE capability_grant g SET revoked_at = now(), revoked_by = g.staff_id"
            "  FROM capability c"
            " WHERE c.ma = g.capability AND g.clinic_id = $1::uuid"
            "   AND g.staff_id = $2::uuid AND g.revoked_at IS NULL"
            "   AND g.scope_type = 'CLINIC' AND c.work_pack <> ALL($3::text[])",
            nguoi.clinic_id,
            nguoi.staff_id,
            giu,
        )
        cache.quen(nguoi.clinic_id, nguoi.staff_id)


__all__ = ["ve_goi_mau_cu"]
