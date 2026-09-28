"""Hoá đơn do MÁY CHỦ tính — contract tiền–thuốc CP1 (19/09/2026).

Trước đây màn thu ngân tự cộng tiền rồi gửi `amount` lên, và `PaymentService`
chỉ kiểm số ấy > 0 (B1); màn thu thuốc còn cộng ĐƠN GIÁ mà quên nhân số lượng
(B2). Tức là số tiền phòng khám thu do trình duyệt quyết.

Từ đây: hoá đơn dựng từ dữ liệu chuẩn, trong CÙNG giao dịch với lần thu —

    dich_vu:  tiền khám (loại khám của lịch hẹn) + service_order đủ điều kiện
              × giá theo mã; dòng của đối tác tự thu (billing_owner) hiện ra
              nhưng KHÔNG cộng vào tổng.
    thuoc:    dòng đơn đã xác định thuốc kho (drug_catalog_id), chưa bị từ chối,
              × số khách mua (purchased_qty, chưa khai = số kê) × đơn giá.

GIÁ THUỐC — HOLD J5 (nguồn giá chuẩn là `drug_catalog` hay `service_price`?)
CHƯA ĐƯỢC CHỐT, nên ở đây không chọn nguồn nào thắng. Lấy mọi giá đang có cho
đúng thuốc ấy (`drug_catalog.unit_price` theo mã thuốc; `service_price` nhóm
thuốc trùng TÊN CHUẨN của chính thuốc trong danh mục), rồi:
    không có giá nào   → dòng thiếu giá, chưa thu được;
    các giá khác nhau  → dòng mâu thuẫn giá, chưa thu được (nói rõ hai số);
    một giá            → dùng.
Đo prod 19/09: 79/80 thuốc hai nguồn trùng, 0 lệch, 1 chỉ có ở danh mục.

`revision` là dấu của nội dung hoá đơn. Thu ngân gửi lại dấu đã thấy; máy chủ
tính lại mà khác dấu → BILL_CHANGED, không thu số cũ.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import asyncpg

from clinicai.services.cashier_board_service import clean_name, norm_name

CLINIC = "CLINIC"
EXTERNAL = "EXTERNAL_PARTNER"
KINDS = ("thuoc", "dich_vu")


@dataclass(frozen=True)
class DongHoaDon:
    source_type: str  # exam | service_order | prescription
    source_id: str
    ten: str
    so_luong: Decimal
    don_vi: str | None
    don_gia: Decimal | None
    thanh_tien: Decimal | None
    ben_thu: str
    drug_catalog_id: str | None = None
    # Mã ĐỊNH DANH của thứ được bán: service_code (chỉ định), mã loại khám
    # (tiền khám). Thuốc dùng drug_catalog_id. Vào revision (review CP1 #2).
    ma: str | None = None
    # Vì sao dòng này chưa thu được (thiếu giá, mâu thuẫn giá, chưa xác định
    # thuốc kho, thiếu số lượng). Rỗng = thu được.
    van_de: str | None = None


@dataclass
class HoaDon:
    visit_id: str
    kind: str
    dong: list[DongHoaDon] = field(default_factory=list)
    # Vấn đề của CẢ LƯỢT, không thuộc dòng nào (vd tiền cũ không truy được).
    van_de_luot: list[str] = field(default_factory=list)
    # ĐỐI TÁC TỰ THU (Tuyền chốt 27/09/2026, Q1): dịch vụ khách trả TRỰC TIẾP
    # cho đối tác. Quầy HIỆN (kèm giá tham khảo) nhưng không cộng, không vào
    # dấu hoá đơn, không vào ảnh chụp lần thu — nó không phải khoản của phòng
    # khám. Chỉ hoá đơn CÒN NỢ điền phần này.
    dong_doi_tac: list[DongHoaDon] = field(default_factory=list)
    # Đối tác đã ghi nhận thu tiền cho chỉ định nào (source_id → ghi nhận).
    doi_tac_da_thu: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def dong_thu(self) -> list[DongHoaDon]:
        """Dòng phòng khám thu (bỏ dòng đối tác tự thu)."""
        return [d for d in self.dong if d.ben_thu == CLINIC]

    @property
    def van_de(self) -> list[str]:
        return self.van_de_luot + [
            f"{d.ten}: {d.van_de}" for d in self.dong_thu if d.van_de
        ]

    @property
    def tong(self) -> int:
        return int(sum((d.thanh_tien or Decimal(0)) for d in self.dong_thu))

    @property
    def thu_duoc(self) -> bool:
        return not self.van_de and self.tong > 0

    @property
    def chi_doi_tac_thu(self) -> bool:
        """Phòng khám không còn khoản nào, chỉ còn dịch vụ khách trả trực tiếp
        cho đối tác — quầy KHÔNG kẹt: nói "Khách trả trực tiếp cho đối tác"."""
        return not self.dong and bool(self.dong_doi_tac)

    @property
    def revision(self) -> str:
        # Gắn cả ĐỊNH DANH thứ được bán (mã dịch vụ / loại khám / thuốc kho) và
        # đơn vị (review CP1 #2): đổi A → B cùng giá, cùng số lượng vẫn là một
        # hoá đơn KHÁC.
        noi_dung = [
            [
                d.source_type,
                d.source_id,
                d.ma,
                d.drug_catalog_id,
                str(d.so_luong),
                d.don_vi,
                str(d.don_gia),
                d.ben_thu,
            ]
            for d in sorted(self.dong, key=lambda x: (x.source_type, x.source_id))
        ]
        return hashlib.sha256(json.dumps([self.kind, noi_dung]).encode()).hexdigest()[
            :16
        ]

    def cho_api(self) -> dict[str, Any]:
        return {
            "visit_id": self.visit_id,
            "kind": self.kind,
            "tong": self.tong,
            "revision": self.revision,
            "thu_duoc": self.thu_duoc,
            "van_de": self.van_de,
            "dong": [_dong_api(d) for d in self.dong],
            "chi_doi_tac_thu": self.chi_doi_tac_thu,
            "dong_doi_tac": [
                {
                    **_dong_api(d),
                    "doi_tac_da_thu": self.doi_tac_da_thu.get(d.source_id),
                }
                for d in self.dong_doi_tac
            ],
        }


def _dong_api(d: DongHoaDon) -> dict[str, Any]:
    return {
        **{k: v for k, v in asdict(d).items()},
        "so_luong": float(d.so_luong),
        "don_gia": float(d.don_gia) if d.don_gia is not None else None,
        "thanh_tien": (float(d.thanh_tien) if d.thanh_tien is not None else None),
    }


def tach_doi_tac(hd: HoaDon) -> HoaDon:
    """Tách dòng ĐỐI TÁC TỰ THU ra khỏi phần phòng khám thu. Thuần.

    Dòng đối tác không vào tổng, không vào dấu hoá đơn, không vào ảnh chụp lần
    thu — chỉ để quầy hiện "khách trả trực tiếp cho đối tác" + giá tham khảo.
    """
    hd.dong_doi_tac = [d for d in hd.dong if d.ben_thu == EXTERNAL]
    hd.dong = [d for d in hd.dong if d.ben_thu == CLINIC]
    return hd


def _tien(don_gia: Decimal, so_luong: Decimal) -> Decimal:
    return (don_gia * so_luong).quantize(Decimal(1), rounding=ROUND_HALF_UP)


def _dong_gia(
    *,
    source_type: str,
    source_id: str,
    ten: str,
    so_luong: Decimal,
    don_vi: str | None,
    gia: list[Decimal],
    ben_thu: str,
    drug_catalog_id: str | None = None,
    ma: str | None = None,
    van_de: str | None = None,
) -> DongHoaDon:
    """Một dòng, với luật giá "không mâu thuẫn" (xem đầu file)."""
    khac_nhau = sorted(set(gia))
    don_gia: Decimal | None = None
    if van_de is None:
        if not khac_nhau:
            van_de = CHUA_CO_GIA
        elif len(khac_nhau) > 1:
            van_de = _gia_mau_thuan(khac_nhau)
        else:
            don_gia = khac_nhau[0]
    return DongHoaDon(
        source_type=source_type,
        source_id=source_id,
        ten=ten,
        so_luong=so_luong,
        don_vi=don_vi,
        don_gia=don_gia,
        thanh_tien=_tien(don_gia, so_luong) if don_gia is not None else None,
        ben_thu=ben_thu,
        drug_catalog_id=drug_catalog_id,
        ma=ma,
        van_de=van_de,
    )


BEN_THU_MAU_THUAN = "cấu hình bên thu mâu thuẫn giữa các bảng giá"
CHUA_CO_GIA = "chưa có giá"


def giai_ben_thu(ben_thu: Sequence[str | None]) -> tuple[str | None, str | None]:
    """Bên thu của một dịch vụ theo cấu hình giá: ``(ben_thu, van_de)``.

    MỘT nguồn luật cho hoá đơn và FinanceGate (FINANCE-GATE §11): không có dòng
    cấu hình → mặc định phòng khám thu (như trước) và dòng sẽ "chưa có giá";
    nhiều bên thu khác nhau → mâu thuẫn, KHÔNG đoán bằng max()/dòng đầu.
    """
    khac = sorted({b for b in ben_thu if b})
    if not khac:
        return CLINIC, None
    if len(khac) > 1:
        return None, BEN_THU_MAU_THUAN
    return khac[0], None


def giai_gia(
    gia: Sequence[Any], ben_thu: Sequence[str | None]
) -> tuple[str | None, Decimal | None, str | None]:
    """``(ben_thu, don_gia, van_de)`` của một dịch vụ — luật chung.

    0đ là giá hợp lệ (không phải thiếu giá). Đối tác tự thu thì giá phòng khám
    không liên quan.
    """
    ben, van_de = giai_ben_thu(ben_thu)
    if van_de or ben != CLINIC:
        return ben, None, van_de
    khac = sorted({Decimal(str(g)) for g in gia if g is not None})
    if not khac:
        return ben, None, CHUA_CO_GIA
    if len(khac) > 1:
        return ben, None, _gia_mau_thuan(khac)
    return ben, khac[0], None


def _gia_mau_thuan(khac: Sequence[Decimal]) -> str:
    return (
        "giá mâu thuẫn giữa các bảng giá ("
        + " / ".join(f"{int(g):,}đ".replace(",", ".") for g in khac)
        + ")"
    )


KHAM_KHONG_HEN = "chưa xác định loại khám (lượt không có lịch hẹn)"
KHAM_KHONG_RO_LOAI = "chưa xác định loại khám"


def dong_kham(
    kham_row: Mapping[str, Any] | None, gia_dv: Sequence[Mapping[str, Any]]
) -> dict[str, Any] | None:
    """Dòng tiền khám của một lượt. Thuần — kiểm được không cần DB.

    Luật (CP1, review CP4, CP6 bước 3): một lượt đã có thì LUÔN có dòng tiền
    khám. Không xác định được loại khám — vì lượt không có lịch hẹn, hay vì
    lịch hẹn không dẫn tới loại khám nào (dữ liệu hỏng, schema đổi sau này) —
    thì hiện dòng "Tiền khám" kèm vấn đề: khoản chưa thu được, chứ không bỏ im
    lặng (thu thiếu mà không ai thấy). Không đoán loại khám, không đoán giá.
    """
    if kham_row is None:
        return None  # không có lượt — nơi gọi đã báo lỗi riêng
    if clean_name(kham_row["name"]):
        # TÁI KHÁM (28/09/2026, theo KiotViet — "Tái khám mong con" 150k khác
        # "Khám mong con lần đầu" 400k): có dòng giá "<loại khám> (tái khám)" và
        # lượt là tái khám thì tính dòng ấy; không có thì như lần đầu.
        ten_tai = f"{kham_row['name']} (tái khám)"
        khop_tai = (
            [r for r in gia_dv if norm_name(r["name"]) == norm_name(ten_tai)]
            if kham_row.get("tai_kham")
            else []
        )
        khop = khop_tai or [
            r for r in gia_dv if norm_name(r["name"]) == norm_name(kham_row["name"])
        ]
        ben, van_de_ben = giai_ben_thu([r["billing_owner"] for r in khop])
        return {
            "ma": kham_row["st_id"],
            "ten": ten_tai if khop_tai else kham_row["name"],
            "gia": [r["unit_price"] for r in khop],
            "ben_thu": ben or CLINIC,
            **({"van_de": van_de_ben} if van_de_ben else {}),
        }
    elif kham_row["khong_hen"]:
        van_de = KHAM_KHONG_HEN
    else:
        van_de = KHAM_KHONG_RO_LOAI
    return {
        "ma": None,
        "ten": "Tiền khám",
        "gia": [],
        "ben_thu": CLINIC,
        "van_de": van_de,
    }


def ghep_dich_vu(
    visit_id: str,
    kham: dict[str, Any] | None,
    chi_dinh: list[dict[str, Any]],
) -> HoaDon:
    """Hoá đơn dịch vụ từ dữ liệu đã đọc. Thuần — kiểm được không cần DB."""
    hd = HoaDon(visit_id=visit_id, kind="dich_vu")
    if kham and clean_name(kham.get("ten")):
        hd.dong.append(
            _dong_gia(
                source_type="exam",
                source_id=f"exam-{visit_id}",
                ten=clean_name(kham.get("ten")),
                so_luong=Decimal(1),
                don_vi=None,
                gia=[Decimal(str(g)) for g in kham.get("gia") or []],
                ben_thu=kham.get("ben_thu") or CLINIC,
                ma=kham.get("ma"),
                van_de=kham.get("van_de"),
            )
        )
    for o in chi_dinh:
        hd.dong.append(
            _dong_gia(
                source_type="service_order",
                source_id=str(o["id"]),
                ten=clean_name(o.get("ten")) or str(o.get("service_code") or ""),
                so_luong=Decimal(1),
                don_vi=None,
                gia=[Decimal(str(g)) for g in o.get("gia") or []],
                ben_thu=o.get("ben_thu") or CLINIC,
                ma=o.get("service_code"),
                van_de=o.get("van_de"),
            )
        )
    return hd


def ghep_thuoc(visit_id: str, don: list[dict[str, Any]]) -> HoaDon:
    """Hoá đơn thuốc. Dòng từ chối / mua 0 không vào hoá đơn."""
    hd = HoaDon(visit_id=visit_id, kind="thuoc")
    for d in don:
        if d.get("refusal_reason"):
            continue
        mua = d.get("purchased_qty")
        so = mua if mua is not None else d.get("quantity_num")
        van_de: str | None = None
        if so is None:
            van_de = "chưa có số lượng"
            so_luong = Decimal(1)
        else:
            so_luong = Decimal(str(so))
            if so_luong == 0:
                continue
        if d.get("drug_catalog_id") is None:
            van_de = "thuốc chưa có trong danh mục giá"
        hd.dong.append(
            _dong_gia(
                source_type="prescription",
                source_id=str(d["id"]),
                ten=(d.get("ten") or "").strip(),
                so_luong=so_luong,
                don_vi=d.get("unit"),
                gia=[Decimal(str(g)) for g in d.get("gia") or []],
                ben_thu=CLINIC,
                drug_catalog_id=(
                    str(d["drug_catalog_id"]) if d.get("drug_catalog_id") else None
                ),
                van_de=van_de,
            )
        )
    return hd


#: Một nguồn (tiền khám / chỉ định) đang được PHÒNG KHÁM giữ phủ: dòng phòng
#: khám thu nằm trong lần thu đang chờ xác minh hoặc đang PAID (kể cả đã hoàn
#: một phần/đủ — hoàn không đổi trạng thái lần thu, không tự thu lại). Phiếu đã
#: HUỶ (VOIDED) thì KHÔNG còn giữ phủ: Tuyền chốt 24/09/2026 "thu nhầm → huỷ →
#: thu lại được; phiếu huỷ lưu lại để đối chiếu, dùng bản mới nhất". Cùng luật
#: với chốt DB ``payment_bill_line_mot_lan_phu`` (20260925000001).
_DA_PHU = """
EXISTS (
    SELECT 1
      FROM public.payment_bill_line bl
      JOIN public.payment_cycle c
        ON c.clinic_id = bl.clinic_id AND c.payment_cycle_id = bl.payment_cycle_id
     WHERE bl.clinic_id = $1::uuid
       AND bl.source_type = {loai}
       AND bl.source_id = {nguon}
       AND bl.billing_owner = 'CLINIC'
       AND c.status IN ('PENDING_VERIFICATION', 'PAID'))
