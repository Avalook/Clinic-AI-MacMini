"""Cách dùng có cấu trúc: câu in trên đơn, liều/ngày, số ngày dùng, ngày hết, gợi ý SL.

Kế hoạch `docs/KE-HOACH-DON-VI-ME-CON-CACH-DUNG.md` mục 2, 4, 5, 6, 10 (PR E). Hàm
thuần — màn kê đơn chỉ hiển thị kết quả, không tự tính. Theo đúng hành vi trang giả
lập Tuyền đã duyệt (26/11): `tinhNgay`, `goiYSoLuong`, `cauCachDung`.

Luật Tuyền chốt:
- Thuốc bôi / xịt / nhát / phần gói / thước đo, dùng một lần, khi cần, theo chỉ định →
  kiểu "chu" (chỉ ghi chữ), KHÔNG tính ngày.
- Danh mục lưu KHOẢNG ("1–2 lần"); bác sĩ phải chọn một số khi kê — chưa chọn thì
  không tính (không lấy cận dưới/trên thay bác sĩ).
- Thiếu "1 [đơn vị kho] có bao nhiêu [viên]" → trả lý do, không đoán.
- Chu kỳ kinh: luôn báo số ngày (Y−X+1); ngày lịch chỉ ƯỚC TÍNH khi có kinh lần cuối +
  chu kỳ. Ô kinh lần cuối là chữ tự do → đọc không ra thì bỏ qua, không ném.
"""

from __future__ import annotations

import math
import re
from datetime import date, timedelta
from decimal import Decimal
from fractions import Fraction
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from clinicai.services.thai_ky_service import doc_ngay_tu_do

Kieu = Literal["ngay", "tuan", "cach_ngay", "chu_ky", "chu"]
CHU_KY_MIN, CHU_KY_MAX = 15, 60
SO_NGAY_TOI_DA = 3660

LY_DO_CHU = "Chỉ ghi chữ — không tính ngày."
LY_DO_KHOANG = "Cách dùng có khoảng — chọn một số để máy tính ngày."
LY_DO_THIEU_LIEU = "Thiếu liều mỗi lần / số lần."
LY_DO_NGOAI_DANH_MUC = "Thuốc ngoài danh mục — chỉ ghi chữ, không tính ngày."


class CachDung(BaseModel):
    """Một cách dùng: mặc định ở danh mục, bản chụp trên dòng đơn (`cach_dung_ct`)."""

    model_config = ConfigDict(extra="ignore")

    kieu: Kieu = "chu"
    #: Mỗi lần bao nhiêu (cho số lẻ 0,5). None = chưa chọn (khi có khoảng).
    moi_lan: Decimal | None = Field(default=None, gt=0, le=100)
    khoang_lan: tuple[Decimal, Decimal] | None = None
    #: Số lần mỗi ngày (kiểu ngày / chu kỳ) hoặc mỗi tuần (kiểu tuần).
    so_lan: int | None = Field(default=None, ge=1, le=24)
    khoang_so_lan: tuple[int, int] | None = None
    #: Chu kỳ kinh: từ ngày X đến ngày Y.
    tu_ngay: int | None = Field(default=None, ge=1, le=60)
    den_ngay: int | None = Field(default=None, ge=1, le=60)
    #: "trong N ngày" (tuỳ chọn) — dùng để gợi ý số lượng.
    trong_ngay: int | None = Field(default=None, ge=1, le=366)
    don_vi_lieu: str = Field(default="viên", min_length=1, max_length=20)
    #: Phần chữ thêm vào câu: thời điểm, lưu ý ngắn ("sau ăn tối").
    thoi_diem: str = Field(default="", max_length=300)

    @model_validator(mode="after")
    def _trong_khoang(self) -> CachDung:
        for gt, kh, ten in (
            (self.moi_lan, self.khoang_lan, "Mỗi lần"),
            (self.so_lan, self.khoang_so_lan, "Số lần"),
        ):
            if kh is None:
                continue
            if kh[0] <= 0 or kh[0] > kh[1]:
                raise ValueError(f"{ten}: khoảng không hợp lệ.")
            if gt is not None and not kh[0] <= gt <= kh[1]:
                khoang = f"{_so_lieu_chu(kh[0])}–{_so_lieu_chu(kh[1])}"
                raise ValueError(f"{ten} phải chọn trong khoảng {khoang}.")
        return self


def doc_ct(v: Any) -> CachDung | None:
    """jsonb đã lưu → CachDung; hỏng/rỗng thì None (không ném — dữ liệu cũ, tay sửa)."""
    if v is None or v == "":
        return None
    try:
        if isinstance(v, str):
            return CachDung.model_validate_json(v)
        return CachDung.model_validate(v)
    except (ValidationError, ValueError):
        return None


