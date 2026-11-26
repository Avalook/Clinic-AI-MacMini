"""MỘT câu hỏi — một hàm: "dòng thuốc này giá bao nhiêu, theo đơn vị nào, đổi về
đơn vị kho bao nhiêu" (kế hoạch docs/KE-HOACH-DON-VI-ME-CON-CACH-DUNG.md mục 12 T2,
14 C1 + C3).

Hoá đơn (`bill_service.hoa_don_thuoc_lo`), màn quầy (`quay_thuoc_service.doc`) và màn
kê (`phieu_kham_service.doc_don_thuoc`) cùng gọi `tinh_gia_dong` — trước 26/11 quầy và
hoá đơn tính giá bằng hai hàm khác nhau (quầy bỏ qua giá theo tên ở bảng giá dịch vụ).

Luật:
  · Đơn vị dòng TRỐNG = đơn vị MẸ (`BangDonVi.don_vi_dong`). Thuốc chưa khai mẹ thì
    trống vẫn là gốc như cũ — chưa thuốc nào có cờ thì không số nào đổi.
  · Đơn vị gốc: giá danh mục + giá cùng tên ở bảng giá dịch vụ nhóm thuốc; hai nguồn
    khác nhau thì hoá đơn báo mâu thuẫn (`bill_service._dong_gia`).
  · Đơn vị khai thêm có giá riêng: dùng giá đó, không đem so với giá gốc.
  · Đơn vị NHỎ hơn mẹ mà chưa có giá: TỰ CHIA từ giá mẹ. Tiền chỉ lưu đồng chẵn
    (`numeric(12,0)`), nên thành tiền = làm tròn(giá mẹ × số × hệ số dòng ÷ hệ số mẹ):
    Ecanix hộp 60 viên 550.000đ → 10 viên 91.667đ, 60 viên đúng 550.000đ (không đắt hơn
    mua hộp). Kèm `gia_goi_y_con` làm tròn LÊN bội 100đ (9.200đ) — chỉ là gợi ý để người
    có quyền khai giá viên, máy không tự lưu.
  · Không giá thì không thu (chủ ý, đầu tệp `bill_service`).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

import asyncpg

from clinicai.services.don_vi_thuoc import BangDonVi, DonViBan, chuan, doc_bang, tien


def so_luong_sach(v: Any) -> Decimal | None:
    """Số lượng dùng để tính tiền. Rác, âm, NaN, None → None (không ném)."""
    if v is None or isinstance(v, bool):
        return None
    try:
        so = Decimal(str(v).replace(",", ".").strip())
    except (InvalidOperation, ValueError):
        return None
    if not so.is_finite() or so < 0:
        return None
    return so


def dong_chan(x: Decimal | None) -> int | None:
    """Số tiền cho màn hiển thị: làm tròn tới đồng (9.166,67 → 9.167, không cắt)."""
    return None if x is None else int(x.quantize(Decimal(1), rounding=ROUND_HALF_UP))


@dataclass(frozen=True)
class GiaDong:
    """Giá của MỘT dòng đơn theo đơn vị của nó."""

    #: Đơn vị hiệu lực của dòng (trống đã đổi sang mẹ). "" = chưa rõ, hiểu như cũ.
    don_vi: str = ""
    #: Đơn giá ứng viên; đúng một giá (hoặc nhiều giá bằng nhau) thì thu được.
    gia: tuple[Decimal, ...] = ()
    #: Hệ số về đơn vị gốc cho ảnh chụp lần thu. None = đơn vị gốc / chưa khai.
    he_so: Decimal | None = None
    #: Chặn thu: đơn vị đã khai mà chưa có giá, và không tự chia được.
    van_de: str | None = None
    #: Không chặn: đơn vị chưa khai, đang tính giá gốc.
    canh_bao: str | None = None
    #: Giá chia từ giá mẹ (không phải giá ai khai).
    tu_chia: bool = False
    gia_goi_y_con: int | None = None

    @property
    def don_gia(self) -> Decimal | None:
        khac = set(self.gia)
        return next(iter(khac)) if len(khac) == 1 else None

    def thanh_tien(self, so_luong: Any) -> Decimal | None:
        """Làm tròn tới đồng (ROUND_HALF_UP) — cùng phép với `bill_service._tien`."""
        so = so_luong_sach(so_luong)
        if so is None or self.van_de or self.don_gia is None:
            return None
        return (self.don_gia * so).quantize(Decimal(1), rounding=ROUND_HALF_UP)


def _tu_chia(bang: BangDonVi, don_vi: str, he_so: Decimal) -> GiaDong | None:
    """Giá đơn vị con chia từ giá mẹ; None khi không có mẹ có giá, hoặc dòng không
    nhỏ hơn mẹ (đơn vị lớn hơn thì không đoán giá)."""
    me: DonViBan | None = bang.dong.get(bang.me) if bang.me else None
    if me is None or me.gia is None or he_so >= me.he_so:
        return None
    don_gia = me.gia * he_so / me.he_so
    goi_y = (don_gia / 100).to_integral_value(rounding=ROUND_CEILING) * 100
    return GiaDong(
        don_vi=don_vi,
        gia=tuple([don_gia]),
        he_so=None if he_so == 1 else he_so,
        tu_chia=True,
        gia_goi_y_con=int(goi_y),
    )


def tinh_gia_dong(
    bang: BangDonVi,
    don_vi: str | None,
    *,
    co_thuoc: bool,
    gia_danh_muc: Decimal | None = None,
    gia_ten: Iterable[Decimal] = (),
) -> GiaDong:
    """Giá của một dòng. `co_thuoc` = dòng đã gắn thuốc kho; `gia_danh_muc` /
    `gia_ten` là hai nguồn giá của ĐƠN VỊ GỐC (xem đầu tệp)."""
    dv = bang.don_vi_dong(don_vi)
    if not co_thuoc:
        return GiaDong(don_vi=dv)
    goc = tuple([] if gia_danh_muc is None else [gia_danh_muc]) + tuple(gia_ten)
    if not chuan(dv) or not bang.co_goc or bang.la_goc(dv):
        if goc:
            return GiaDong(don_vi=dv, gia=goc)
        return _tu_chia(bang, dv, Decimal(1)) or GiaDong(don_vi=dv)
    k = bang.nhan_ra(dv)
    d = bang.dong.get(chuan(k)) if k else None
    if d is None:
        gia_goc = "" if bang.gia_goc is None else f" {tien(bang.gia_goc)}"
        return GiaDong(
            don_vi=dv,
            gia=goc,
            canh_bao=f"đơn vị “{dv}” chưa khai ở Danh mục — đang tính giá gốc"
            f"{gia_goc}/{bang.goc}. Thêm đơn vị ở Danh mục kho để tính đúng giá.",
        )
    # Tắt bán chỉ bỏ đơn vị khỏi ô chọn: dòng đang chờ thu giữ giá đã lưu, không hỏng.
    if d.gia is not None:
        return GiaDong(don_vi=dv, gia=tuple([d.gia]), he_so=d.he_so)
    return _tu_chia(bang, dv, d.he_so) or GiaDong(
        don_vi=dv,
        he_so=d.he_so,
        van_de=f"đơn vị “{dv}” chưa có giá bán — thêm giá ở Danh mục kho "
        "hoặc đổi đơn vị của dòng",
    )


async def doc_gia_theo_ten(
    conn: asyncpg.Connection, clinic_id: str
) -> dict[str, list[Decimal]]:
    """Giá thuốc ở bảng giá dịch vụ (nhóm 'thuoc'), theo tên đã chuẩn hoá."""
    # Nạp trong hàm: cashier_board_service → … → pharmacy_service → tệp này là vòng.
    from clinicai.services.cashier_board_service import norm_name

    theo_ten: dict[str, list[Decimal]] = {}
    for g in await conn.fetch(
        """
        SELECT name, unit_price FROM public.service_price
         WHERE clinic_id = $1::uuid AND active AND "group" = 'thuoc'
           AND unit_price IS NOT NULL
        """,
        clinic_id,
    ):
        theo_ten.setdefault(norm_name(g["name"]), []).append(g["unit_price"])
    return theo_ten


def gia_ten_cua(
    theo_ten: Mapping[str, Sequence[Decimal]], *ten: str | None
) -> list[Decimal]:
    """Giá theo TÊN CHUẨN của chính thuốc trong danh mục — không phải tên bác sĩ gõ."""
    from clinicai.services.cashier_board_service import norm_name

    ra: list[Decimal] = []
    for t in {norm_name(x) for x in ten}:
        if t:
            ra.extend(theo_ten.get(t, []))
    return ra


async def gia_cac_dong(
    conn: asyncpg.Connection, clinic_id: str, dong: Sequence[Mapping[str, Any]]
) -> list[GiaDong]:
    """`tinh_gia_dong` cho nhiều dòng — hai câu SQL cho cả danh sách. Mỗi dòng cần
    `drug_catalog_id`, `unit`, `gia_danh_muc`, `name_base`, `name_raw`."""
    theo_ten = await doc_gia_theo_ten(conn, clinic_id)
    bang = await doc_bang(conn, clinic_id, [d["drug_catalog_id"] for d in dong])
    return [
        tinh_gia_dong(
            bang.get(d["drug_catalog_id"] or "", BangDonVi()),
            d["unit"],
            co_thuoc=bool(d["drug_catalog_id"]),
            gia_danh_muc=d["gia_danh_muc"],
            gia_ten=gia_ten_cua(theo_ten, d["name_base"], d["name_raw"]),
        )
        for d in dong
    ]


def don_vi_ke_cua(bang: Mapping[str, BangDonVi], thuoc: str | None) -> str | None:
    """Đơn vị kê mặc định (mẹ, không có thì gốc) của một thuốc trong `doc_bang`."""
    return bang.get(thuoc or "", BangDonVi()).don_vi_ke or None


def gia_don_vi_ke(
    bang: Mapping[str, BangDonVi], thuoc: str, gia_danh_muc: Decimal | None
) -> int | None:
    """Đơn giá (đồng) của đơn vị kê mặc định — giá cạnh tên thuốc ở ô chọn màn kê."""
    b = bang.get(thuoc, BangDonVi())
    gd = tinh_gia_dong(b, None, co_thuoc=True, gia_danh_muc=gia_danh_muc)
    return dong_chan(gd.don_gia)


async def don_vi_me(conn: asyncpg.Connection, clinic_id: str, thuoc: str | None) -> str:
    """Đơn vị mẹ đã khai của thuốc; "" = chưa khai (trống hiểu như cũ)."""
    if not thuoc:
        return ""
    bang = await doc_bang(conn, clinic_id, [str(thuoc)])
    return bang.get(str(thuoc), BangDonVi()).don_vi_dong(None)


async def don_vi_ke_mac_dinh(
    conn: asyncpg.Connection, clinic_id: str, thuoc: str | None
) -> str:
    """Đơn vị điền vào dòng đơn đang trống: mẹ nếu có cờ, không thì gốc."""
    if not thuoc:
        return ""
    bang = await doc_bang(conn, clinic_id, [str(thuoc)])
    return bang.get(str(thuoc), BangDonVi()).don_vi_ke
