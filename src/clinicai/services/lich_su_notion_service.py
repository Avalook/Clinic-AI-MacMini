"""Lịch sử khám cũ nhập từ Notion (05/10/2026) — chỉ ĐỌC.

Dữ liệu nằm ở schema ``lich_su_notion`` (migration 20261005100000), nạp bằng
``nhap_lich_su_notion.py``. Màn Danh sách bệnh nhân đọc qua đây.

Hai tầng quyền:
  * thấy DANH SÁCH lượt cũ (ngày, loại khám, bác sĩ) = cửa của màn Danh sách
    bệnh nhân (``patient.list.view``, router gác);
  * thấy NỘI DUNG (khám – tư vấn, chẩn đoán, kết quả, thuốc, tệp) = đúng quyền
    xem lịch sử phiếu khám (``kiem_quyen_core(..., "xem_lich_su")``).

Mốc thời gian chỉ là NGÀY (Notion không có check-in/check-out). "Lần thứ N" tính
trên dữ liệu có từ 04/2025; cùng ngày nhiều lượt thì không rõ thứ tự.
"""

from __future__ import annotations

import json
from typing import Any

import asyncpg

from clinicai.api.exceptions import NotFoundError
from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import SafetyGateError

GHI_CHU_CO_DINH = (
    "Hồ sơ khám trước khi dùng hệ thống này. Chỉ có NGÀY khám, không có giờ "
    'vào/ra. "Lần thứ N" tính trên dữ liệu có từ 04/2025 — trước đó không '
    "có dữ liệu."
)


async def co_quyen_noi_dung(conn: asyncpg.Connection, identity: StaffIdentity) -> bool:
    """Người này đọc được NỘI DUNG khám không — cùng hàm quyền phiếu khám."""
    from clinicai.services.phieu_kham_service import kiem_quyen_core

    try:
        await kiem_quyen_core(conn, identity, "xem_lich_su")
    except SafetyGateError:
        return False
    return True


def _json(v: Any) -> Any:
    return json.loads(v) if isinstance(v, str) else v


