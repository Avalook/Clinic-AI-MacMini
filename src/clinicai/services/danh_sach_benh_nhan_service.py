"""Danh sách bệnh nhân — tra cứu hồ sơ + các lượt khám (16/09/2026).

VÌ SAO RỜI SUPABASE VỀ ĐÂY. Màn cũ đọc thẳng database trong trình duyệt và đếm
lượt khám bằng một bộ lọc "COMPLETED, hoặc CHECKED_IN trong HÔM NAY". Qua nửa
đêm, mọi lượt check-in hôm qua chưa đóng biến mất: 46/46 hồ sơ hiện "Chưa khám"
và "Có lượt đang mở = 0", trong khi màn Quản lý khách hàng cùng lúc ghi "Đã
check-in — đang chờ khám" cho chính những người ấy. Hai màn nói ngược nhau.

Luật ở đây (một chỗ):
  · MỘT LƯỢT KHÁM = lịch hẹn khách ĐÃ TỚI (CHECKED_IN hoặc COMPLETED), bất kể
    ngày. Lịch còn hẹn / huỷ / không đến không phải lượt khám.
  · ĐANG MỞ = CHECKED_IN mà quầy chưa đóng lượt (visit.closed_at NULL).
  · Phân loại: 0 lượt = Chưa khám · 1 = Khám lần đầu · ≥ 2 = Tái khám.
  · Thư ký y khoa chỉ thấy khách của bác sĩ mình (thu_ky_bac_si).
  · XẾP THEO HOẠT ĐỘNG GẦN NHẤT (27/09/2026 đợt 3, A6) — ``KHOA_XEP``. Trần
    ``TRAN_HO_SO`` cắt theo CÙNG khoá ấy: bản cũ lấy 5000 hồ sơ MỚI TẠO nhất,
    nên khi vượt trần, khách cũ vừa khám hôm nay bị cắt khỏi danh sách.
"""

from __future__ import annotations

from typing import Any

import asyncpg

from clinicai.api.identity import StaffIdentity
from clinicai.services.danh_sach_khach_cskh import COT_KENH_DOI_HUY
from clinicai.services.thu_ky_bac_si import khach_duoc_xem

TRAN_HO_SO = 5000
TRAN_LUOT = 20000

#: Khoá xếp danh sách bệnh nhân (alias `p` = patient). Phòng khám 27/09/2026:
#: *"Danh sách BN nên hiển thị ngày gần nhất bên trên"*.
#:
#: coalesce(LƯỢT gần nhất, LỊCH gần nhất, ngày tạo hồ sơ) — màn này là màn
#: lâm sàng nên lượt khám thật đứng trước:
#:   * lượt = `visit.created_at`, hoặc giờ hẹn của lịch khách ĐÃ TỚI
#:     (CHECKED_IN / COMPLETED — đúng định nghĩa "một lượt khám" ở trên);
#:   * lịch = lúc ĐẶT lịch gần nhất, hoặc giờ hẹn ĐÃ QUA còn sống. Giờ hẹn
#:     TƯƠNG LAI không tính — tái khám ba tháng tới không ghim khách lên đầu;
#:   * chưa có gì → ngày tạo hồ sơ (khách mới vẫn lên đầu ngày tạo).
KHOA_XEP = """
    coalesce(
        greatest(
            (SELECT max(v.created_at) FROM visit v
              WHERE v.clinic_id = p.clinic_id
                AND v.clinic_patient_id = p.clinic_patient_id),
            (SELECT max(a.slot_start) FROM appointment a
              WHERE a.clinic_id = p.clinic_id
                AND a.clinic_patient_id = p.clinic_patient_id
                AND a.status IN ('CHECKED_IN', 'COMPLETED'))
        ),
        greatest(
            (SELECT max(a.created_at) FROM appointment a
              WHERE a.clinic_id = p.clinic_id
                AND a.clinic_patient_id = p.clinic_patient_id),
            (SELECT max(a.slot_start) FROM appointment a
              WHERE a.clinic_id = p.clinic_id
                AND a.clinic_patient_id = p.clinic_patient_id
                AND a.slot_start <= now()
                AND a.status NOT IN ('CANCELLED', 'NO_SHOW', 'DOCTOR_DECLINED'))
        ),
        p.created_at
    )
"""

_HO_SO_SQL = f"""
SELECT p.clinic_patient_id::text AS clinic_patient_id, p.patient_code,
       p.full_name, p.date_of_birth, p.phone_primary, p.phone_secondary,
       p.gender, p.ethnicity, p.nationality, p.occupation, p.patient_objection,
       p.address, p.guardian_name, hd.luc AS hoat_dong_gan_nhat,
       coalesce((
           SELECT json_agg(json_build_object('so_dien_thoai', t.so_dien_thoai,
                                             'loai', t.loai))
             FROM patient_sdt_them t
            WHERE t.clinic_patient_id = p.clinic_patient_id
       ), '[]'::json) AS patient_sdt_them,
{COT_KENH_DOI_HUY}
  FROM patient p
  CROSS JOIN LATERAL (SELECT {KHOA_XEP} AS luc) hd
 WHERE p.clinic_id = $1::uuid
   AND p.clinic_patient_id::text
       = ANY(coalesce($2::text[], ARRAY[p.clinic_patient_id::text]))
 -- Mã khách là khoá phụ: hai khách cùng mốc không đổi chỗ giữa hai lần tải.
 ORDER BY hd.luc DESC, p.clinic_patient_id
 LIMIT $3
"""