def _so_lieu_chu(x: Decimal | Fraction | int | float) -> str:
    """1 → "1", 0.5 → "0,5", 1.25 → "1,25" (kiểu Việt)."""
    d = (
        Decimal(x.numerator) / Decimal(x.denominator)
        if isinstance(x, Fraction)
        else Decimal(x)
    )
    s = format(d.quantize(Decimal("0.01")).normalize(), "f")
    return s.replace(".", ",")


def _chon(gt: Any, kh: Any) -> str:
    if gt is not None:
        return _so_lieu_chu(gt)
    return f"{_so_lieu_chu(kh[0])}–{_so_lieu_chu(kh[1])}" if kh else "?"


def chua_chon_khoang(ct: CachDung) -> bool:
    return (ct.khoang_lan is not None and ct.moi_lan is None) or (
        ct.khoang_so_lan is not None and ct.so_lan is None and ct.kieu != "cach_ngay"
    )


def cau_cach_dung(ct: CachDung | None, chu_cu: str = "") -> str:
    """Câu in trên đơn. Kiểu "chu" giữ nguyên chữ bác sĩ/danh mục."""
    if ct is None or ct.kieu == "chu":
        return chu_cu.strip()
    lan = _chon(ct.so_lan, ct.khoang_so_lan)
    moi = f"mỗi lần {_chon(ct.moi_lan, ct.khoang_lan)} {ct.don_vi_lieu}"
    dau = {
        "ngay": f"Ngày {lan} lần",
        "tuan": f"Tuần {lan} lần",
        "cach_ngay": "Cách ngày 1 lần",
        "chu_ky": f"Ngày {lan} lần, từ ngày {ct.tu_ngay or '?'} đến ngày "
        f"{ct.den_ngay or '?'} chu kỳ kinh",
    }[ct.kieu]
    cau = f"{dau}, {moi}"
    if ct.trong_ngay and ct.kieu != "chu_ky":
        cau += f", trong {ct.trong_ngay} ngày"
    them = ct.thoi_diem.strip().rstrip(".")
    return f"{cau}. {them[:1].upper()}{them[1:]}." if them else f"{cau}."


def lieu_ngay(ct: CachDung) -> Fraction | None:
    """Số đơn vị liều mỗi ngày (tuần chia 7, cách ngày chia 2). None = chưa đủ ô."""
    if ct.kieu == "chu" or ct.moi_lan is None or chua_chon_khoang(ct):
        return None
    m = Fraction(ct.moi_lan)
    if ct.kieu == "cach_ngay":
        return m / 2
    if ct.so_lan is None:
        return None
    if ct.kieu == "tuan":
        return m * ct.so_lan / 7
    return m * ct.so_lan


def so_luong_so(chu: Any) -> Fraction | None:
    """ "30", "1,5", "2 viên" → số; "1/2", "uống đến hết", "0", rác → None (không đoán).

    Cùng luật `public.so_luong_tu_van_ban` / `soLuongTuChu`."""
    m = re.match(r"^\s*([0-9]+(?:[.,][0-9]+)?)\s*(?:$|[^0-9/.,].*$)", str(chu or ""))
    if not m:
        return None
    n = Fraction(Decimal(m.group(1).replace(",", ".")))
    return n if n > 0 else None


def goi_y_so_luong(
    lieu: Fraction, so_ngay: int, lieu_moi_kho: Fraction, he_so: Fraction
) -> int:
    """Số lượng (theo đơn vị đang chọn) đủ dùng `so_ngay` ngày — làm tròn LÊN."""
    can = math.ceil(lieu * so_ngay)
    return math.ceil(Fraction(can) / (lieu_moi_kho * he_so))


def doc_ngay_kinh(chu: Any, ngay_ke: date) -> date | None:
    """Ô "Kinh lần cuối" là chữ tự do — đọc bằng CÙNG hàm của thai kỳ (`sk_lmp`).

    Đọc không ra / ngày không có thật ("31/02") / sau ngày kê → None. Không ném."""
    d = doc_ngay_tu_do(chu)
    return d if d is not None and d <= ngay_ke else None


def doc_chu_ky(chu: Any) -> int | None:
    m = re.fullmatch(r"\s*(\d{1,3})\s*(?:ngày)?\s*", str(chu or ""))
    if not m:
        return None
    n = int(m[1])
    return n if CHU_KY_MIN <= n <= CHU_KY_MAX else None