"""

#: Tiền dịch vụ của lượt mà KHÔNG truy được tới từng dòng: lần thu đang chờ
#: hoặc đã từng nhận tiền nhưng không có dòng hoá đơn nào, hoặc dòng ``payment``
#: dịch vụ không trỏ tới lần thu có dòng hoá đơn (SELECTION §9, FINANCE-GATE §4
#: bước 2). Không suy phân bổ từ số tiền, trạng thái hay hình chiếu payment.
THU_CU_KHONG_TRUY_DUOC_SQL = """
SELECT EXISTS (
           SELECT 1 FROM public.payment_cycle c
            WHERE c.clinic_id = $1::uuid AND c.visit_id = $2::uuid
              AND c.kind = 'dich_vu'
              AND c.status IN ('PENDING_VERIFICATION', 'PAID')
              AND NOT EXISTS (
                  SELECT 1 FROM public.payment_bill_line bl
                   WHERE bl.clinic_id = c.clinic_id
                     AND bl.payment_cycle_id = c.payment_cycle_id))
    OR EXISTS (
           SELECT 1 FROM public.payment p
            WHERE p.clinic_id = $1::uuid AND p.visit_id = $2::uuid
              AND p.kind = 'dich_vu'
              AND NOT EXISTS (
                  SELECT 1 FROM public.payment_bill_line bl
                   WHERE bl.clinic_id = p.clinic_id
                     AND bl.payment_cycle_id = p.payment_cycle_id))
