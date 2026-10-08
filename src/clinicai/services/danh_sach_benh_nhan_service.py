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
  · XẾP THEO HOẠT ĐỘNG GẦN NHẤT (27/09/2026 đợt 3, A6) — cột ``luc`` của
    ``_CO_SO``.

PHÂN TRANG PHÍA MÁY CHỦ (06/10/2026). Sáng 06/10 nạp ~8.600 hồ sơ cũ từ Notion.
Bản trước nạp HẾT danh sách về trình duyệt (trần 5.000) rồi lọc tại chỗ, nên
phải giấu hồ sơ cũ chưa hoạt động — màn chỉ còn 145 hồ sơ. Nay MỌI hồ sơ vào
danh sách; máy chủ tìm (tên không dấu / mã / một phần SĐT), lọc theo tab, xếp,
cắt trang ``MOT_TRANG`` dòng, và đếm số ở tab + ô tổng trên TOÀN BỘ hồ sơ.
Đầu vào rác (trang chữ, trang âm, tab lạ, mã khách hỏng) → mặc định, không ném.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any
from uuid import UUID

import asyncpg

from clinicai.api.identity import StaffIdentity
from clinicai.services.danh_sach_khach_cskh import COT_KENH_DOI_HUY
from clinicai.services.lich_su_luot import LOAI_DU_LIEU_SQL
from clinicai.services.nhan_luot import doc_nhan_luot, tra_nhan
from clinicai.services.thu_ky_bac_si import khach_duoc_xem

#: Số hồ sơ một trang — cùng cỡ với Quản lý khách hàng (KHACH_MOT_TRANG).
MOT_TRANG = 50
#: Trần lượt khám nạp kèm MỘT trang. Lượt CHỈ nạp cho khách của trang đang xem
#: + khách đang chọn (≤ 51 người) — tối 06/10 lượt cũ Notion thành ~14.000 lượt
#: thật, gửi hết về trình duyệt như bản trước (trần 20.000) là quá tải. Số lượt
#: để phân loại mới / cũ / chưa khám vẫn đếm trên TOÀN BỘ ở ``_CO_SO``.
TRAN_LUOT = 5000

#: Tab của màn (``?loc=``) → (số lượt tối thiểu, tối đa). Cùng ngưỡng với
#: ``phan_loai``. Không có / lạ = tất cả.
LOC_THEO_SO_LUOT: dict[str, tuple[int, int | None]] = {
    "lan-dau": (1, 1),
    "tai-kham": (2, None),
    "chua-kham": (0, 0),
}