_LUOT_SQL = """
SELECT a.id::text AS id, a.clinic_patient_id::text AS clinic_patient_id,
       a.status, a.queue_number, a.slot_start, a.booking_channel,
       st.name AS service_name, d.full_name AS doctor_name,
       v.closed_at
  FROM appointment a
  LEFT JOIN service_type st ON st.id = a.service_type_id
  LEFT JOIN staff d ON d.id = a.doctor_id
  LEFT JOIN LATERAL (
      SELECT vi.closed_at FROM visit vi
       WHERE vi.clinic_id = a.clinic_id AND vi.appointment_id = a.id
       ORDER BY vi.checked_in_at DESC NULLS LAST
       LIMIT 1
  ) v ON TRUE
 WHERE a.clinic_id = $1::uuid
   AND a.status IN ('CHECKED_IN', 'COMPLETED')
   AND a.clinic_patient_id::text
       = ANY(coalesce($2::text[], ARRAY[a.clinic_patient_id::text]))
 ORDER BY a.slot_start DESC
 LIMIT $3
"""


def phan_loai(so_luot: int) -> str:
    if so_luot <= 0:
        return "Chưa khám"
    return "Khám lần đầu" if so_luot == 1 else "Tái khám"


def dang_mo(luot: dict[str, Any]) -> bool:
    return luot["status"] == "CHECKED_IN" and luot.get("closed_at") is None


def gop(ho_so: list[dict[str, Any]], luot: list[dict[str, Any]]) -> dict[str, Any]:
    """Ghép hồ sơ + lượt (đã xếp mới → cũ) thành dòng danh sách + số tổng. Thuần.

    GIỮ NGUYÊN THỨ TỰ ``ho_so`` — câu SQL đã xếp theo hoạt động gần nhất
    (``KHOA_XEP``). Bản trước xếp lại ở đây theo lượt mới nhất rồi dồn mọi
    khách "Chưa khám" xuống đáy theo tên: khách mới tạo hôm nay nằm sau khách
    khám từ năm ngoái (27/09/2026 đợt 3, A6)."""
    theo_khach: dict[str, list[dict[str, Any]]] = {}
    for x in luot:
        theo_khach.setdefault(x["clinic_patient_id"], []).append(x)

    dong: list[dict[str, Any]] = []
    for h in ho_so:
        cac = theo_khach.get(h["clinic_patient_id"], [])
        dong.append(
            {
                "ho_so": h,
                "so_luot": len(cac),
                "phan_loai": phan_loai(len(cac)),
                "dang_mo": any(dang_mo(x) for x in cac),
                "luot": cac,
            }
        )
    return {
        "tong": {
            "ho_so": len(dong),
            "dang_mo": sum(1 for r in dong if r["dang_mo"]),
            "lan_dau": sum(1 for r in dong if r["phan_loai"] == "Khám lần đầu"),
            "tai_kham": sum(1 for r in dong if r["phan_loai"] == "Tái khám"),
            "chua_kham": sum(1 for r in dong if r["phan_loai"] == "Chưa khám"),
        },
        "dong": dong,
    }


class DanhSachBenhNhanService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def lay(self, *, identity: StaffIdentity) -> dict[str, Any]:
        ids = await khach_duoc_xem(self._pool, identity)
        async with self._pool.acquire() as conn:
            ho_so = await conn.fetch(_HO_SO_SQL, identity.clinic_id, ids, TRAN_HO_SO)
            luot = await conn.fetch(_LUOT_SQL, identity.clinic_id, ids, TRAN_LUOT)
        return gop(
            [_ho_so(r) for r in ho_so],
            [
                {
                    **dict(r),
                    "slot_start": r["slot_start"].isoformat(),
                    "closed_at": r["closed_at"].isoformat() if r["closed_at"] else None,
                }
                for r in luot
            ],
        )


def _ho_so(r: asyncpg.Record) -> dict[str, Any]:
    import json

    d = dict(r)
    d["date_of_birth"] = r["date_of_birth"].isoformat() if r["date_of_birth"] else None
    hd = d.get("hoat_dong_gan_nhat")
    d["hoat_dong_gan_nhat"] = hd.isoformat() if hd is not None else None
    sdt = r["patient_sdt_them"]
    d["patient_sdt_them"] = json.loads(sdt) if isinstance(sdt, str) else (sdt or [])
    dh = d.get("doi_huy_gan_nhat")
    d["doi_huy_gan_nhat"] = json.loads(dh) if isinstance(dh, str) else dh
    return d