async def lich_su(
    pool: asyncpg.Pool, *, identity: StaffIdentity, clinic_patient_id: str
) -> dict[str, Any]:
    """Tóm tắt lịch sử Notion của một khách: người + các lượt + lịch hẹn."""
    async with pool.acquire() as conn:
        noi_dung = await co_quyen_noi_dung(conn, identity)
        nguoi = await conn.fetchrow(
            """
            SELECT ho_so_notion, nguon_ten, ghi_chu_lan_dau, link_drive,
                   notion_url, cach_ghep
              FROM lich_su_notion.nguoi
             WHERE clinic_id = $1::uuid AND clinic_patient_id = $2::uuid
             ORDER BY nguoi_key LIMIT 1
            """,
            identity.clinic_id,
            clinic_patient_id,
        )
        if nguoi is None:
            return {"co_lich_su": False}
        luot = await conn.fetch(
            """
            SELECT l.notion_id::text AS id, l.ma, l.ngay_kham, l.nguon_ngay, l.lan_thu,
                   l.thu_tu_khong_chac, l.loai_kham_goc, st.name AS loai_kham,
                   l.bac_si_goc, s.full_name AS bac_si, l.co_so_goc,
                   CASE WHEN $3 THEN l.chan_doan END AS chan_doan,
                   (SELECT count(*) FROM lich_su_notion.dich_vu d
                     WHERE d.luot_kham_id = l.notion_id) AS so_dich_vu,
                   (SELECT count(*) FROM lich_su_notion.xet_nghiem x
                     WHERE x.luot_kham_id = l.notion_id) AS so_xet_nghiem,
                   (SELECT count(*) FROM lich_su_notion.ke_thuoc t
                     WHERE t.luot_kham_id = l.notion_id) AS so_thuoc,
                   (SELECT count(*) FROM lich_su_notion.bat_thuong b
                     WHERE b.luot_kham_id = l.notion_id) AS so_bat_thuong
              FROM lich_su_notion.luot_kham l
              LEFT JOIN public.service_type st ON st.id = l.service_type_id
              LEFT JOIN public.staff s ON s.id = l.staff_id
             WHERE l.clinic_id = $1::uuid AND l.clinic_patient_id = $2::uuid
               -- Lượt đã chuyển thành lượt thật (06/10) hiện ở "Lịch sử các lượt
               -- khám"; ở đây chỉ còn lượt trùng ngày với lượt có sẵn trên hệ thống.
               AND NOT EXISTS (SELECT 1 FROM lich_su_notion.luot_that t
                                WHERE t.notion_id = l.notion_id
                                  AND t.visit_id IS NOT NULL)
             ORDER BY l.ngay_kham DESC, l.lan_thu DESC NULLS LAST
            """,
            identity.clinic_id,
            clinic_patient_id,
            noi_dung,
        )
        da_chuyen = await conn.fetchval(
            """
            SELECT count(DISTINCT t.visit_id) FROM lich_su_notion.luot_that t
              JOIN lich_su_notion.luot_kham l ON l.notion_id = t.notion_id
             WHERE l.clinic_id = $1::uuid AND l.clinic_patient_id = $2::uuid
               AND t.visit_id IS NOT NULL
            """,
            identity.clinic_id,
            clinic_patient_id,
        )
        hen = await conn.fetch(
            """
            SELECT ma, ngay_hen, gio_hen, loai_kham_goc, bac_si_goc,
                   tinh_trang_den, tinh_trang_cskh, trang_thai
              FROM lich_su_notion.lich_hen
             WHERE clinic_id = $1::uuid AND clinic_patient_id = $2::uuid
             ORDER BY ngay_hen DESC NULLS LAST, gio_hen DESC NULLS LAST
            """,
            identity.clinic_id,
            clinic_patient_id,
        )
    return {
        "co_lich_su": True,
        "co_noi_dung": noi_dung,
        "so_luot_da_chuyen": da_chuyen or 0,
        "ghi_chu_co_dinh": GHI_CHU_CO_DINH,
        "nguoi": {
            "ho_so_notion": list(nguoi["ho_so_notion"] or []),
            "nguon_ten": nguoi["nguon_ten"],
            "ghi_chu_lan_dau": nguoi["ghi_chu_lan_dau"],
            "link_drive": nguoi["link_drive"] if noi_dung else None,
            "notion_url": nguoi["notion_url"],
            "ghep_vao_ho_so_co_san": nguoi["cach_ghep"] == "ghep_sdt_ten",
        },
        "luot": [
            {
                **dict(r),
                "ngay_kham": r["ngay_kham"].isoformat(),
            }
            for r in luot
        ],
        "lich_hen": [
            {
                **dict(r),
                "ngay_hen": r["ngay_hen"].isoformat() if r["ngay_hen"] else None,
                "gio_hen": r["gio_hen"].strftime("%H:%M") if r["gio_hen"] else None,
            }
            for r in hen
        ],
    }