# CƠ SỞ CỦA MỌI CÂU: mỗi hồ sơ người gọi được xem, kèm số lượt, đang mở, mốc
# hoạt động gần nhất (``luc``) và có khớp ô tìm + tab không (``khop``).
#
# ``luc`` = coalesce(LƯỢT gần nhất, LỊCH gần nhất, ngày tạo hồ sơ). Phòng khám
# 27/09/2026: *"Danh sách BN nên hiển thị ngày gần nhất bên trên"*. Màn lâm
# sàng nên lượt khám thật đứng trước:
#   * lượt = `visit.created_at`, hoặc giờ hẹn của lịch khách ĐÃ TỚI
#     (CHECKED_IN / COMPLETED — đúng định nghĩa "một lượt khám" ở trên);
#   * lịch = lúc ĐẶT lịch gần nhất, hoặc giờ hẹn ĐÃ QUA còn sống. Giờ hẹn
#     TƯƠNG LAI không tính — tái khám ba tháng tới không ghim khách lên đầu;
#   * chưa có gì → ngày tạo hồ sơ (khách mới vẫn lên đầu ngày tạo).
# Gộp MỘT lần theo khách (``lh``/``vs``, hash join) thay vì bốn câu con cho từng
# hồ sơ như bản trước: 8.700 hồ sơ × 4 câu con mới là thứ làm chậm trang.
#
# Tham số: $1 clinic · $2 mã khách được xem (NULL = không lọc) · $3 mẫu ILIKE ·
# $4 chuỗi tìm (bỏ dấu ở SQL) · $5 mẫu chỉ-số cho SĐT · $6/$7 số lượt min/max.
_CO_SO = """
WITH lh AS (
    SELECT a.clinic_patient_id,
           count(*) FILTER (WHERE a.status IN ('CHECKED_IN', 'COMPLETED'))
               AS so_luot,
           bool_or(a.status = 'CHECKED_IN' AND v.closed_at IS NULL) AS dang_mo,
           max(a.slot_start) FILTER (WHERE a.status IN ('CHECKED_IN', 'COMPLETED'))
               AS den_gan_nhat,
           max(a.created_at) AS dat_gan_nhat,
           max(a.slot_start) FILTER (
               WHERE a.slot_start <= now()
                 AND a.status NOT IN ('CANCELLED', 'NO_SHOW', 'DOCTOR_DECLINED'))
               AS hen_da_qua
      FROM appointment a
      -- Một lịch có tối đa một lượt (uq_visit_appointment_id) → không nhân dòng.
      LEFT JOIN visit v
        ON v.clinic_id = a.clinic_id AND v.appointment_id = a.id
     WHERE a.clinic_id = $1::uuid AND a.clinic_patient_id IS NOT NULL
     GROUP BY a.clinic_patient_id
), vs AS (
    SELECT v.clinic_patient_id, max(v.created_at) AS luot_gan_nhat
      FROM visit v
     WHERE v.clinic_id = $1::uuid AND v.clinic_patient_id IS NOT NULL
     GROUP BY v.clinic_patient_id
), co_so AS (
    SELECT p.clinic_patient_id,
           coalesce(lh.so_luot, 0) AS so_luot,
           coalesce(lh.dang_mo, false) AS dang_mo,
           coalesce(greatest(vs.luot_gan_nhat, lh.den_gan_nhat),
                    greatest(lh.dat_gan_nhat, lh.hen_da_qua),
                    p.created_at) AS luc,
           ($3::text IS NULL
            OR p.full_name ILIKE $3 OR p.patient_code ILIKE $3
            OR p.sdt_tim_kiem ILIKE $3
            OR p.full_name_unaccent ILIKE
               '%' || lower(replace(replace(f_unaccent($4), 'đ', 'd'), 'Đ', 'D'))
               || '%'
            OR ($5::text IS NOT NULL AND p.sdt_tim_kiem LIKE $5))
           AND coalesce(lh.so_luot, 0) >= $6
           AND ($7::int IS NULL OR coalesce(lh.so_luot, 0) <= $7) AS khop
      FROM patient p
      LEFT JOIN lh ON lh.clinic_patient_id = p.clinic_patient_id
      LEFT JOIN vs ON vs.clinic_patient_id = p.clinic_patient_id
     WHERE p.clinic_id = $1::uuid
       AND ($2::text[] IS NULL OR p.clinic_patient_id::text = ANY($2::text[]))
)
"""

# Ô tổng + số ở tab đếm trên TOÀN BỘ ``co_so``; ``khop`` = số dòng của bảng.
_DEM_SQL = (
    _CO_SO
    + """
SELECT count(*) AS ho_so,
       count(*) FILTER (WHERE dang_mo) AS dang_mo,
       count(*) FILTER (WHERE so_luot = 1) AS lan_dau,
       count(*) FILTER (WHERE so_luot >= 2) AS tai_kham,
       count(*) FILTER (WHERE so_luot = 0) AS chua_kham,
       count(*) FILTER (WHERE khop) AS khop
  FROM co_so
"""
)

_COT_HO_SO = f"""
       p.clinic_patient_id::text AS clinic_patient_id, p.patient_code,
       p.full_name, p.date_of_birth, p.phone_primary, p.phone_secondary,
       p.gender, p.ethnicity, p.nationality, p.occupation, p.patient_objection,
       p.address, p.guardian_name, tr.luc AS hoat_dong_gan_nhat,
       coalesce((
           SELECT json_agg(json_build_object('so_dien_thoai', t.so_dien_thoai,
                                             'loai', t.loai))
             FROM patient_sdt_them t
            WHERE t.clinic_patient_id = p.clinic_patient_id
       ), '[]'::json) AS patient_sdt_them,
{COT_KENH_DOI_HUY}
"""

#: Chiều xếp → (ORDER BY trên ``co_so``, ORDER BY câu ngoài). Chọn trong danh
#: sách trắng, không ghép chuỗi người dùng. "xa" là đảo ĐÚNG thứ tự "gan", kể
#: cả khoá phụ mã khách — hai khách cùng mốc không đổi chỗ giữa hai lần tải →
#: phân trang không lặp / sót.
_XEP = {
    "gan": ("luc DESC, clinic_patient_id", "tr.luc DESC, p.clinic_patient_id"),
    "xa": ("luc ASC, clinic_patient_id DESC", "tr.luc ASC, p.clinic_patient_id DESC"),
}


def _trang_sql(xep: str) -> str:
    """Một trang: cắt trên ``co_so`` TRƯỚC, rồi mới tính cột nặng (SĐT thêm,
    kênh / đổi huỷ) cho ≤ 50 dòng. $8 offset · $9 limit."""
    trong, ngoai = _XEP[xep]
    return (
        _CO_SO
        + f"""
, tr AS (
    SELECT clinic_patient_id, luc FROM co_so
     WHERE khop
     ORDER BY {trong}
     OFFSET $8 LIMIT $9
)
SELECT {_COT_HO_SO}
  FROM tr JOIN patient p
    ON p.clinic_id = $1::uuid AND p.clinic_patient_id = tr.clinic_patient_id
 ORDER BY {ngoai}
"""
    )