"""

THU_CU_KHONG_TRUY_DUOC = (
    "lượt có lần thu dịch vụ cũ không truy được tới từng dòng — cần đối soát"
    " tài chính trước khi thu tiếp"
)

#: Chỉ định còn tính tiền được: chưa huỷ / chưa "không làm", chưa bắt đầu, chưa
#: kết thúc. Đã bắt đầu hoặc đã làm xong mà chưa có tiền là BẤT THƯỜNG — để
#: FinanceGate đưa đi đối soát, không thu bù ở quầy (CHECKPOINT §3).
_CON_TINH_TIEN = """
    o.exec_status IN ('authorized', 'assigned')
    AND coalesce(o.execution_status, 'PENDING') = 'PENDING'
"""

_GIA_CHI_DINH = """
SELECT o.id::text AS id, o.service_name, o.service_code,
       coalesce(array_agg(pr.unit_price)
                FILTER (WHERE pr.unit_price IS NOT NULL), '{{}}') AS gia,
       coalesce(array_agg(DISTINCT pr.billing_owner)
                FILTER (WHERE pr.billing_owner IS NOT NULL), '{{}}') AS ben_thu
  FROM public.service_order o
  LEFT JOIN public.service_price pr
    ON pr.clinic_id = o.clinic_id AND pr.service_code = o.service_code
   AND pr.active AND pr."group" = 'dich_vu'
 WHERE o.clinic_id = $1::uuid AND o.visit_id = $2::uuid
   AND {dieu_kien}
 GROUP BY o.id, o.service_name, o.service_code, o.created_at
 ORDER BY o.created_at, o.id
