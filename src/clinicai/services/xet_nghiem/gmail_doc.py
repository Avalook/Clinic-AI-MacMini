"""Đọc thư kết quả Gmail từng phòng xét nghiệm — HÀM THUẦN (Gmail G3).

Luật lấy từ phân tích thư thật 4 lab (09/11/2026, kế hoạch mục G3 "đề xuất chỉnh luật",
Tuyền duyệt). Nhận ra kiểu thư bằng TIÊU ĐỀ (không bằng tên đối tác — đối tác đặt tên
gì cũng được):

- TM (True Medicine): tên tiêu đề · SĐT trong PDF theo nhãn `SĐT:` / `Số điện
  thoại:` · năm sinh ở thân `NS:`.
- GLHD (Greenlab, High Detect): tên tiêu đề · SĐT tiêu đề `- 0xxxxxxxxx` (hỏng ⇒ PDF
  theo nhãn) · năm sinh PDF `Năm sinh:` / `NS:`.
- EU (Eurofins): tên tiêu đề · SĐT trong PDF không nhãn, CHỈ khi có đúng một số di
  động · năm sinh = ngày dd/mm/yyyy trong PDF có năm ≤ năm nay − 14.

Không dùng mã xét nghiệm trong tên tệp (True Medicine ghi sai loại) và không ghép theo
mã mẫu của lab (có mã dùng lại cho người khác). Greenlab trả từng phần: thư
`Trạng thái : Chưa đủ kết quả` KHÔNG tự ghép. Rác / không khớp mẫu ⇒ None, không ném.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from clinicai.services.xet_nghiem.ghep_khach import chuan, chuan_sdt, sdt_trong

_TRA_LOI: Final = r"^(?:(?:Trả lời|RE|FW|FWD|TR)\s*:\s*)*"
_TM_RE: Final = re.compile(
    _TRA_LOI + r"Kết quả xét nghiệm:\s*(?P<ten>.+?)\s*-\s*Ngày xét nghiệm", re.I
)
_GLHD_RE: Final = re.compile(
    _TRA_LOI
    + r"KQ xét nghiệm KH\s+(?P<ten>.+?)\s*\(SID:\s*[\d-]+\)\s*-\s*(?P<sdt>.*)$",
    re.I,
)
_EU_RE: Final = re.compile(
    _TRA_LOI
    + r"KẾT QUẢ\s+(?:GEN LẶN\s+)?(?:NIP\d{7}(?:CCL)?|Y\d{7})\s*-\s*(?P<ten>.+)$",
    re.I,
)
_NS_THAN_RE: Final = re.compile(r"\bNS:\s*(\d{4})\b")
_NS_PDF_RE: Final = re.compile(r"(?:Năm sinh|\bNS)\s*:\s*(\d{4})\b")
_NGAY_RE: Final = re.compile(r"\b\d{2}/\d{2}/(\d{4})\b")
_SDT_NHAN_RE: Final = re.compile(
    r"(?:SĐT|Số điện thoại|Điện thoại)\s*:\s*((?:\+?84|0)(?:[\s.\-]?\d){9})"
)
_CHUA_DU_RE: Final = re.compile(r"Trạng thái\s*:\s*Chưa đủ kết quả", re.I)
#: Eurofins `NIP1234567.pdf` (không có tên) là phiếu mã vạch / FF, không phải kết quả.
_PHIEU_EU_RE: Final = re.compile(r"^NIP\d{7}\.pdf$", re.I)


#: Loại xét nghiệm (G7, Tuyền 11/11): từ khoá (đã bỏ dấu, chữ thường, nguyên từ). Đo 60
#: PDF Tâm Minh: 32 chỉ STD, 27 chỉ HPV, 1 cả ba ⇒ đủ tách HPV / STD của cùng khách.
#: (Danh sách, không tuple một phần tử: chốt cú pháp SQL
#: `test_sql_trong_service_cu_phap_dung` đọc dấu phẩy trước ngoặc đóng là SQL nối hụt.)
_LOAI_KQ: Final = {
    "HPV": ["hpv", "papilloma"],
    "STD": ["chlamydia", "neisseria", "trichomonas", "mycoplasma", "ureaplasma",
            "treponema", "giang mai", "herpes", "hsv", "gardnerella", "lau cau",
            "13 tac nhan", "std"],
    "THINPREP": ["thinprep", "thin prep", "te bao hoc", "bethesda", "pap smear"],
    "NIPT": ["nipt"],
    "GEN": ["gen lan", "carrier"],
}  # fmt: skip
#: Loại theo TÊN DỊCH VỤ (chỉ định). Không khớp gì (vd "Xét nghiệm máu") ⇒ rỗng.
_LOAI_DV: Final = {
    "HPV": ["hpv"],
    "STD": ["std", "benh lay"],
    "THINPREP": ["thinprep"],
    "NIPT": ["nipt"],
    "GEN": ["gen"],
}


def _co_tu(van: str, bang: dict[str, list[str]]) -> frozenset[str]:
    s = f" {chuan(van)} "
    return frozenset(
        loai for loai, tu in bang.items() if any(f" {t} " in s for t in tu)
    )


#: HPV hay viết dính số / dạng dài ("HPV16/18" ⇒ "hpv16 18", "papillomavirus") — thiếu
#: thì tờ HPV có một chữ STD lạc vào bị đọc thành CHỈ STD ⇒ gán nhầm (soát G7).
_HPV_DINH: Final = re.compile(r" (?:hpv\d+|papillomavirus|papillomaviruses) ")


def loai_ket_qua(chu: object) -> frozenset[str]:
    """HÀM THUẦN: loại xét nghiệm nhắc trong chữ PDF kết quả. Rác ⇒ rỗng."""
    if not isinstance(chu, str):
        return frozenset()
    loai = _co_tu(chu, _LOAI_KQ)
    if _HPV_DINH.search(f" {chuan(chu)} "):
        loai |= {"HPV"}
    return loai


def loai_dich_vu(ten: object) -> frozenset[str]:
    """HÀM THUẦN: loại xét nghiệm của một chỉ định theo tên dịch vụ ("Combo HPV 40 +
    thinprep" ⇒ HPV + THINPREP). Không nhận ra ⇒ rỗng (không dùng để loại)."""
    return _co_tu(ten, _LOAI_DV) if isinstance(ten, str) else frozenset()


@dataclass(frozen=True)
class DocThu:
    kieu: str  # "TM" | "GLHD" | "EU" | "" (không nhận ra ⇒ không tự ghép)
    ten: str | None
    sdt: str | None
    nam_sinh: int | None
    #: Vì sao thư nhận ra được mà KHÔNG được tự ghép (mã `drive_tep.luu_tru_vi_sao`):
    #: CHUA_DU_KET_QUA (Greenlab trả từng phần) · PHIEU_MA_VACH (Eurofins). None = được.
    khong_tu_ghep: str | None = None
    #: Loại xét nghiệm đọc được trong CHỮ PDF (không theo tên tệp — True Medicine ghi
    #: sai loại ở tên tệp). Rỗng = không biết ⇒ không dùng để chọn chỉ định.
    loai: frozenset[str] = frozenset()

    @property
    def tu_ghep_duoc(self) -> bool:
        return bool(self.kieu) and self.khong_tu_ghep is None


def kieu_thu(tieu_de: object) -> tuple[str, str | None, str | None]:
    """(kiểu, tên, SĐT ở tiêu đề) từ tiêu đề. Không khớp ⇒ ("", None, None)."""
    s = " ".join(tieu_de.split()) if isinstance(tieu_de, str) else ""
    if m := _TM_RE.match(s):
        return "TM", _ten(m["ten"]), None
    if m := _GLHD_RE.match(s):
        return "GLHD", _ten(m["ten"]), chuan_sdt(m["sdt"])
    if m := _EU_RE.match(s):
        return "EU", _ten(m["ten"]), None
    return "", None, None


def _ten(s: str) -> str | None:
    s = " ".join(s.replace(".", " ").split()).strip(" -")
    return s if 2 <= len(s) <= 120 else None


def _mot(gia_tri: set[str]) -> str | None:
    return next(iter(gia_tri)) if len(gia_tri) == 1 else None


def sdt_theo_nhan(chu_pdf: str) -> str | None:
    """SĐT theo nhãn `SĐT:` / `Số điện thoại:` — đúng MỘT số khác nhau, không thì None
    (dòng `Hotline:` của lab không có nhãn này)."""
    return _mot({x for m in _SDT_NHAN_RE.findall(chu_pdf or "") if (x := chuan_sdt(m))})


def nam_sinh(s: object) -> int | None:
    try:
        n = int(str(s))
    except (TypeError, ValueError):
        return None
    return n if 1900 <= n <= 2100 else None


def ns_eu(chu_pdf: str, nam_nay: int) -> int | None:
    """Eurofins: nhãn `Ngày sinh:` rỗng; ngày sinh là ngày dd/mm/yyyy có năm ≤ nay−14
    (ngày lấy / nhận mẫu là năm nay). Đúng một năm khác nhau, không thì None."""
    nam = {
        n
        for m in _NGAY_RE.findall(chu_pdf or "")
        if (n := nam_sinh(m)) is not None and n <= nam_nay - 14
    }
    return next(iter(nam)) if len(nam) == 1 else None


def doc_thu(
    tieu_de: object,
    than: object,
    ten_tep: object,
    chu_pdf: object,
    nam_nay: int,
) -> DocThu:
    """HÀM THUẦN: một PDF của một thư ⇒ tên / SĐT / năm sinh theo luật của kiểu thư."""
    kieu, ten, sdt_td = kieu_thu(tieu_de)
    than_s = than if isinstance(than, str) else ""
    chu = chu_pdf if isinstance(chu_pdf, str) else ""
    tep = ten_tep if isinstance(ten_tep, str) else ""
    khong: str | None = None
    sdt: str | None = None
    ns: int | None = None
    if kieu == "TM":
        sdt = sdt_theo_nhan(chu)
        m = _NS_THAN_RE.search(than_s)
        ns = nam_sinh(m.group(1)) if m else None
    elif kieu == "GLHD":
        sdt = sdt_td or sdt_theo_nhan(chu)
        ns = _mot_nam({nam_sinh(x) for x in _NS_PDF_RE.findall(chu)})
        if _CHUA_DU_RE.search(than_s):
            khong = "CHUA_DU_KET_QUA"  # kết quả từng phần — bản "Đủ kết quả" về sau
    elif kieu == "EU":
        sdt = _mot(sdt_trong(chu))
        ns = ns_eu(chu, nam_nay)
        if _PHIEU_EU_RE.match(tep.strip()):
            khong = "PHIEU_MA_VACH"  # phiếu mã vạch, không phải kết quả
    return DocThu(
        kieu=kieu,
        ten=ten,
        sdt=sdt,
        nam_sinh=ns,
        khong_tu_ghep=khong,
        loai=loai_ket_qua(chu),
    )


def _mot_nam(nam: set[int | None]) -> int | None:
    co = {n for n in nam if n is not None}
    return next(iter(co)) if len(co) == 1 else None


def xac_thuc_ok(ket_qua_xac_thuc: object, tu: object) -> bool:
    """Header `Authentication-Results` của Gmail: thư thật từ miền người gửi?
    DMARC pass, hoặc DKIM pass với `header.d` / `header.i` đúng miền người gửi.
    Không có header / rác ⇒ False (thư giả mạo người gửi không được TỰ ghép).

    Chỉ tin header do CHÍNH Gmail ghi (authserv-id `mx.google.com`, dòng trên cùng —
    `gmail_api` chỉ giữ dòng đó): người gửi tự chèn được thêm header cùng tên. Mỗi kết
    quả (`;`) xét riêng: `dmarc=pass` phải kèm `header.from=` đúng miền; `dkim=pass`
    phải kèm `header.d=` / `header.i=@` đúng miền; `spf=pass` phải kèm `smtp.mailfrom`
    cùng miền (SPF "khớp miền" như DMARC nhận) — so NGUYÊN miền, không so tiền tố
    (`lab.vn.ke-gian.com` không phải `lab.vn`).

    SPF (11/11/2026, đo prod): HighDetect gửi qua Google Workspace KHÔNG cài DKIM riêng
    (chữ ký mang miền `…gappssmtp.com`) và không khai DMARC ⇒ chỉ SPF chứng được miền;
    luật cũ xếp oan mọi thư máu vào Lưu trữ "không xác thực"."""
    if (
        not isinstance(ket_qua_xac_thuc, str)
        or not isinstance(tu, str)
        or "@" not in tu
    ):
        return False
    mien = tu.rsplit("@", 1)[1].strip().lower()
    # Bỏ chú thích "(...)" của RFC 8601 (spf=pass (google.com: ...) smtp.mailfrom=...).
    h = re.sub(r"\([^()]*\)", " ", ket_qua_xac_thuc.lower())
    dau, *cac = h.split(";")
    if dau.strip() != "mx.google.com" or not mien:
        return False
    for kq in cac:
        the = {k: v for k, _, v in (x.partition("=") for x in kq.split()) if k and v}
        if the.get("dmarc") == "pass" and the.get("header.from") == mien:
            return True
        i = the.get("header.i", "")
        if the.get("dkim") == "pass" and (
            the.get("header.d") == mien or ("@" in i and i.rsplit("@", 1)[1] == mien)
        ):
            return True
        mf = the.get("smtp.mailfrom", "")
        if the.get("spf") == "pass" and mf.rsplit("@", 1)[-1] == mien:
            return True
    return False