_TRANG_SQL = {k: _trang_sql(k) for k in _XEP}

#: Một hồ sơ theo mã (``?chon=`` — khách mở từ link, có thể ngoài trang đang
#: xem). Vẫn đi qua ``co_so`` để thư ký không mở được khách ngoài phạm vi; KHÔNG
#: lọc theo ô tìm / tab. $8 = mã khách.
_MOT_SQL = (
    _CO_SO
    + f"""
, tr AS (SELECT clinic_patient_id, luc FROM co_so WHERE clinic_patient_id = $8::uuid)
SELECT {_COT_HO_SO}
  FROM tr JOIN patient p
    ON p.clinic_id = $1::uuid AND p.clinic_patient_id = tr.clinic_patient_id
"""
)

# `visit_id` + `loai_du_lieu` (07/10/2026, T8): bấm một lượt mở đúng khung đọc
# — phiếu v5 → hồ sơ kiểu Bàn khám; đời cũ / Notion / chưa phiếu → khung cũ.
_LUOT_SQL = f"""
SELECT a.id::text AS id, a.clinic_patient_id::text AS clinic_patient_id,
       a.status, a.queue_number, a.slot_start, a.booking_channel,
       st.name AS service_name, d.full_name AS doctor_name,
       v.closed_at, v.visit_id::text AS visit_id, v.loai_du_lieu
  FROM appointment a
  LEFT JOIN service_type st ON st.id = a.service_type_id
  LEFT JOIN staff d ON d.id = a.doctor_id
  LEFT JOIN LATERAL (
      SELECT vi.closed_at, vi.visit_id,
             {LOAI_DU_LIEU_SQL.format(v="vi")} AS loai_du_lieu
        FROM visit vi
       WHERE vi.clinic_id = a.clinic_id AND vi.appointment_id = a.id
       ORDER BY vi.checked_in_at DESC NULLS LAST
       LIMIT 1
  ) v ON TRUE
 WHERE a.clinic_id = $1::uuid
   AND a.status IN ('CHECKED_IN', 'COMPLETED')
   AND a.clinic_patient_id::text = ANY($2::text[])
 ORDER BY a.slot_start DESC
 LIMIT $3
"""


def phan_loai(so_luot: int) -> str:
    if so_luot <= 0:
        return "Chưa khám"
    return "Khám lần đầu" if so_luot == 1 else "Tái khám"


def dang_mo(luot: dict[str, Any]) -> bool:
    return luot["status"] == "CHECKED_IN" and luot.get("closed_at") is None


def doc_trang(v: Any) -> int:
    """``?trang=`` → số trang ≥ 1. Rác (chữ, âm, rỗng, số thực) → 1."""
    try:
        n = int(str(v).strip())
    except (TypeError, ValueError):
        return 1
    return n if n >= 1 else 1


def doc_loc(v: Any) -> str | None:
    """``?loc=`` → khoá tab trong ``LOC_THEO_SO_LUOT``; lạ / rỗng → None (tất cả)."""
    k = str(v or "").strip()
    return k if k in LOC_THEO_SO_LUOT else None


def doc_sap(v: Any) -> str:
    """``?sap=`` → "gan" (mặc định, hoạt động gần nhất trước) hoặc "xa"."""
    return "xa" if str(v or "").strip() == "xa" else "gan"


def chuoi_tim(q: Any) -> str:
    """Bỏ ký tự đặc biệt của ILIKE, gộp khoảng trắng, cắt 100 ký tự. Rác → rỗng."""
    t = re.sub(r"[,()%*_\\]", " ", str(q or ""))
    return " ".join(t.split())[:100]


def mau_so(t: str) -> str | None:
    """Ô tìm CHỈ có số (kèm dấu cách / chấm / gạch / +) → mẫu tìm trong cột gộp
    mọi SĐT, bỏ dấu ngăn: "0912 345" khớp "0912345678". Dưới 3 chữ số → bỏ
    (khớp quá rộng); có chữ cái → không phải số điện thoại."""
    if not t or not re.fullmatch(r"[\d\s.+\-]+", t):
        return None
    so = re.sub(r"\D", "", t)
    return f"%{so}%" if len(so) >= 3 else None


def ma_khach(v: Any) -> str | None:
    """``?chon=`` → mã khách chuẩn; hỏng → None."""
    try:
        return str(UUID(str(v or "").strip()))
    except ValueError:
        return None