"""


async def _kham(
    conn: asyncpg.Connection, clinic_id: str, visit_id: str
) -> dict[str, Any] | None:
    gia_dv = await conn.fetch(
        """
        SELECT name, unit_price, billing_owner FROM public.service_price
         WHERE clinic_id = $1::uuid AND active AND "group" = 'dich_vu'
           AND unit_price IS NOT NULL
        """,
        clinic_id,
    )
    kham_row = await conn.fetchrow(
        """
        SELECT st.id::text AS st_id, st.name,
               (vi.appointment_id IS NULL) AS khong_hen,
               -- Tái khám: khách đã có lượt HOÀN TẤT cùng loại khám trước lượt này.
               EXISTS (
                   SELECT 1 FROM public.appointment a0
                    WHERE a0.clinic_id = vi.clinic_id
                      AND a0.clinic_patient_id = vi.clinic_patient_id
                      AND a0.service_type_id = st.id
                      AND a0.status = 'COMPLETED'
                      AND a0.id IS DISTINCT FROM vi.appointment_id
                      AND a0.slot_start < coalesce(a.slot_start, vi.created_at)
               ) AS tai_kham,
               -- Dây H2 (24/09/2026): lịch "đi thẳng phòng" mà khách đi thẳng
               -- phòng thật (không qua bác sĩ) thì KHÔNG có buổi khám nào để
               -- tính tiền khám — tiền là của chính chỉ định. Rơi về bác sĩ
               -- chính (không có chỉ định mang sang) thì vẫn tính như lượt khám.
               (coalesce(st.di_thang_phong, false)
                AND coalesce(ef.route_decision, 'SERVICES') = 'SERVICES')
                   AS khong_kham
          FROM public.visit vi
          LEFT JOIN public.appointment a
            ON a.id = vi.appointment_id AND a.clinic_id = vi.clinic_id
          LEFT JOIN public.service_type st
            ON st.id = coalesce(vi.service_type_id, a.service_type_id)
          LEFT JOIN public.encounter_flow ef
            ON ef.clinic_id = vi.clinic_id AND ef.visit_id = vi.visit_id
         WHERE vi.clinic_id = $1::uuid AND vi.visit_id = $2::uuid
        """,
        clinic_id,
        visit_id,
    )
    if kham_row is not None and kham_row["khong_kham"]:
        return None
    return dong_kham(kham_row, gia_dv)


def _chi_dinh(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for o in rows:
        ben, van_de = giai_ben_thu(list(o["ben_thu"]))
        out.append(
            {
                "id": o["id"],
                "ten": o["service_name"],
                "service_code": o["service_code"],
                "gia": list(o["gia"]),
                "ben_thu": ben,
                **({"van_de": van_de} if van_de else {}),
            }
        )
    return out


async def hoa_don_con_no(
    conn: asyncpg.Connection,
    *,
    clinic_id: str,
    visit_id: str,
    coi_nhu_chon: Sequence[str] = (),
) -> HoaDon:
    """OUTSTANDING BILL dịch vụ (Lifecycle v1 Slice 3).

    Chỉ những gì phòng khám CÒN phải thu của lượt:
      * tiền khám — nếu chưa có lần thu nào đang giữ phủ nó;
      * chỉ định khách đã CHỌN (SELECTED), còn tính tiền được, chưa được phủ.
    Không vào: chưa chọn / không chọn / dòng cũ NULL, đã huỷ, không làm, đã
    bắt đầu hoặc bị gián đoạn, đối tác tự thu, đang chờ xác minh, đã từng thu
    (kể cả đã huỷ phiếu hay đã hoàn — không tự thu lại).

    ``coi_nhu_chon`` (quầy thu một hoá đơn, 27/09/2026): các chỉ định CÒN CHỜ
    KHÁCH QUYẾT được tính NHƯ ĐÃ CHỌN — hoá đơn DỰ KIẾN nếu khách làm đúng như
    mặc định của quầy. Cùng một câu SQL, cùng luật giá, nên sau khi lệnh thu
    gộp chốt đúng lựa chọn ấy, hoá đơn thật có đúng ``revision`` này. Chỉ đọc —
    không ghi gì. Rỗng = hoá đơn thật (mọi nơi khác gọi như cũ).
    """
    unknown = bool(await conn.fetchval(THU_CU_KHONG_TRUY_DUOC_SQL, clinic_id, visit_id))
    kham = await _kham(conn, clinic_id, visit_id)
    exam_phu = await conn.fetchval(
        "SELECT " + _DA_PHU.format(loai="'exam'", nguon="$2"),
        clinic_id,
        f"exam-{visit_id}",
    )
    rows = await conn.fetch(
        _GIA_CHI_DINH.format(
            dieu_kien=f"""
            (o.selection_status = 'SELECTED'
             OR (o.selection_status = 'PENDING' AND o.id::text = ANY($3::text[])))
            AND {_CON_TINH_TIEN}
            AND NOT {_DA_PHU.format(loai="'service_order'", nguon="o.id::text")}
            """
        ),
        clinic_id,
        visit_id,
        sorted({str(i) for i in coi_nhu_chon}),
    )
    hd = ghep_dich_vu(visit_id, None if exam_phu else kham, _chi_dinh(rows))
    # Đối tác tự thu không phải khoản của phòng khám — không vào hoá đơn thu,
    # nhưng vẫn HIỆN ở quầy (27/09/2026).
    tach_doi_tac(hd)
    if hd.dong_doi_tac:
        hd.doi_tac_da_thu = await doi_tac_da_thu(
            conn, clinic_id, [d.source_id for d in hd.dong_doi_tac]
        )
    if unknown:
        hd.van_de_luot.append(THU_CU_KHONG_TRUY_DUOC)
    return hd


async def doi_tac_da_thu(
    conn: asyncpg.Connection, clinic_id: str, order_ids: Sequence[str]
) -> dict[str, dict[str, Any]]:
    """Ghi nhận ĐỐI TÁC ĐÃ THU còn hiệu lực của các chỉ định (bảng của khối Đối
    tác, `doi_tac_thanh_toan`) — để quầy / Xem lượt nói "Đối tác đã thu"."""
    ids = sorted({str(i) for i in order_ids if i})
    if not ids:
        return {}
    rows = await conn.fetch(
        """
        SELECT service_order_id::text AS id, so_tien, hinh_thuc, ghi_luc
          FROM public.doi_tac_thanh_toan
         WHERE clinic_id = $1::uuid AND service_order_id = ANY($2::uuid[])
           AND huy_luc IS NULL
        """,
        clinic_id,
        ids,
    )
    return {
        r["id"]: {
            "so_tien": int(r["so_tien"]),
            "hinh_thuc": r["hinh_thuc"],
            "luc": r["ghi_luc"].isoformat(),
        }
        for r in rows
    }


async def chi_doi_tac_thu_luot(
    conn: asyncpg.Connection, *, clinic_id: str, visit_id: str
) -> bool:
    """Lượt KHÔNG có khoản nào phòng khám phải thu, và có dịch vụ khách trả trực
    tiếp cho đối tác (27/09/2026) — check-out không đòi phiếu thu dịch vụ.

    Đúng hoá đơn còn nợ của quầy; dịch vụ đối tác đã làm xong thì rời hoá đơn
    còn nợ, nên hỏi thêm "lượt có chỉ định đối tác thu mà khách đã chọn".
    """
    hd = await hoa_don_con_no(conn, clinic_id=clinic_id, visit_id=visit_id)
    if hd.dong or hd.van_de_luot:
        return False
    if hd.dong_doi_tac:
        return True
    return bool(
        await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM public.service_order o
                  JOIN public.service_price pr
                    ON pr.clinic_id = o.clinic_id AND pr.service_code = o.service_code
                   AND pr.active AND pr."group" = 'dich_vu'
                   AND pr.billing_owner = 'EXTERNAL_PARTNER'
                 WHERE o.clinic_id = $1::uuid AND o.visit_id = $2::uuid
                   AND o.selection_status = 'SELECTED'
                   AND o.exec_status NOT IN ('draft', 'cancelled'))
            """,
            clinic_id,
            visit_id,
        )
    )


