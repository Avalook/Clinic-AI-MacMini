"""Tự ghép thư kết quả Gmail vào đúng việc — Gmail G3 (luật Tuyền duyệt 09/11/2026).

Chỉ thư nhận TỪ mốc `xet_nghiem_cai_dat.gmail_tu_ngay` (giờ VN) trở đi, và chỉ thư có
xác thực đúng miền người gửi (DKIM/DMARC — header From giả được), mới được xét. Thư
trước mốc / không xác thực / Greenlab "Chưa đủ kết quả" / phiếu mã vạch ⇒ `LUU_TRU`
(chỉ ở Kho) như G2. Mốc chỉ áp cho thư NHẬN SAU khi đặt mốc; thư đã vào Kho trước đó
không được xét lại tự động.

Quyết định là MỘT hàm thuần `quyet` (test bằng bảng). Khớp tên + SĐT = luật duy nhất
`ghep_khach.khop_ds` (cùng luật Drive). Năm sinh chỉ để gỡ khi nhiều khách cùng khớp.
Không ghép theo mã mẫu của lab, không theo mã xét nghiệm trong tên tệp. Không chắc ⇒
hàng ghép tay kèm lý do + gợi ý, KHÔNG đoán.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Final
from zoneinfo import ZoneInfo

import asyncpg
import structlog

from clinicai.core.tran import canh_bao_neu_day
from clinicai.services.xet_nghiem import ghep_khach
from clinicai.services.xet_nghiem.gmail_doc import DocThu

logger = structlog.get_logger()

_VN: Final = ZoneInfo("Asia/Ho_Chi_Minh")
TRAN_VIEC: Final = 500


@dataclass(frozen=True)
class ViecGmail:
    order_id: str
    clinic_patient_id: str
    visit_id: str | None
    ten: str | None
    sdt: str | None
    nam_sinh: int | None
    da_lay_mau: bool
    co_tep: bool


@dataclass(frozen=True)
class QuyetGmail:
    """`ly_do` None = TỰ GHÉP vào `order_id`; còn lại = mã lý do chờ (`drive_tep`)."""

    ly_do: str | None
    order_id: str | None = None
    clinic_patient_id: str | None = None
    visit_id: str | None = None
    goi_y_order_id: str | None = None
    goi_y_clinic_patient_id: str | None = None


LUU_TRU: Final = QuyetGmail("LUU_TRU")


def quyet(d: DocThu, viec: list[ViecGmail], co_chu: bool) -> QuyetGmail:
    """HÀM THUẦN: một PDF (đã đọc theo luật lab) + các việc của đối tác ⇒ quyết.

    - Không nhận ra kiểu thư ⇒ KHONG_KHOP_KHACH (ghép tay — người xem).
    - Kiểu nhận ra nhưng không được tự ghép (từng phần / phiếu) ⇒ LUU_TRU.
    - Thiếu tên / SĐT ⇒ KHONG_DOC_DUOC (PDF scan) hoặc KHONG_KHOP_KHACH.
    - Khớp ≠ 1 khách (sau khi gỡ bằng năm sinh) ⇒ KHONG_KHOP_KHACH / NHIEU_KHACH.
    - Một khách: đúng 1 việc đang chờ kết quả ⇒ TỰ GHÉP; nhiều ⇒ ONG_NHIEU_VIEC; chưa
      lấy mẫu ⇒ CHUA_LAY_MAU; đã có tờ ⇒ CO_BAN_MOI (gợi ý việc khi đúng một)."""
    if not d.kieu:
        return QuyetGmail("KHONG_KHOP_KHACH")
    if not d.tu_ghep_duoc:
        return LUU_TRU
    if not d.ten or not d.sdt:
        return QuyetGmail("KHONG_DOC_DUOC" if not co_chu else "KHONG_KHOP_KHACH")
    khop = ghep_khach.khop_ds(f"{d.ten}\n{d.sdt}", viec)
    if len({v.clinic_patient_id for v in khop}) > 1 and d.nam_sinh is not None:
        # Năm sinh chỉ để GỠ; lọc mà không còn ai (hồ sơ thiếu năm sinh) ⇒ giữ nguyên
        # ⇒ NHIEU_KHACH (người chọn), không được rơi thành "không khớp ai".
        loc = [v for v in khop if v.nam_sinh == d.nam_sinh]
        khop = loc or khop
    khach = {v.clinic_patient_id for v in khop}
    if not khach:
        return QuyetGmail("KHONG_KHOP_KHACH")
    if len(khach) > 1:
        return QuyetGmail("NHIEU_KHACH")
    kh = next(iter(khach))
    cho = [v for v in khop if v.da_lay_mau and not v.co_tep]
    if len(cho) == 1:
        v = cho[0]
        return QuyetGmail(None, v.order_id, v.clinic_patient_id, v.visit_id)
    if cho:
        return QuyetGmail("ONG_NHIEU_VIEC", goi_y_clinic_patient_id=kh)
    for ma, nhom in (
        ("CHUA_LAY_MAU", [v for v in khop if not v.da_lay_mau and not v.co_tep]),
        ("CO_BAN_MOI", [v for v in khop if v.co_tep]),
    ):
        if nhom:
            return QuyetGmail(
                ma,
                goi_y_order_id=nhom[0].order_id if len(nhom) == 1 else None,
                goi_y_clinic_patient_id=kh,
            )
    return QuyetGmail("KHONG_KHOP_KHACH", goi_y_clinic_patient_id=kh)


def trong_moc(nhan_luc: Any, moc: date | None) -> bool:
    """Thư nhận (giờ VN) từ mốc trở đi? Không mốc ⇒ False (chưa tự ghép thư nào)."""
    if moc is None or nhan_luc is None:
        return False
    try:
        return bool(nhan_luc.astimezone(_VN).date() >= moc)
    except (AttributeError, ValueError):
        return False


#: Mọi việc đối tác này trong 120 ngày (cả chưa lấy mẫu / đã có tờ — để gợi ý), kèm năm
#: sinh khách để gỡ trùng SĐT (mẹ con chung số).
_VIEC_SQL = """
SELECT o.id::text AS order_id, v.clinic_patient_id::text AS clinic_patient_id,
       o.visit_id::text AS visit_id, p.full_name AS ten, p.phone_primary AS sdt,
       coalesce(p.birth_year::int, extract(year FROM p.date_of_birth)::int)
           AS nam_sinh,
       EXISTS (SELECT 1 FROM mau_xet_nghiem_viec mv
                 JOIN mau_xet_nghiem m ON m.id = mv.mau_id AND m.huy_luc IS NULL
                WHERE mv.clinic_id = x.clinic_id AND mv.service_order_id = o.id
                  AND mv.go_luc IS NULL) AS da_lay_mau,
       EXISTS (SELECT 1 FROM tep_ket_qua k
                WHERE k.clinic_id = x.clinic_id AND k.service_order_id = o.id
                  AND k.da_xoa_luc IS NULL
                  AND coalesce(k.xac_nhan_trang_thai, '')
                      NOT IN ('TU_CHOI', 'THU_HOI')) AS co_tep
  FROM xet_nghiem_viec x
  JOIN service_order o ON o.id = x.service_order_id AND o.clinic_id = x.clinic_id
  JOIN visit v ON v.visit_id = o.visit_id AND v.clinic_id = o.clinic_id
  JOIN patient p
    ON p.clinic_patient_id = v.clinic_patient_id AND p.clinic_id = v.clinic_id
 WHERE x.clinic_id = $1::uuid AND x.doi_tac_id = $2::uuid
   AND o.exec_status <> 'cancelled'
   AND x.tao_luc > now() - interval '120 days'
 LIMIT 500
