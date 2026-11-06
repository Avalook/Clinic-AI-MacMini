"""Ghép tệp kết quả Drive theo TÊN + SĐT khách đọc trong PDF (Tuyền chốt 05/11/2026).

Mã ống là mã nội bộ phòng khám — đối tác không biết để ghi vào tên tệp. Nên: đọc chữ
trong PDF (và tên tệp), tìm SĐT khách VÀ tên khách (bỏ dấu, không phân hoa thường) của
những việc đối tác này đang chờ kết quả. Ghép tự động CHỈ khi khớp đúng MỘT khách có
đúng MỘT việc chờ; còn lại (không đọc được chữ — PDF scan, không ai khớp, hai khách
cùng khớp, một khách hai việc chờ) ⇒ hàng "chưa khớp", người bấm Gán. Không đoán.

Đọc PDF bằng `pypdf` trên máy chủ — nội dung kết quả không gửi đi đâu.
"""

from __future__ import annotations

import io
import re
import unicodedata
from dataclasses import dataclass
from typing import Final

import asyncpg
import structlog

from clinicai.core.tran import canh_bao_neu_day

logger = structlog.get_logger()

#: Chỉ đọc vài trang đầu (họ tên + SĐT ở đầu phiếu) — tệp dài không làm chậm vòng quét.
TRAN_TRANG: Final = 5
TRAN_UNG_VIEN: Final = 500
_SDT_RE: Final = re.compile(r"(?<!\d)(?:\+?84|0)(?:[\s.\-]?\d){9}(?!\d)")


def chuan(s: object) -> str:
    """Bỏ dấu, chữ thường, chỉ giữ chữ/số, một dấu cách. Rác ⇒ ""."""
    if not isinstance(s, str):
        return ""
    s = s.replace("đ", "d").replace("Đ", "D")
    s = "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )
    return " ".join(re.sub(r"[^0-9a-z]+", " ", s.lower()).split())


def chuan_sdt(s: object) -> str | None:
    """SĐT VN về dạng 0xxxxxxxxx (10 số). Rác ⇒ None."""
    if not isinstance(s, str):
        return None
    so = re.sub(r"\D", "", s)
    if so.startswith("84") and len(so) == 11:
        so = "0" + so[2:]
    return so if len(so) == 10 and so.startswith("0") else None


def sdt_trong(van_ban: str) -> set[str]:
    return {x for m in _SDT_RE.findall(van_ban or "") if (x := chuan_sdt(m))}


def chu_pdf(data: bytes) -> str:
    """Chữ của vài trang đầu PDF. PDF scan / hỏng / không phải PDF ⇒ "" (không ném)."""
    if not data.startswith(b"%PDF"):
        return ""
    try:
        from pypdf import PdfReader

        doc = PdfReader(io.BytesIO(data))
        return "\n".join((p.extract_text() or "") for p in doc.pages[:TRAN_TRANG])
    except Exception:  # noqa: BLE001 — PDF lạ/hỏng ⇒ coi như không đọc được chữ
        logger.info("drive_pdf_khong_doc_duoc")
        return ""


@dataclass(frozen=True)
class UngVien:
    order_id: str
    clinic_patient_id: str
    visit_id: str | None
    ten: str | None
    sdt: str | None


def khop_khach(
    van_ban: str, ung_vien: list[UngVien]
) -> tuple[UngVien | None, str | None]:
    """HÀM THUẦN. `van_ban` = tên tệp + chữ PDF (thô). Trả (việc ghép, None) hoặc
    (None, lý do chờ): KHONG_DOC_DUOC · KHONG_KHOP_KHACH · NHIEU_KHACH ·
    ONG_NHIEU_VIEC."""
    chu = f" {chuan(van_ban)} "
    if not chu.strip():
        return None, "KHONG_DOC_DUOC"
    sdts = sdt_trong(van_ban)
    khop = [
        u
        for u in ung_vien
        if (s := chuan_sdt(u.sdt)) in sdts
        and s is not None
        and (ten := chuan(u.ten))
        and f" {ten} " in chu
    ]
    if not khop:
        return None, "KHONG_KHOP_KHACH"
    if len({u.clinic_patient_id for u in khop}) > 1:
        return None, "NHIEU_KHACH"
    if len(khop) > 1:
        return None, "ONG_NHIEU_VIEC"
    return khop[0], None


_UNG_VIEN_SQL = """
SELECT o.id::text AS order_id, v.clinic_patient_id::text AS clinic_patient_id,
       o.visit_id::text AS visit_id, p.full_name AS ten, p.phone_primary AS sdt
  FROM xet_nghiem_viec x
  JOIN service_order o ON o.id = x.service_order_id AND o.clinic_id = x.clinic_id
  JOIN visit v ON v.visit_id = o.visit_id AND v.clinic_id = o.clinic_id
  JOIN patient p
    ON p.clinic_patient_id = v.clinic_patient_id AND p.clinic_id = v.clinic_id
 WHERE x.clinic_id = $1::uuid AND x.doi_tac_id = $2::uuid
   AND o.exec_status <> 'cancelled'
   AND x.tao_luc > now() - interval '120 days'
   -- Đang chờ kết quả = đã lấy mẫu (ống còn hiệu lực), chưa có tờ còn hiệu lực.
   AND EXISTS (SELECT 1 FROM mau_xet_nghiem_viec mv
                JOIN mau_xet_nghiem m ON m.id = mv.mau_id AND m.huy_luc IS NULL
               WHERE mv.clinic_id = x.clinic_id AND mv.service_order_id = o.id
                 AND mv.go_luc IS NULL)
   AND NOT EXISTS (SELECT 1 FROM tep_ket_qua k
                    WHERE k.clinic_id = x.clinic_id AND k.service_order_id = o.id
                      AND k.da_xoa_luc IS NULL
                      AND coalesce(k.xac_nhan_trang_thai, '')
                          NOT IN ('TU_CHOI', 'THU_HOI'))
 LIMIT 500
"""


async def doc_ung_vien(
    conn: asyncpg.Connection, cid: str, doi_tac_id: str
) -> list[UngVien]:
    rows = await conn.fetch(_UNG_VIEN_SQL, cid, doi_tac_id)
    canh_bao_neu_day("xet_nghiem_viec", len(rows), TRAN_UNG_VIEN, clinic_id=cid)
    return [UngVien(**dict(r)) for r in rows]
