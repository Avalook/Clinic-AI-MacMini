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
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Protocol, TypeVar

import asyncpg
import structlog

from clinicai.core.tran import canh_bao_neu_day

logger = structlog.get_logger()

#: Chỉ đọc vài trang đầu (họ tên + SĐT ở đầu phiếu) — tệp dài không làm chậm vòng quét.
TRAN_TRANG: Final = 5
TRAN_UNG_VIEN: Final = 2000
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
    """Một việc của đối tác + khách của nó. `da_lay_mau`/`co_tep` cho biết việc có
    đang CHỜ kết quả (Drive chỉ xét việc đang chờ; Gmail dùng cả việc khác để gợi ý)."""

    order_id: str
    clinic_patient_id: str
    visit_id: str | None
    ten: str | None
    sdt: str | None
    nam_sinh: int | None = None
    da_lay_mau: bool = True
    co_tep: bool = False
    #: Giờ nhận thư nguồn của tờ còn hiệu lực MỚI NHẤT đến từ GMAIL. None = không có
    #: tờ nào từ Gmail (có thể vẫn có tờ tải tay — `co_tep`). Chỉ `doc_chi_dinh` điền.
    tep_gmail_luc: datetime | None = None

    @property
    def dang_cho(self) -> bool:
        return self.da_lay_mau and not self.co_tep


class _CoTenSdt(Protocol):
    @property
    def ten(self) -> str | None: ...
    @property
    def sdt(self) -> str | None: ...


_K = TypeVar("_K", bound=_CoTenSdt)


def khop_ds(van_ban: str, ung_vien: Sequence[_K]) -> list[_K]:
    """HÀM THUẦN — LUẬT KHỚP DUY NHẤT (Drive + Gmail): ứng viên có SĐT nằm trong chữ
    VÀ tên (bỏ dấu, nguyên cụm) nằm trong chữ."""
    chu = f" {chuan(van_ban)} "
    sdts = sdt_trong(van_ban)
    return [
        u
        for u in ung_vien
        if (s := chuan_sdt(u.sdt)) in sdts
        and s is not None
        and (ten := chuan(u.ten))
        and f" {ten} " in chu
    ]


def khop_khach(
    van_ban: str, ung_vien: list[UngVien]
) -> tuple[UngVien | None, str | None]:
    """HÀM THUẦN. `van_ban` = tên tệp + chữ PDF (thô). Trả (việc ghép, None) hoặc
    (None, lý do chờ): KHONG_DOC_DUOC · KHONG_KHOP_KHACH · NHIEU_KHACH ·
    ONG_NHIEU_VIEC."""
    if not chuan(van_ban):
        return None, "KHONG_DOC_DUOC"
    khop = khop_ds(van_ban, ung_vien)
    if not khop:
        return None, "KHONG_KHOP_KHACH"
    if len({u.clinic_patient_id for u in khop}) > 1:
        return None, "NHIEU_KHACH"
    if len(khop) > 1:
        return None, "ONG_NHIEU_VIEC"
    return khop[0], None


#: MỌI việc đối tác này trong 120 ngày — MỘT câu cho Drive + Gmail. Đã lấy mẫu = ống
#: còn hiệu lực; có tệp = tờ còn hiệu lực. Mới nhất trước: chạm trần thì sót việc cũ.
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
 ORDER BY x.tao_luc DESC
 LIMIT 2000
"""


async def doc_viec(
    conn: asyncpg.Connection, cid: str, doi_tac_id: str
) -> list[UngVien]:
    rows = await conn.fetch(_VIEC_SQL, cid, doi_tac_id)
    # Chạm trần ⇒ có thể sót đúng việc: báo (luật cắt không im lặng).
    canh_bao_neu_day("xet_nghiem_viec", len(rows), TRAN_UNG_VIEN, clinic_id=cid)
    return [UngVien(**dict(r)) for r in rows]


async def doc_ung_vien(
    conn: asyncpg.Connection, cid: str, doi_tac_id: str
) -> list[UngVien]:
    """Việc đang CHỜ kết quả (Drive chỉ tự ghép vào đây)."""
    return [u for u in await doc_viec(conn, cid, doi_tac_id) if u.dang_cho]


#: Gmail G5 (Tuyền 11/11): MỌI chỉ định loại xét nghiệm lab này làm — việc Bàn XN chụp
#: đúng lab này, hoặc chỉ định chưa có việc mà dịch vụ được gán cho lab này ở Cài đặt →
#: Đối tác (chỉ định cũ trước khi gán vẫn được) — tạo trong 60 ngày TRƯỚC giờ nhận thư
#: ($3). Không cần Lấy mẫu. Việc Bàn XN đã chụp lab KHÁC thì không phải của lab này.
_CHI_DINH_SQL = """
SELECT o.id::text AS order_id, v.clinic_patient_id::text AS clinic_patient_id,
       o.visit_id::text AS visit_id, p.full_name AS ten, p.phone_primary AS sdt,
       coalesce(p.birth_year::int, extract(year FROM p.date_of_birth)::int)
           AS nam_sinh,
       t.so > 0 AS co_tep, t.gmail_luc AS tep_gmail_luc
  FROM service_order o
  JOIN visit v ON v.visit_id = o.visit_id AND v.clinic_id = o.clinic_id
  JOIN patient p
    ON p.clinic_patient_id = v.clinic_patient_id AND p.clinic_id = v.clinic_id
  LEFT JOIN xet_nghiem_viec x
    ON x.clinic_id = o.clinic_id AND x.service_order_id = o.id
  LEFT JOIN LATERAL (
       SELECT count(*) AS so,
              max((SELECT max(d.email_nhan_luc) FROM drive_tep d
                    WHERE d.clinic_id = k.clinic_id AND d.tep_ket_qua_id = k.id
                      AND d.nguon = 'GMAIL')) AS gmail_luc
         FROM tep_ket_qua k
        WHERE k.clinic_id = o.clinic_id AND k.service_order_id = o.id
          AND k.da_xoa_luc IS NULL
          AND coalesce(k.xac_nhan_trang_thai, '') NOT IN ('TU_CHOI', 'THU_HOI')
  ) t ON true
 WHERE o.clinic_id = $1::uuid
   AND o.exec_status NOT IN ('draft', 'cancelled')
   AND o.created_at <= $3 AND o.created_at > $3 - interval '60 days'
   AND (x.doi_tac_id = $2::uuid
        OR (x.service_order_id IS NULL AND EXISTS (
            SELECT 1 FROM service_price sp
              JOIN doi_tac_dich_vu a
                ON a.clinic_id = sp.clinic_id AND a.service_price_id = sp.id
               AND a.doi_tac_id = $2::uuid AND a.ngung_luc IS NULL
             WHERE sp.clinic_id = o.clinic_id AND sp."group" = 'dich_vu'
               AND sp.service_code = o.service_code)))
 ORDER BY o.created_at DESC
 LIMIT 2000
"""


async def doc_chi_dinh(
    conn: asyncpg.Connection, cid: str, doi_tac_id: str, truoc: datetime
) -> list[UngVien]:
    """Chỉ định ứng viên cho MỘT thư Gmail của lab `doi_tac_id` nhận lúc `truoc`."""
    rows = await conn.fetch(_CHI_DINH_SQL, cid, doi_tac_id, truoc)
    canh_bao_neu_day("service_order", len(rows), TRAN_UNG_VIEN, clinic_id=cid)
    return [UngVien(**dict(r)) for r in rows]
