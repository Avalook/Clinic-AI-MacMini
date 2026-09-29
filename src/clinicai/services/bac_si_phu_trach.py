"""Ai là BÁC SĨ của một việc — tách khỏi câu hỏi "ai được làm việc ấy".

Tuyền chốt 29/09/2026: *"Điều dưỡng và thư ký là TRỌN QUYỀN luôn — làm việc cho
bác sĩ thật sự."* Ai có quyền Bàn khám (lego `ban_kham`, hoặc được xếp lịch hôm
nay vào phòng khám — `v_quyen_thuc_te`) làm được như bác sĩ: khám, kê đơn, đính
chính đơn, Hoàn tất khám, bấm tiếp phiên bác sĩ đang mở.

Hai câu hỏi khác nhau, hai nơi trả lời:

* ĐƯỢC LÀM KHÔNG → luôn hỏi QUYỀN (`permissions/can.py`).
* AI LÀ BÁC SĨ (tên in ở chỗ ký, bác sĩ phụ trách của phiên, luật "hai bác sĩ
  không giành một lượt") → dữ liệu tài khoản: `clinic_membership.role` là
  DOCTOR / ULTRASOUND_DOCTOR. Đây là DANH TÍNH người ký, không phải quyền — trợ
  lý có trọn quyền vẫn không thành bác sĩ trên giấy.

Luật duy nhất còn chặn giữa những người có quyền: hai BÁC SĨ THẬT khác nhau
không giành một lượt / một phiên (HOLD đính chính chéo bác sĩ, Dr4Women).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import asyncpg

from clinicai.api.identity import vi_tri_dang_trong_ca
from clinicai.core.clock import now_vn

#: Vai tài khoản của người KÝ như bác sĩ.
VAI_BAC_SI: tuple[str, ...] = ("DOCTOR", "ULTRASOUND_DOCTOR")


async def bac_si_trong(
    conn: asyncpg.Connection, clinic_id: str, ids: Iterable[str | None]
) -> set[str]:
    """Những mã trong `ids` là tài khoản bác sĩ (còn hoạt động) của phòng khám."""
    ds = sorted({str(i) for i in ids if i})
    if not ds:
        return set()
    rows = await conn.fetch(
        "SELECT DISTINCT staff_id::text AS id FROM public.clinic_membership"
        " WHERE clinic_id = $1::uuid AND staff_id::text = ANY($2::text[])"
        " AND is_active AND role = ANY($3::text[])",
        clinic_id,
        ds,
        list(VAI_BAC_SI),
    )
    return {r["id"] for r in rows}


def hai_bac_si_khac_nhau(
    *, toi: str, bac_si_cua_viec: str | None, bac_si: set[str]
) -> bool:
    """Thuần: người bấm là bác sĩ thật VÀ việc đã thuộc một bác sĩ thật khác.

    Trợ lý (không phải bác sĩ) không bao giờ "giành" của bác sĩ; việc chưa có bác
    sĩ (hoặc đang ghi một người không phải bác sĩ) thì không có gì để giành."""
    return (
        bac_si_cua_viec is not None
        and bac_si_cua_viec != toi
        and toi in bac_si
        and bac_si_cua_viec in bac_si
    )


async def la_bac_si_khac(
    conn: asyncpg.Connection, clinic_id: str, toi: str, bac_si_cua_viec: str | None
) -> bool:
    """`hai_bac_si_khac_nhau` đọc tư cách bác sĩ từ database."""
    if not bac_si_cua_viec or bac_si_cua_viec == toi:
        return False
    return hai_bac_si_khac_nhau(
        toi=toi,
        bac_si_cua_viec=bac_si_cua_viec,
        bac_si=await bac_si_trong(conn, clinic_id, (toi, bac_si_cua_viec)),
    )


# ── BÁC SĨ THỰC HIỆN MẶC ĐỊNH CỦA PHIẾU KẾT QUẢ ──────────────────────────────
#
# Tuyền 29/09: "mặc định tên bác sĩ; trong hệ thống ghi lịch sử thì mới ghi dòng
# người nhập". Điều dưỡng bấm Hoàn tất phiếu siêu âm → chỗ ký "Bác sĩ thực hiện"
# phải là bác sĩ đứng phòng ấy hôm nay, không phải điều dưỡng. Người nhập /
# người bấm vẫn nằm ở `nhap_boi` / `hoan_tat_boi` (lịch sử).

_BAC_SI_DUNG_PHONG_SQL = """
SELECT w.staff_id::text AS id, w.station, w.shift, w.status, c.settings
  FROM public.service_order o
  JOIN public.vi_tri_lam_viec v
    ON v.clinic_id = o.clinic_id AND v.room_id = o.room_id
  JOIN public.work_roster w
    ON w.clinic_id = v.clinic_id AND w.station = v.code
  JOIN public.clinic_membership m
    ON m.clinic_id = w.clinic_id AND m.staff_id = w.staff_id
   AND m.is_active AND m.role = ANY($3::text[])
  JOIN public.clinic c ON c.id = o.clinic_id
 WHERE o.clinic_id = $1::uuid AND o.id = $2::uuid
   AND w.status <> 'REJECTED'
   AND w.work_date = (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
 ORDER BY array_position(ARRAY['SANG', 'CHIEU', 'TOI', 'FULL'], w.shift),
          v.sort NULLS LAST, w.station, w.staff_id
"""


def bac_si_dang_trong_ca(
    dong: Sequence[tuple[str, str, str, str]], phut: int, settings: object
) -> list[str]:
    """Thuần: từ các dòng lịch ``(bác sĩ, trạm, ca, trạng thái)`` của phòng hôm
    nay → bác sĩ ĐANG trong ca lúc `phut` (cùng luật ca với cửa gác vai —
    `vi_tri_dang_trong_ca`; công tắc ca tắt thì mọi dòng trừ REJECTED)."""
    ket: list[str] = []
    for ai, tram, ca, trang_thai in dong:
        if vi_tri_dang_trong_ca([(tram, ca, trang_thai)], phut, settings):
            if ai not in ket:
                ket.append(ai)
    return ket


def chon_bac_si_thuc_hien(
    *, nguoi_bam: str, nguoi_bam_la_bac_si: bool, bac_si_phong: Sequence[str]
) -> str:
    """Thuần: ai đứng tên "Bác sĩ thực hiện" khi không ai chọn người thực hiện.

    * Người bấm là bác sĩ → chính họ.
    * Phòng hôm nay có ĐÚNG MỘT bác sĩ đang trong ca → bác sĩ ấy.
    * Không có, hoặc nhiều bác sĩ (không biết ai làm) → người bấm, như cũ — thà
      in người thật đã bấm còn hơn in tên một bác sĩ có thể không làm ca này.
      Muốn tên bác sĩ thì chọn "Người thực hiện" trên phiếu.
    """
    if nguoi_bam_la_bac_si:
        return nguoi_bam
    ds = list(dict.fromkeys(bac_si_phong))
    if len(ds) == 1:
        return ds[0]
    return nguoi_bam


async def bac_si_thuc_hien_mac_dinh(
    conn: asyncpg.Connection,
    *,
    clinic_id: str,
    service_order_id: str,
    nguoi_bam: str,
) -> str:
    """Người đứng tên thực hiện phiếu kết quả của chỉ định khi không ai chọn."""
    if await bac_si_trong(conn, clinic_id, [nguoi_bam]):
        return nguoi_bam
    rows = await conn.fetch(
        _BAC_SI_DUNG_PHONG_SQL, clinic_id, service_order_id, list(VAI_BAC_SI)
    )
    if not rows:
        return nguoi_bam
    bay_gio = now_vn()
    dang_trong_ca = bac_si_dang_trong_ca(
        [(r["id"], str(r["station"]), str(r["shift"]), str(r["status"])) for r in rows],
        bay_gio.hour * 60 + bay_gio.minute,
        rows[0]["settings"],
    )
    return chon_bac_si_thuc_hien(
        nguoi_bam=nguoi_bam, nguoi_bam_la_bac_si=False, bac_si_phong=dang_trong_ca
    )


__all__ = [
    "VAI_BAC_SI",
    "bac_si_dang_trong_ca",
    "bac_si_thuc_hien_mac_dinh",
    "bac_si_trong",
    "chon_bac_si_thuc_hien",
    "hai_bac_si_khac_nhau",
    "la_bac_si_khac",
]