def ghep(
    ho_so: list[dict[str, Any]], luot: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Ghép hồ sơ + lượt (đã xếp mới → cũ) thành dòng danh sách. Thuần.

    GIỮ NGUYÊN THỨ TỰ ``ho_so`` — câu SQL đã xếp theo hoạt động gần nhất.
    Bản trước xếp lại ở đây theo lượt mới nhất rồi dồn mọi khách "Chưa khám"
    xuống đáy theo tên: khách mới tạo hôm nay nằm sau khách khám từ năm ngoái
    (27/09/2026 đợt 3, A6)."""
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
    return dong


class DanhSachBenhNhanService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def lay(
        self,
        *,
        identity: StaffIdentity,
        trang: Any = 1,
        q: Any = None,
        loc: Any = None,
        sap: Any = None,
        chon: Any = None,
    ) -> dict[str, Any]:
        """Một trang danh sách + số đếm toàn bộ + (tuỳ) một hồ sơ ``chon``.

        ``tong`` (ô tổng + số ở tab) đếm trên TOÀN BỘ hồ sơ người gọi được xem,
        không theo ô tìm / tab / trang. ``so_khop`` = số hồ sơ khớp ô tìm + tab
        (dòng "Hiển thị x–y trên N"). Trang vượt quá → trang cuối. ``chon``
        chỉ có khi khách ấy KHÔNG nằm trong trang trả về."""
        ids = await khach_duoc_xem(self._pool, identity)
        t = chuoi_tim(q)
        khoang = LOC_THEO_SO_LUOT.get(doc_loc(loc) or "", (0, None))
        nen = (
            identity.clinic_id,
            ids,
            f"%{t}%" if t else None,
            t,
            mau_so(t),
            khoang[0],
            khoang[1],
        )
        ma_chon = ma_khach(chon)
        async with self._pool.acquire() as conn:
            dem = await conn.fetchrow(_DEM_SQL, *nen)
            so_khop = int(dem["khop"]) if dem else 0
            so_trang = max(1, math.ceil(so_khop / MOT_TRANG))
            so = min(doc_trang(trang), so_trang)
            ho_so = await conn.fetch(
                _TRANG_SQL[doc_sap(sap)], *nen, (so - 1) * MOT_TRANG, MOT_TRANG
            )
            mot = None
            if ma_chon and all(r["clinic_patient_id"] != ma_chon for r in ho_so):
                mot = await conn.fetchrow(_MOT_SQL, *nen, ma_chon)
            can_luot = [r["clinic_patient_id"] for r in ho_so]
            if mot is not None:
                can_luot.append(mot["clinic_patient_id"])
            luot = (
                await conn.fetch(_LUOT_SQL, identity.clinic_id, can_luot, TRAN_LUOT)
                if can_luot
                else []
            )
            # "Lượt khám n" / "Buổi k/N" (08/10/2026) — đếm trên MỌI lượt của
            # khách theo thời gian, không theo chỉ số mảng ở màn.
            nhan = await doc_nhan_luot(conn, identity.clinic_id, can_luot)
        cac_luot = [
            {
                **dict(r),
                "slot_start": r["slot_start"].isoformat(),
                "closed_at": r["closed_at"].isoformat() if r["closed_at"] else None,
                "nhan_luot": tra_nhan(
                    nhan, visit_id=r.get("visit_id"), appointment_id=r.get("id")
                ),
            }
            for r in luot
        ]
        return {
            "tong": {
                k: int(dem[k]) if dem else 0
                for k in ("ho_so", "dang_mo", "lan_dau", "tai_kham", "chua_kham")
            },
            "dong": ghep([_ho_so(r) for r in ho_so], cac_luot),
            "trang": so,
            "mot_trang": MOT_TRANG,
            "so_trang": so_trang,
            "so_khop": so_khop,
            "chon": ghep([_ho_so(mot)], cac_luot)[0] if mot is not None else None,
        }


def _ho_so(r: asyncpg.Record) -> dict[str, Any]:
    d = dict(r)
    d["date_of_birth"] = r["date_of_birth"].isoformat() if r["date_of_birth"] else None
    hd = d.get("hoat_dong_gan_nhat")
    d["hoat_dong_gan_nhat"] = hd.isoformat() if hd is not None else None
    sdt = r["patient_sdt_them"]
    d["patient_sdt_them"] = json.loads(sdt) if isinstance(sdt, str) else (sdt or [])
    dh = d.get("doi_huy_gan_nhat")
    d["doi_huy_gan_nhat"] = json.loads(dh) if isinstance(dh, str) else dh
    return d
