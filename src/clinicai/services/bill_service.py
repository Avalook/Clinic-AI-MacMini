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
from collections.abc import Mapping
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

    @property
    def dong_thu(self) -> list[DongHoaDon]:
        """Dòng phòng khám thu (bỏ dòng đối tác tự thu)."""
        return [d for d in self.dong if d.ben_thu == CLINIC]

    @property
    def van_de(self) -> list[str]:
        return [f"{d.ten}: {d.van_de}" for d in self.dong_thu if d.van_de]

    @property
    def tong(self) -> int:
        return int(sum((d.thanh_tien or Decimal(0)) for d in self.dong_thu))

    @property
    def thu_duoc(self) -> bool:
        return not self.van_de and self.tong > 0

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
            "dong": [
                {
                    **{k: v for k, v in asdict(d).items()},
                    "so_luong": float(d.so_luong),
                    "don_gia": float(d.don_gia) if d.don_gia is not None else None,
                    "thanh_tien": (
                        float(d.thanh_tien) if d.thanh_tien is not None else None
                    ),
                }
                for d in self.dong
            ],
        }


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
            van_de = "chưa có giá"
        elif len(khac_nhau) > 1:
            van_de = (
                "giá mâu thuẫn giữa các bảng giá ("
                + " / ".join(f"{int(g):,}đ".replace(",", ".") for g in khac_nhau)
                + ")"
            )
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


KHAM_KHONG_HEN = "chưa xác định loại khám (lượt không có lịch hẹn)"
KHAM_KHONG_RO_LOAI = "chưa xác định loại khám"


def dong_kham(
    kham_row: Mapping[str, Any] | None, gia_dv: list[Mapping[str, Any]]
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
    if kham_row["khong_hen"]:
        van_de = KHAM_KHONG_HEN
    elif clean_name(kham_row["name"]):
        khop = [
            r for r in gia_dv if norm_name(r["name"]) == norm_name(kham_row["name"])
        ]
        return {
            "ma": kham_row["st_id"],
            "ten": kham_row["name"],
            "gia": [r["unit_price"] for r in khop],
            "ben_thu": khop[0]["billing_owner"] if khop else CLINIC,
        }
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
            van_de = "chưa xác định thuốc trong kho"
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


async def tinh_hoa_don(
    conn: asyncpg.Connection, *, clinic_id: str, visit_id: str, kind: str
) -> HoaDon:
    """Đọc dữ liệu chuẩn và dựng hoá đơn. Gọi trong giao dịch của lần thu."""
    if kind not in KINDS:
        raise ValueError(f"kind không hợp lệ: {kind!r}")
    if kind == "dich_vu":
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
                   (vi.appointment_id IS NULL) AS khong_hen
              FROM public.visit vi
              LEFT JOIN public.appointment a
                ON a.id = vi.appointment_id AND a.clinic_id = vi.clinic_id
              LEFT JOIN public.service_type st ON st.id = a.service_type_id
             WHERE vi.clinic_id = $1::uuid AND vi.visit_id = $2::uuid
            """,
            clinic_id,
            visit_id,
        )
        kham = dong_kham(kham_row, gia_dv)
        orders = await conn.fetch(
            """
            SELECT o.id::text AS id, o.service_name, o.service_code,
                   coalesce(array_agg(pr.unit_price)
                            FILTER (WHERE pr.unit_price IS NOT NULL), '{}') AS gia,
                   coalesce(max(pr.billing_owner), 'CLINIC') AS ben_thu
              FROM public.service_order o
              LEFT JOIN public.service_price pr
                ON pr.clinic_id = o.clinic_id AND pr.service_code = o.service_code
               AND pr.active AND pr."group" = 'dich_vu'
             WHERE o.clinic_id = $1::uuid AND o.visit_id = $2::uuid
               AND o.exec_status NOT IN ('draft', 'cancelled', 'not_performed')
             GROUP BY o.id, o.service_name, o.service_code, o.created_at
             ORDER BY o.created_at, o.id
            """,
            clinic_id,
            visit_id,
        )
        return ghep_dich_vu(
            visit_id,
            kham,
            [
                {
                    "id": o["id"],
                    "ten": o["service_name"],
                    "service_code": o["service_code"],
                    "gia": list(o["gia"]),
                    "ben_thu": o["ben_thu"],
                }
                for o in orders
            ],
        )

    don = await conn.fetch(
        """
        SELECT r.id::text AS id, r.drug_name_raw, r.quantity_num, r.purchased_qty,
               r.unit, r.refusal_reason, r.drug_catalog_id::text AS drug_catalog_id,
               c.name_base, c.name_raw, c.unit_price AS gia_danh_muc
          FROM public.prescription r
          LEFT JOIN public.drug_catalog c
            ON c.id = r.drug_catalog_id AND c.clinic_id = r.clinic_id
         WHERE r.clinic_id = $1::uuid AND r.visit_id = $2::uuid
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
