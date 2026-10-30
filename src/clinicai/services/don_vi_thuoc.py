"""Nhiều đơn vị bán của một thuốc (Tuyền 31/10/2026).

Mỗi thuốc có MỘT đơn vị gốc (`drug_catalog.don_vi_ban`, giá `unit_price`) — kho giữ
theo đơn vị này. Các đơn vị khác nằm ở `thuoc_quy_doi`: "1 hộp = 30 gói", giá riêng,
đang bán hay chỉ để quy đổi lô.

Mọi số trên DÒNG ĐƠN (`quantity_num`, `purchased_qty`, `dispensed_qty`, chờ gán lô,
dòng hoá đơn, hoàn tiền) tính theo ĐƠN VỊ ĐÃ BÁN của dòng đó. Mọi số ở LÔ và sổ kho
tính theo đơn vị của lô. Chỉ chỗ chạm tới cả hai mới đổi, qua `QuyDoiDong`.

Lô theo đơn vị khác gốc (lô cũ "hộp", thuốc bán "viên"): cột kho chỉ có 3 số lẻ nên
20 viên từ lô 30 viên/hộp ghi 0,667 hộp. Chấp nhận khi sai số làm tròn, quy về đơn vị
gốc, không quá `SAI_SO_GOC_TOI_DA` (hệ số tới 100 luôn lọt). Hệ số lớn hơn mà đổi không
chẵn thì KHÔNG trừ: phần đó vào chờ gán lô, câu báo nói rõ.

Chữ bác sĩ gõ tự do giữ nguyên trên dòng đơn. `BangDonVi` chỉ NHẬN DIỆN: "Hộp", "hop",
"hộp 30 viên", "v" (khi thuốc chỉ có một đơn vị bắt đầu bằng v). Nhận không ra thì là
đơn vị chưa khai, không đoán. Số lượng do `so_luong_tu_van_ban` đọc ("1/2 hộp" không
có số) — ở đây không đoán số.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

import asyncpg

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.api.identity import StaffIdentity

#: Hệ số tối đa — khớp CHECK `thuoc_quy_doi.he_so`.
HE_SO_TOI_DA = Decimal(10_000)
GIA_TOI_DA = Decimal(999_999_999)
BA_SO_LE = Decimal("0.001")
#: Số giữ cho phần lẻ theo đơn vị bán (0,333333 hộp): đủ để đổi lại ra số gói đúng.
SAU_SO_LE = Decimal("0.000001")
#: Sai số làm tròn tối đa (theo đơn vị gốc) một lần trừ lô khác đơn vị gốc.
SAI_SO_GOC_TOI_DA = Decimal("0.05")
DO_DAI_TOI_DA = 50


def chuan(don_vi: str | None) -> str:
    """Chỉ chuẩn hoá cách viết (cùng cách với `public.chuan_don_vi`): "Hộp" = "hộp"."""
    return " ".join(unicodedata.normalize("NFC", don_vi or "").casefold().split())


def so_dep(x: Decimal) -> str:
    return format(x.normalize(), "f") if x != 0 else "0"


def _bo_dau(s: str) -> str:
    tach = unicodedata.normalize("NFD", s.replace("đ", "d").replace("Đ", "d"))
    return "".join(c for c in tach if not unicodedata.combining(c))


@dataclass(frozen=True)
class DonViBan:
    don_vi: str
    he_so: Decimal
    gia: Decimal | None
    dang_ban: bool
    #: Dấu phiên bản dòng (cap_nhat_luc): hai người cùng sửa thì người sau bị báo.
    phien: str | None = None


@dataclass(frozen=True)
class GiaDonVi:
    """Giá của một dòng theo đơn vị của nó — để `bill_service` khỏi tự suy luật."""

    #: Tiền lấy từ bảng đơn vị (None = đường giá gốc như cũ).
    gia: Decimal | None = None
    he_so: Decimal | None = None
    #: Chặn thu: đơn vị có trong bảng nhưng chưa có giá.
    van_de: str | None = None
    #: Không chặn: đơn vị chưa khai, đang tính giá gốc.
    canh_bao: str | None = None


@dataclass(frozen=True)
class BangDonVi:
    """Đơn vị gốc + các đơn vị khai thêm của MỘT thuốc."""

    goc: str = ""
    gia_goc: Decimal | None = None
    dong: Mapping[str, DonViBan] = field(default_factory=dict)

    @property
    def co_goc(self) -> bool:
        return bool(chuan(self.goc))

    def _khop(self, don_vi: str | None) -> str | None:
        """Khoá đơn vị đã khai ứng với chữ `don_vi`; None = nhận không ra.

        Thử từ chắc tới yếu, mỗi bước phải ra ĐÚNG MỘT đơn vị: đúng chữ → bỏ dấu
        → từ đầu tiên ("hộp 30 viên") → chữ tắt ("v"). Hai đơn vị cùng khớp thì
        không chọn."""
        c = chuan(don_vi)
        if not c:
            return None
        goc = chuan(self.goc)
        khoa = [goc, *self.dong] if goc else list(self.dong)
        if c in khoa:
            return c
        kd = _bo_dau(c)
        dau = kd.split()[0]
        khop_bo_dau = [k for k in khoa if _bo_dau(k) == kd]
        khop_dau = [k for k in khoa if _bo_dau(k) == dau]
        khop_tat = [k for k in khoa if len(kd) <= 2 and _bo_dau(k).startswith(kd)]
        for khop in (khop_bo_dau, khop_dau, khop_tat):
            if khop:
                return khop[0] if len(khop) == 1 else None
        return None

    def la_goc(self, don_vi: str | None) -> bool:
        return self.co_goc and self._khop(don_vi) == chuan(self.goc)

    def he_so(self, don_vi: str | None) -> Decimal | None:
        """Đổi `don_vi` về đơn vị gốc; None = không đổi được, không đoán."""
        k = self._khop(don_vi)
        if k is None:
            return None
        if k == chuan(self.goc):
            return Decimal(1)
        return self.dong[k].he_so

    def nhan_ra(self, don_vi: str | None) -> str | None:
        """Chữ chuẩn của đơn vị nếu thuốc này có; gõ "HỘP", "hop" ra "hộp"."""
        k = self._khop(don_vi)
        if k is None:
            return None
        return self.goc if k == chuan(self.goc) else self.dong[k].don_vi

    def gia_dong(self, don_vi: str | None) -> GiaDonVi:
        if not chuan(don_vi) or not self.co_goc or self.la_goc(don_vi):
            return GiaDonVi()
        k = self._khop(don_vi)
        d = self.dong[k] if k else None
        if d is None:
            gia = "" if self.gia_goc is None else f" {tien(self.gia_goc)}"
            return GiaDonVi(
                canh_bao=f"đơn vị “{don_vi}” chưa khai ở Danh mục — đang tính giá gốc"
                f"{gia}/{self.goc}. Thêm đơn vị ở Danh mục kho để tính đúng giá."
            )
        # Tắt bán chỉ bỏ đơn vị khỏi ô chọn: dòng đang chờ thu giữ giá đã lưu, không
        # hỏng. Chỉ dòng chưa từng có giá (đơn vị nhập đã nhớ) mới chặn thu.
        if d.gia is None:
            return GiaDonVi(
                he_so=d.he_so,
                van_de=f"đơn vị “{don_vi}” chưa có giá bán — thêm giá ở Danh mục kho "
                "hoặc đổi đơn vị của dòng",
            )
        return GiaDonVi(gia=d.gia, he_so=d.he_so)

    def lua_chon(self) -> list[dict[str, Any]]:
        """Đơn vị quầy chọn được: gốc trước, rồi các đơn vị đang bán."""
        ra: list[dict[str, Any]] = []
        if self.co_goc:
            ra.append(
                {
                    "don_vi": self.goc,
                    "he_so": "1",
                    "gia": int(self.gia_goc) if self.gia_goc is not None else None,
                    "goc": True,
                }
            )
        for d in sorted(self.dong.values(), key=lambda x: (x.he_so, x.don_vi)):
            if d.dang_ban and d.gia is not None:
                ra.append(
                    {
                        "don_vi": d.don_vi,
                        "he_so": so_dep(d.he_so),
                        "gia": int(d.gia),
                        "goc": False,
                    }
                )
        return ra

    def cac_dong(self) -> list[dict[str, Any]]:
        """Mọi đơn vị đã khai, cả đang tắt — cho form Sửa của danh mục."""
        return [
            {
                "don_vi": d.don_vi,
                "he_so": so_dep(d.he_so),
                "gia": int(d.gia) if d.gia is not None else None,
                "dang_ban": d.dang_ban,
                "phien": d.phien,
            }
            for d in sorted(self.dong.values(), key=lambda x: (x.he_so, x.don_vi))
        ]

    def nhan_gia(self) -> list[dict[str, Any]]:
        """Dòng giá cho danh mục: "gói 85.000 đ · hộp (30 gói) 2.400.000 đ"."""
        ra: list[dict[str, Any]] = []
        if self.co_goc:
            ra.append(
                {
                    "nhan": self.goc,
                    "gia": int(self.gia_goc) if self.gia_goc is not None else None,
                }
            )
        for d in sorted(self.dong.values(), key=lambda x: (x.he_so, x.don_vi)):
            if d.dang_ban:
                ra.append(
                    {
                        "nhan": f"{d.don_vi} ({so_dep(d.he_so)} {self.goc})",
                        "gia": int(d.gia) if d.gia is not None else None,
                    }
                )
        return ra

    def chu_ton(self, ton_theo_don_vi: Iterable[Mapping[str, Any]]) -> str | None:
        """Tồn cộng về đơn vị gốc (chỉ phần đổi được), đọc thêm theo đơn vị lớn
        nhất: "= 280 viên · 9 hộp 10 viên". Không có gì để nói thì None."""
        tong = Decimal(0)
        co_lo_khac_goc = False
        for x in ton_theo_don_vi:
            hs = self.he_so(x.get("don_vi"))
            if hs is None:
                continue
            co_lo_khac_goc = co_lo_khac_goc or hs != 1
            tong += Decimal(str(x.get("ton") or 0)) * hs
        if not self.co_goc or tong <= 0:
            return None
        # Lô tính hộp ghi 3 số lẻ: 9,333 × 30 = 279,99 đọc là 280 viên.
        tong = tong.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        phan = [f"= {so_dep(tong)} {self.goc}"] if co_lo_khac_goc else []
        lon = [d for d in self.dong.values() if d.he_so > 1]
        if lon:
            d = max(lon, key=lambda x: x.he_so)
            nguyen = (tong / d.he_so).to_integral_value(rounding=ROUND_FLOOR)
            du = tong - nguyen * d.he_so
            if nguyen > 0 and du > 0:
                phan.append(f"{so_dep(nguyen)} {d.don_vi} {so_dep(du)} {self.goc}")
            elif nguyen > 0 and not co_lo_khac_goc:
                phan.append(f"{so_dep(nguyen)} {d.don_vi}")
        return " · ".join(phan) or None


def tien(x: Decimal) -> str:
    return f"{int(x):,}đ".replace(",", ".")


@dataclass(frozen=True)
class QuyDoiDong:
    """Đổi số của MỘT dòng đơn ra số của lô, và ngược lại."""

    don_vi: str
    he_so_dong: Decimal | None
    bang: BangDonVi

    def _cung_don_vi(self, don_vi_lo: str | None) -> bool:
        if chuan(don_vi_lo) == chuan(self.don_vi):
            return True
        # Dòng "hộp 30 viên" với lô "hộp": cùng một đơn vị đã khai.
        k = self.bang._khop(self.don_vi)
        return k is not None and k == self.bang._khop(don_vi_lo)

    def ty_le(self, don_vi_lo: str | None) -> Decimal | None:
        """Một đơn vị của dòng = bao nhiêu đơn vị lô; None = không đổi được."""
        if self._cung_don_vi(don_vi_lo):
            return Decimal(1)
        lo = self.bang.he_so(don_vi_lo)
        if lo is None or self.he_so_dong is None:
            return None
        return self.he_so_dong / lo

    def so_lo(self, so_dong: Decimal, don_vi_lo: str | None) -> Decimal | None:
        """Số phải trừ ở lô cho `so_dong` đơn vị của dòng (xem đầu file)."""
        if self._cung_don_vi(don_vi_lo):
            return so_dong.quantize(BA_SO_LE, rounding=ROUND_HALF_UP)
        lo = self.bang.he_so(don_vi_lo)
        if lo is None or self.he_so_dong is None:
            return None
        tho = so_dong * self.he_so_dong / lo
        tron = tho.quantize(BA_SO_LE, rounding=ROUND_HALF_UP)
        if tron > 0 and abs(tho - tron) * lo <= SAI_SO_GOC_TOI_DA:
            return tron
        return None

    def so_dong(self, so_goc_don_vi: Decimal, don_vi: str | None) -> Decimal | None:
        """Đổi `so_goc_don_vi` theo `don_vi` (của lần giao khác) về đơn vị dòng."""
        if self._cung_don_vi(don_vi):
            return so_goc_don_vi
        hs = self.bang.he_so(don_vi)
        if hs is None or self.he_so_dong is None:
            return None
        return so_goc_don_vi * hs / self.he_so_dong


def so_de_doc(
    so: Decimal, he_so: Decimal | None, goc: str | None, don_vi: str | None
) -> str:
    """Số đã giao cho người đọc: quy về đơn vị gốc khi dòng bán đơn vị khác.

    Quầy thiếu 1 gói của hộp 30 gói: "1 gói", không phải "0.033333 hộp"."""
    if he_so and he_so != 1 and goc:
        ra = (so * he_so).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
        return f"{format(ra.normalize(), 'f')} {goc}"
    return f"{format(so.normalize(), 'f')} {don_vi or ''}".strip()


def cau_thieu_quy_doi(q: QuyDoiDong, don_vi_lo: Iterable[str | None]) -> str | None:
    """Vì sao phần giao chưa trừ được kho, nói rõ việc phải làm. None = không vì
    đơn vị (chỉ là hết hàng)."""
    b = q.bang
    if not b.co_goc:
        return "Thuốc này chưa khai đơn vị — khai đơn vị ở Danh mục kho rồi gán lô."
    if not chuan(q.don_vi):
        return (
            f"Dòng này chưa ghi đơn vị — đơn vị gốc của thuốc là “{b.goc}”, gán lô "
            "theo đơn vị đó."
        )
    if q.he_so_dong is None:
        return (
            f"Cần thêm đơn vị “{q.don_vi}” ở Danh mục kho "
            f"(1 {q.don_vi} = ? {b.goc}) rồi gán lô."
        )
    thieu = sorted(
        {
            (u or "").strip()
            for u in don_vi_lo
            if chuan(u) and q.ty_le(u) is None and (u or "").strip()
        }
    )
    if thieu:
        ds = ", ".join(f"“{u}”" for u in thieu)
        return f"Có lô tính theo {ds} chưa có hệ số về “{b.goc}” — thêm ở Danh mục kho."
    return None


async def doc_bang(
    conn: asyncpg.Connection, clinic_id: str, thuoc_ids: Sequence[str]
) -> dict[str, BangDonVi]:
    """Bảng đơn vị của nhiều thuốc — hai câu SQL cho cả danh sách."""
    ids = sorted({str(t) for t in thuoc_ids if t})
    if not ids:
        return {}
    goc = await conn.fetch(
        "SELECT id::text AS id, don_vi_ban, unit_price FROM public.drug_catalog"
        " WHERE clinic_id = $1::uuid AND id = ANY($2::uuid[])",
        clinic_id,
        ids,
    )
    dong = await conn.fetch(
        "SELECT drug_catalog_id::text AS id, don_vi, he_so, gia, dang_ban,"
        "       cap_nhat_luc::text AS phien"
        "  FROM public.thuoc_quy_doi"
        " WHERE clinic_id = $1::uuid AND drug_catalog_id = ANY($2::uuid[])",
        clinic_id,
        ids,
    )
    theo: dict[str, dict[str, DonViBan]] = {}
    for r in dong:
        theo.setdefault(r["id"], {})[chuan(r["don_vi"])] = DonViBan(
            don_vi=r["don_vi"],
            he_so=Decimal(str(r["he_so"])),
            gia=Decimal(str(r["gia"])) if r["gia"] is not None else None,
            dang_ban=bool(r["dang_ban"]),
            phien=r["phien"],
        )
    return {
        r["id"]: BangDonVi(
            goc=(r["don_vi_ban"] or "").strip(),
            gia_goc=Decimal(str(r["unit_price"]))
            if r["unit_price"] is not None
            else None,
            dong=theo.get(r["id"], {}),
        )
        for r in goc
    }


async def quy_doi_cua_dong(
    conn: asyncpg.Connection,
    clinic_id: str,
    *,
    thuoc: str | None,
    don_vi: str | None,
    prescription_id: str,
) -> QuyDoiDong:
    """Hệ số của một dòng đã bán: lấy HỆ SỐ LÚC THU (ảnh chụp) nếu có — sửa danh
    mục sau đó không làm sai dòng đã thu; không có thì đọc bảng hiện tại."""
    if not thuoc:  # chưa rõ thuốc kho thì không có gì để đổi
        return QuyDoiDong((don_vi or "").strip(), None, BangDonVi())
    bang = (await doc_bang(conn, clinic_id, [thuoc])).get(str(thuoc), BangDonVi())
    chup = await he_so_da_chup(conn, clinic_id, [prescription_id])
    hs = chup.get(prescription_id) or bang.he_so(don_vi)
    return QuyDoiDong(don_vi=(don_vi or "").strip(), he_so_dong=hs, bang=bang)


async def he_so_da_chup(
    conn: asyncpg.Connection, clinic_id: str, prescription_ids: Sequence[str]
) -> dict[str, Decimal]:
    """Hệ số LÚC THU của các dòng đơn: lần thu còn hiệu lực gần nhất; không có thì
    lần đã huỷ phiếu (thuốc giao từ lần ấy vẫn trả theo số lúc bán)."""
    ids = list(dict.fromkeys(str(p) for p in prescription_ids))
    if not ids:
        return {}
    rows = await conn.fetch(
        """
        SELECT DISTINCT ON (bl.source_id) bl.source_id, bl.he_so
          FROM public.payment_bill_line bl
          JOIN public.payment_cycle c
            ON c.clinic_id = bl.clinic_id AND c.payment_cycle_id = bl.payment_cycle_id
         WHERE bl.clinic_id = $1::uuid AND bl.source_type = 'prescription'
           AND bl.source_id = ANY($2::text[])
           AND c.status IN ('PAID', 'PENDING_VERIFICATION', 'VOIDED')
         ORDER BY bl.source_id, (c.status = 'VOIDED'), (c.paid_at IS NULL),
                  c.paid_at DESC
        """,
        clinic_id,
        ids,
    )
    return {r["source_id"]: Decimal(str(r["he_so"])) for r in rows if r["he_so"]}


def doc_don_vi_gui_len(
    ds: Any, *, goc: str | None, gia_goc: Decimal | None
) -> list[DonViBan]:
    """Danh sách đơn vị người dùng gửi ở form Sửa → dòng đã kiểm. Không gửi giá thì
    LƯU RÕ giá gợi ý = hệ số × giá gốc. Rác → câu tiếng Việt, không 500."""
    if ds is None:
        return []
    if not isinstance(ds, list) or len(ds) > 20:
        raise ValidationError("Danh sách đơn vị bán không hợp lệ.")
    ra: list[DonViBan] = []
    da_co: set[str] = set()
    for d in ds:
        if not isinstance(d, Mapping):
            raise ValidationError("Dòng đơn vị bán không hợp lệ.")
        chu = " ".join(str(d.get("don_vi") or "").split())
        if not chu:
            raise ValidationError("Nhập tên đơn vị (hộp, vỉ, lọ…).")
        if len(chu) > DO_DAI_TOI_DA:
            raise ValidationError(f"Tên đơn vị quá dài (tối đa {DO_DAI_TOI_DA} ký tự).")
        ma = chuan(chu)
        if ma in da_co:
            raise ValidationError(f"Đơn vị “{chu}” bị trùng.")
        da_co.add(ma)
        if not chuan(goc):
            raise ValidationError(
                "Khai đơn vị bán của thuốc (ô Đơn vị gốc) trước khi thêm đơn vị khác."
            )
        if ma == chuan(goc):
            raise ValidationError(
                f"“{chu}” là đơn vị gốc rồi — đơn vị thêm phải khác đơn vị gốc."
            )
        hs = _he_so(d.get("he_so"), chu)
        dang_ban = d.get("dang_ban") is not False
        gia = _gia(d.get("gia"), chu)
        if gia is None and dang_ban:
            if gia_goc is None:
                raise ValidationError(
                    f"Nhập giá cho “{chu}” — thuốc chưa có giá gốc để gợi ý."
                )
            gia = (hs * gia_goc).quantize(Decimal(1), rounding=ROUND_HALF_UP)
        phien = d.get("phien")
        ra.append(
            DonViBan(
                don_vi=ma,
                he_so=hs,
                gia=gia,
                dang_ban=dang_ban,
                phien=str(phien) if phien else None,
            )
        )
    return ra


def _he_so(v: Any, chu: str) -> Decimal:
    try:
        hs = Decimal(str(v).replace(",", ".").strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError(f"Hệ số của “{chu}” phải là một con số.") from exc
    if not hs.is_finite() or hs <= 0:
        raise ValidationError(f"Hệ số của “{chu}” phải lớn hơn 0.")
    if hs > HE_SO_TOI_DA:
        raise ValidationError(
            f"Hệ số của “{chu}” quá lớn (tối đa {HE_SO_TOI_DA:,.0f}) — kiểm tra lại."
        )
    tron = hs.quantize(BA_SO_LE, rounding=ROUND_HALF_UP)
    if tron <= 0:
        raise ValidationError(f"Hệ số của “{chu}” quá nhỏ (tối đa 3 số lẻ).")
    return tron


def _gia(v: Any, chu: str) -> Decimal | None:
    if v is None or str(v).strip() == "":
        return None
    chu_so = str(v).strip()
    # "2.400.000" / "2,400,000" là cách viết tiền, không phải số lẻ.
    if re.fullmatch(r"\d{1,3}([.,]\d{3})+", chu_so):
        chu_so = re.sub(r"[.,]", "", chu_so)
    try:
        gia = Decimal(chu_so)
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError(f"Giá của “{chu}” phải là một con số.") from exc
    if not gia.is_finite() or gia < 0:
        raise ValidationError(f"Giá của “{chu}” phải là số không âm.")
    if gia > GIA_TOI_DA:
        raise ValidationError(f"Giá của “{chu}” quá lớn — kiểm tra lại.")
    return gia.quantize(Decimal(1), rounding=ROUND_HALF_UP)


async def luu_cac_don_vi(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    *,
    thuoc: str,
    ds: Sequence[DonViBan],
) -> list[dict[str, Any]]:
    """Ghi các đơn vị vừa gửi, trong giao dịch của người gọi. Đơn vị KHÔNG gửi thì
    giữ nguyên: "bỏ" một đơn vị là tắt bán, hệ số còn đó cho lô và dòng cũ. Trả các
    thay đổi để ghi nhật ký.

    Hai người cùng sửa: lệnh UPDATE thuốc của người gọi đã khoá dòng thuốc nên hai
    lần lưu xếp hàng; người sau mang `phien` cũ thì bị từ chối, không đè mất số."""
    if not ds:
        return []
    cu = {
        r["don_vi"]: r
        for r in await conn.fetch(
            "SELECT don_vi, he_so, gia, dang_ban, cap_nhat_luc::text AS phien"
            "  FROM public.thuoc_quy_doi"
            " WHERE clinic_id = $1::uuid AND drug_catalog_id = $2::uuid FOR UPDATE",
            identity.clinic_id,
            thuoc,
        )
    }
    doi: list[dict[str, Any]] = []
    for d in ds:
        c = cu.get(d.don_vi)
        if c is not None and (
            (d.phien is not None and d.phien != c["phien"])
            or (d.phien is None and (c["dang_ban"] or c["gia"] is not None))
        ):
            raise ConflictError(
                f"Đơn vị “{d.don_vi}” vừa được người khác sửa — tải lại rồi sửa tiếp."
            )
        if (
            c is not None
            and Decimal(str(c["he_so"])) == d.he_so
            and c["gia"] == d.gia
            and bool(c["dang_ban"]) == d.dang_ban
        ):
            continue
        await conn.execute(
            """
            INSERT INTO public.thuoc_quy_doi
                (clinic_id, drug_catalog_id, don_vi, he_so, gia, dang_ban,
                 cap_nhat_boi)
            VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7::uuid)
            ON CONFLICT (clinic_id, drug_catalog_id, don_vi)
            DO UPDATE SET he_so = EXCLUDED.he_so, gia = EXCLUDED.gia,
                          dang_ban = EXCLUDED.dang_ban,
                          cap_nhat_boi = EXCLUDED.cap_nhat_boi,
                          cap_nhat_luc = now()
            """,
            identity.clinic_id,
            thuoc,
            d.don_vi,
            d.he_so,
            d.gia,
            d.dang_ban,
            identity.staff_id,
        )
        doi.append(
            {
                "don_vi": d.don_vi,
                "he_so": str(d.he_so),
                "gia": None if d.gia is None else int(d.gia),
                "dang_ban": d.dang_ban,
                "truoc": None
                if c is None
                else {
                    "he_so": str(c["he_so"]),
                    "gia": None if c["gia"] is None else int(c["gia"]),
                    "dang_ban": bool(c["dang_ban"]),
                },
            }
        )
    return doi


async def kiem_doi_don_vi_goc(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    *,
    thuoc: str,
    goc_moi: str | None,
) -> None:
    """Đơn vị gốc là nghĩa của số tồn và mọi hệ số. Đổi khi còn tồn theo gốc cũ, đã
    có hệ số theo gốc cũ, hay còn dòng chờ gán lô thì các số ấy đổi nghĩa — chặn.

    Không còn gì neo vào gốc cũ thì đổi được: gốc khai sai, lô thật lại tính theo
    đơn vị mới."""
    cu = await conn.fetchval(
        "SELECT don_vi_ban FROM public.drug_catalog"
        " WHERE id = $1::uuid AND clinic_id = $2::uuid",
        thuoc,
        identity.clinic_id,
    )
    if not chuan(cu) or chuan(cu) == chuan(goc_moi):
        return
    r = await conn.fetchrow(
        """
        SELECT EXISTS (SELECT 1 FROM public.thuoc_quy_doi q
                        WHERE q.clinic_id = $1::uuid AND q.drug_catalog_id = $2::uuid)
                   AS co_he_so,
               EXISTS (SELECT 1 FROM public.drug_batch b
                        WHERE b.clinic_id = $1::uuid AND b.drug_catalog_id = $2::uuid
                          AND b.quantity_on_hand <> 0
                          AND public.chuan_don_vi(b.unit) = $3) AS co_ton,
               EXISTS (SELECT 1 FROM public.thuoc_giao_chua_gan_lo g
                        WHERE g.clinic_id = $1::uuid AND g.drug_catalog_id = $2::uuid
                          AND g.drug_batch_id IS NULL) AS co_cho_gan
        """,
        identity.clinic_id,
        thuoc,
        chuan(cu),
    )
    if r["co_ton"]:
        raise ConflictError(
            f"Kho đang có tồn tính theo “{cu}” — đổi đơn vị gốc sẽ đổi nghĩa toàn bộ "
            "số tồn. Giữ đơn vị gốc và thêm đơn vị bán mới bên dưới."
        )
    if r["co_he_so"] or r["co_cho_gan"]:
        raise ConflictError(
            f"Thuốc đã có hệ số hoặc dòng chờ gán lô theo “{cu}” — đổi đơn vị gốc sẽ "
            "làm sai các số ấy. Giữ đơn vị gốc, hoặc tạo thuốc mới."
        )