async def hoa_don_theo_anh_chup(
    conn: asyncpg.Connection, *, clinic_id: str, visit_id: str, cycle_id: str
) -> HoaDon:
    """Hoá đơn HIỆN TẠI của đúng các nguồn nằm trong ảnh chụp một lần thu.

    Dùng khi xác minh chuyển khoản/QR (Slice 3 §6): tiền khách chuyển là cho
    đúng các dòng đã chụp. Chỉ định mới phát sinh SAU ảnh chụp thuộc lần thu
    sau — không làm lần chờ này "lệch". Chỉ khi CHÍNH nguồn đã chụp đổi giá,
    đổi bên thu, bị huỷ / không làm thì dấu mới khác dấu đã lưu.
    """
    nguon = await conn.fetch(
        "SELECT source_type, source_id FROM public.payment_bill_line"
        " WHERE clinic_id = $1::uuid AND payment_cycle_id = $2::uuid",
        clinic_id,
        cycle_id,
    )
    co_kham = any(r["source_type"] == "exam" for r in nguon)
    ids = sorted(r["source_id"] for r in nguon if r["source_type"] == "service_order")
    kham = await _kham(conn, clinic_id, visit_id) if co_kham else None
    rows = await conn.fetch(
        _GIA_CHI_DINH.format(
            dieu_kien="""
            o.id::text = ANY($3::text[])
            AND o.exec_status NOT IN ('draft', 'cancelled', 'not_performed')
            AND coalesce(o.execution_status, 'PENDING')
                NOT IN ('CANCELLED', 'NOT_PERFORMED')
            """
        ),
        clinic_id,
        visit_id,
        ids,
    )
    return ghep_dich_vu(visit_id, kham, _chi_dinh(rows))