async def chi_tiet_luot(
    pool: asyncpg.Pool, *, identity: StaffIdentity, luot_id: str
) -> dict[str, Any]:
    """Toàn bộ một lượt cũ: khám – tư vấn, dịch vụ + kết quả, xét nghiệm, thuốc."""
    async with pool.acquire() as conn:
        if not await co_quyen_noi_dung(conn, identity):
            raise SafetyGateError("Bạn không có quyền xem nội dung phiếu khám.")
        luot = await conn.fetchrow(
            """
            SELECT l.notion_id::text AS id,
                   l.clinic_patient_id::text AS clinic_patient_id,
                   l.ma, l.ngay_kham, l.nguon_ngay, l.lan_thu, l.thu_tu_khong_chac,
                   l.loai_kham_goc, st.name AS loai_kham, l.bac_si_goc,
                   s.full_name AS bac_si,
                   l.co_so_goc, l.kham_tu_van, l.chan_doan, l.ghi_chu_vinh_vien,
                   l.tinh_trang_goc, l.notion_url
              FROM lich_su_notion.luot_kham l
              LEFT JOIN public.service_type st ON st.id = l.service_type_id
              LEFT JOIN public.staff s ON s.id = l.staff_id
             WHERE l.clinic_id = $1::uuid AND l.notion_id = $2::uuid
            """,
            identity.clinic_id,
            luot_id,
        )
        if luot is None:
            raise NotFoundError("Không tìm thấy lượt khám cũ này.")
        dv = await conn.fetch(
            """
            SELECT d.notion_id::text AS id, d.ma, d.ten_goc, sp.name AS ten_bang_gia,
                   d.nguoi_lam, d.ngay, d.tinh_trang_goc,
                   coalesce((SELECT jsonb_agg(jsonb_build_object(
                        'ma', k.ma, 'tieu_de', k.tieu_de, 'mo_ta', k.mo_ta,
                        'ket_luan', k.ket_luan, 'bac_si_ky', k.bac_si_ky,
                        'ghi_chu', k.ghi_chu, 'ghi_de_chan_doan', k.ghi_de_chan_doan,
                        'da_co_noi_dung', k.da_co_noi_dung,
                        'link_drive_cu', k.link_drive_cu) ORDER BY k.ma)
                      FROM lich_su_notion.ket_qua k
                     WHERE k.dich_vu_id = d.notion_id), '[]') AS ket_qua
              FROM lich_su_notion.dich_vu d
              LEFT JOIN public.service_price sp
                ON sp.clinic_id = d.clinic_id AND sp.service_code = d.service_code
             WHERE d.luot_kham_id = $1::uuid
             ORDER BY d.ma
            """,
            luot_id,
        )
        kq_le = await conn.fetch(
            """
            SELECT ma, tieu_de, mo_ta, ket_luan, bac_si_ky, ghi_chu,
                   da_co_noi_dung, link_drive_cu
              FROM lich_su_notion.ket_qua
             WHERE luot_kham_id = $1::uuid AND dich_vu_id IS NULL
             ORDER BY ma
            """,
            luot_id,
        )
        xn = await conn.fetch(
            """
            SELECT notion_id::text AS id, ma, noi_lam, phan_loai, ket_qua,
                   ket_qua_ai,
                   tro_ly_ghi_chu, ghi_chu_vinh_vien, tep, tinh_trang_goc, ngay
              FROM lich_su_notion.xet_nghiem
             WHERE luot_kham_id = $1::uuid
             ORDER BY ma
            """,
            luot_id,
        )
        thuoc = await conn.fetch(
            """
            SELECT ma, ten_thuoc, huong_dan, so_luong, ghi_chu_so_luong, luu_y
              FROM lich_su_notion.ke_thuoc
             WHERE luot_kham_id = $1::uuid
             ORDER BY ma
            """,
            luot_id,
        )
        bt = await conn.fetch(
            """
            SELECT loai, muc, chi_tiet, notion_url, trang_thai
              FROM lich_su_notion.bat_thuong
             WHERE luot_kham_id = $1::uuid
             ORDER BY id
            """,
            luot_id,
        )

    def tep(v: Any) -> list[dict[str, Any]]:
        # Chỉ trả TÊN + vị trí trong danh sách; đường dẫn kho không ra trình duyệt.
        return [
            {"i": i, "ten": t.get("ten"), "co_tep": bool(t.get("khoa"))}
            for i, t in enumerate(_json(v) or [])
        ]

    return {
        **{k: v for k, v in dict(luot).items() if k != "ngay_kham"},
        "ngay_kham": luot["ngay_kham"].isoformat(),
        "dich_vu": [
            {
                **dict(r),
                "ngay": r["ngay"].isoformat() if r["ngay"] else None,
                "ket_qua": _json(r["ket_qua"]),
            }
            for r in dv
        ],
        "ket_qua_khong_gan_dich_vu": [dict(r) for r in kq_le],
        "xet_nghiem": [
            {
                **dict(r),
                "tep": tep(r["tep"]),
                "ngay": r["ngay"].isoformat() if r["ngay"] else None,
            }
            for r in xn
        ],
        "thuoc": [dict(r) for r in thuoc],
        "bat_thuong": [dict(r) for r in bt],
    }


async def khoa_tep_xet_nghiem(
    pool: asyncpg.Pool, *, identity: StaffIdentity, xn_id: str, i: int
) -> tuple[str, str]:
    """(khoá kho, tên tệp) của tệp thứ ``i`` của một xét nghiệm cũ — sau khi
    chứng minh quyền và đúng phòng khám. Khoá luôn nằm dưới ``<clinic_id>/``."""
    async with pool.acquire() as conn:
        if not await co_quyen_noi_dung(conn, identity):
            raise SafetyGateError("Bạn không có quyền xem kết quả xét nghiệm.")
        v = await conn.fetchval(
            "SELECT tep FROM lich_su_notion.xet_nghiem"
            " WHERE clinic_id = $1::uuid AND notion_id = $2::uuid",
            identity.clinic_id,
            xn_id,
        )
    ds = _json(v) or []
    if not (0 <= i < len(ds)) or not ds[i].get("khoa"):
        raise NotFoundError("Không có tệp này.")
    khoa = f"{identity.clinic_id}/lich-su-notion/{ds[i]['khoa']}"
    if ".." in khoa.split("/"):
        raise NotFoundError("Không có tệp này.")
    return khoa, str(ds[i].get("ten") or "ket-qua")