"""


async def doc_viec(
    conn: asyncpg.Connection, cid: str, doi_tac_id: str
) -> list[ViecGmail]:
    rows = await conn.fetch(_VIEC_SQL, cid, doi_tac_id)
    # Chạm trần ⇒ có thể sót đúng việc: báo (luật cắt không im lặng).
    canh_bao_neu_day("xet_nghiem_viec", len(rows), TRAN_VIEC, clinic_id=cid)
    return [ViecGmail(**dict(r)) for r in rows]


async def gan_tu_dong(
    pool: asyncpg.Pool, cid: str, dong_id: str, q: QuyetGmail, data: bytes, ten: str
) -> bool:
    """Dòng thư đã ghi (cùng giao dịch cả thư) ⇒ tạo tờ kết quả qua ĐÚNG lõi tải lên
    của tệp đối tác (`tai_len`, máy quét, nguồn GMAIL ⇒ CHO_XAC_NHAN, báo bác sĩ +
    CSKH), gắn vào dòng, phát `lab.result_arrived`. Tải lên lỗi ⇒ dòng sang LOI_TEP
    (hàng ghép tay), không mất thư."""
    from clinicai.services.nguon_tep import MayQuet
    from clinicai.services.tep_ket_qua_service import TepKetQuaService
    from clinicai.services.xet_nghiem import drive

    assert q.order_id is not None and q.clinic_patient_id is not None
    try:
        kq = await TepKetQuaService(pool).tai_len(
            identity=MayQuet(clinic_id=cid),
            clinic_patient_id=q.clinic_patient_id,
            data=data,
            ten_hien_thi=ten,
            service_order_id=q.order_id,
            la_tep_doi_tac=True,
            tu_drive=True,
            tu_gmail=True,
        )
    except Exception as e:  # noqa: BLE001 — tệp hỏng / quá lớn ⇒ ghép tay
        logger.warning("gmail_tu_ghep_loi", drive_tep_id=dong_id, loai=type(e).__name__)
        await pool.execute(
            "UPDATE drive_tep SET ly_do_cho = 'LOI_TEP' WHERE clinic_id = $1::uuid"
            " AND id = $2::uuid AND tep_ket_qua_id IS NULL AND tu_choi_luc IS NULL",
            cid,
            dong_id,
        )
        return False
    await pool.execute(
        "UPDATE drive_tep SET tep_ket_qua_id = $3::uuid, ghep_luc = now()"
        " WHERE clinic_id = $1::uuid AND id = $2::uuid"
        "   AND tep_ket_qua_id IS NULL AND tu_choi_luc IS NULL",
        cid,
        dong_id,
        str(kq["id"]),
    )
    await drive._phat_den(
        pool, cid, drive.Quyet(q.order_id, q.clinic_patient_id, q.visit_id, None)
    )
    return True