async def tinh_hoa_don(
    conn: asyncpg.Connection, *, clinic_id: str, visit_id: str, kind: str
) -> HoaDon:
    """Đọc dữ liệu chuẩn và dựng hoá đơn. Gọi trong giao dịch của lần thu.

    ``dich_vu`` là OUTSTANDING BILL (``hoa_don_con_no``); ``thuoc`` giữ nguyên.
    """
    if kind not in KINDS:
        raise ValueError(f"kind không hợp lệ: {kind!r}")
    if kind == "dich_vu":
        return await hoa_don_con_no(conn, clinic_id=clinic_id, visit_id=visit_id)

    don = await conn.fetch(
        """
        SELECT r.id::text AS id, r.drug_name_raw, r.quantity_num, r.purchased_qty,
               r.unit, r.refusal_reason, r.drug_catalog_id::text AS drug_catalog_id,
               c.name_base, c.name_raw, c.unit_price AS gia_danh_muc
          FROM public.prescription r
          LEFT JOIN public.drug_catalog c
            ON c.id = r.drug_catalog_id AND c.clinic_id = r.clinic_id
         WHERE r.clinic_id = $1::uuid AND r.visit_id = $2::uuid
           -- CP6: hoá đơn MỚI chỉ gồm đơn hiện hành. Ảnh chụp của lần thu cũ
           -- (payment_bill_line) vẫn trỏ dòng lịch sử — không mất.
           AND r.removed_at IS NULL
         ORDER BY r.created_at, r.id
        """,
        clinic_id,
        visit_id,
    )
    gia_thuoc = await conn.fetch(
        """
        SELECT name, unit_price FROM public.service_price
         WHERE clinic_id = $1::uuid AND active AND "group" = 'thuoc'
           AND unit_price IS NOT NULL
        """,
        clinic_id,
    )
    theo_ten: dict[str, list[Any]] = {}
    for g in gia_thuoc:
        theo_ten.setdefault(norm_name(g["name"]), []).append(g["unit_price"])
    dong: list[dict[str, Any]] = []
    for d in don:
        gia: list[Any] = []
        if d["drug_catalog_id"]:
            if d["gia_danh_muc"] is not None:
                gia.append(d["gia_danh_muc"])
            # Tên CHUẨN của chính thuốc trong danh mục — không phải tên bác sĩ gõ.
            for ten in {norm_name(d["name_base"]), norm_name(d["name_raw"])}:
                if ten:
                    gia.extend(theo_ten.get(ten, []))
        dong.append(
            {
                "id": d["id"],
                "ten": d["drug_name_raw"],
                "quantity_num": d["quantity_num"],
                "purchased_qty": d["purchased_qty"],
                "unit": d["unit"],
                "refusal_reason": d["refusal_reason"],
                "drug_catalog_id": d["drug_catalog_id"],
                "gia": gia,
            }
        )
    return ghep_thuoc(visit_id, dong)