def uoc_tinh_chu_ky(
    lmp: date, chu_ky: int, tu_ngay: int, den_ngay: int, ngay_ke: date
) -> dict[str, date]:
    """Kinh tới = kinh lần cuối + k×chu kỳ (lần đầu không trước ngày kê)."""
    k = max(0, math.ceil((ngay_ke - lmp).days / chu_ky))
    toi = lmp + timedelta(days=k * chu_ky)
    return {
        "kinh_toi": toi,
        "bat_dau": toi + timedelta(days=tu_ngay - 1),
        "het": toi + timedelta(days=den_ngay - 1),
    }


def tinh_dong(
    ct: CachDung | None,
    *,
    so_luong: Any,
    he_so: Fraction | None,
    lieu_moi_kho: Fraction | None,
    don_vi_kho: str,
    ngay_ke: date,
    kinh: tuple[date, int] | None = None,
) -> dict[str, Any]:
    """Một dòng đơn → số ngày / ngày hết / gợi ý SL hoặc lý do không tính.

    `he_so`: 1 [đơn vị dòng] = bao nhiêu [đơn vị kho]; `lieu_moi_kho`: 1 [đơn vị kho] =
    bao nhiêu [đơn vị liều]. None = chưa khai (máy không đoán)."""
    kq: dict[str, Any] = {
        "tinh_duoc": False,
        "ly_do": None,
        "lieu_ngay": None,
        "so_ngay": None,
        "ngay_het": None,
        "goi_y_so_luong": None,
        "uoc_tinh": None,
        "so_lieu_can": None,
    }
    if ct is None or ct.kieu == "chu":
        return {**kq, "ly_do": LY_DO_CHU}
    if chua_chon_khoang(ct):
        return {**kq, "ly_do": LY_DO_KHOANG}
    lieu = lieu_ngay(ct)
    if lieu is None or lieu <= 0:
        return {**kq, "ly_do": LY_DO_THIEU_LIEU}
    kq["lieu_ngay"] = _so_lieu_chu(lieu)
    du_quy_doi = he_so is not None and lieu_moi_kho is not None
    if ct.kieu == "chu_ky":
        if not ct.tu_ngay or not ct.den_ngay or ct.tu_ngay > ct.den_ngay:
            return {**kq, "ly_do": "Nhập từ ngày → đến ngày của chu kỳ kinh."}
        so = ct.den_ngay - ct.tu_ngay + 1
        kq.update(tinh_duoc=True, so_ngay=so, so_lieu_can=_so_lieu_chu(lieu * so))
        if du_quy_doi:
            assert he_so is not None and lieu_moi_kho is not None
            kq["goi_y_so_luong"] = goi_y_so_luong(lieu, so, lieu_moi_kho, he_so)
        if kinh is not None:
            kq["uoc_tinh"] = uoc_tinh_chu_ky(
                kinh[0], kinh[1], ct.tu_ngay, ct.den_ngay, ngay_ke
            )
        return kq
    if lieu_moi_kho is None:
        return {
            **kq,
            "ly_do": f"Chưa khai 1 {don_vi_kho or 'đơn vị kho'} có bao nhiêu "
            f"{ct.don_vi_lieu} — khai ở Kho thuốc › Danh mục.",
        }
    if he_so is None:
        return {**kq, "ly_do": "Đơn vị của dòng chưa khai quy đổi về đơn vị kho."}
    if ct.trong_ngay:
        kq["goi_y_so_luong"] = goi_y_so_luong(lieu, ct.trong_ngay, lieu_moi_kho, he_so)
    sl = so_luong_so(so_luong)
    if sl is None:
        return {
            **kq,
            "ly_do": "Nhập số lượng, hoặc số ngày dùng để máy gợi ý số lượng.",
        }
    so_lieu = sl * he_so * lieu_moi_kho
    so = math.floor(so_lieu / lieu)
    if so < 1:
        return {**kq, "ly_do": "Số lượng kê chưa đủ một ngày dùng."}
    if so > SO_NGAY_TOI_DA:  # gõ nhầm "9999999" — không để ngày vượt lịch (500)
        return {**kq, "ly_do": "Số lượng quá lớn — đủ dùng hơn 10 năm, kiểm lại."}
    kq.update(
        tinh_duoc=True,
        so_ngay=so,
        so_lieu_can=_so_lieu_chu(so_lieu),
        ngay_het=ngay_ke + timedelta(days=so - 1),
    )
    return kq


__all__ = [
    "CachDung",
    "cau_cach_dung",
    "doc_chu_ky",
    "doc_ct",
    "doc_ngay_kinh",
    "goi_y_so_luong",
    "lieu_ngay",
    "so_luong_so",
    "tinh_dong",
    "uoc_tinh_chu_ky",
]
