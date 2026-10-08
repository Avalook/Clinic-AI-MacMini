"""Công nợ khi khách về — chặn check-out còn nợ (Tuyền chốt 01/10/2026).

Sự cố 30/09: khách về mà dịch vụ đã làm chưa thu; check-out cho qua bằng một
câu lý do tự động, không ai thấy nợ. Luật mới:

  * Check-out — kể cả "về giữa chừng" — khi khách còn khoản CHƯA THU thì máy
    chủ CHẶN. Không vượt bằng lý do nữa.
  * Hai đường qua: THU NGAY ở quầy (đường thu có sẵn), hoặc GHI NỢ kèm lý do —
    một dòng ``cong_no`` (CHUA_THU). Thu nợ sau ở quầy → bên nhận ``cong_no``
    đổi dòng sang DA_THU khi lượt hết nợ.

NỢ LÀ GÌ (``no_khi_ve``) — dùng lại luật hoá đơn ``bill_service.hoa_don_con_no``
rồi lọc theo luật Tuyền chốt:

  * Phí khám CHỈ là nợ khi đã chọn dịch vụ khám con trong hồ sơ khám (7 loại
    khám đặt lịch được phép 0đ). Phí khám mặc định vì CHƯA CHỌN — kể cả có giá
    mặc định — không là nợ, không chặn.
  * Chỉ định: chỉ khoản ĐANG LÀM / ĐÃ LÀM mà chưa thu (kể cả khách chưa chốt ở
    quầy — dịch vụ đã làm là đã nhận). Khoản khách không chọn làm, hay chưa làm,
    không tính. Phụ thu đi theo chỉ định cha. Vật tư khách đã được thêm vào hoá
    đơn (C13) là nợ ngay — không gắn chỉ định nào.
  * Thuốc: dòng quầy đã ghi số khách mua (``purchased_qty``) hoặc đã cấp
    (``dispensed_qty``) mà chưa thu. Dòng khách từ chối / mua 0 không tính.
  * Dịch vụ đối tác tự thu không tính (khách trả thẳng đối tác).

Dòng chưa có giá vẫn là nợ (số tiền chưa rõ) — không im lặng bỏ qua.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

import asyncpg

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.core.tran import canh_bao_neu_day
from clinicai.events.catalogue import CongNoDaGhi, CongNoDaHuy
from clinicai.events.emit import emit_event, nguoi
from clinicai.services.bill_service import (
    CLINIC,
    HoaDon,
    hoa_don_con_no,
    tinh_hoa_don,
)
from clinicai.services.moc_kham_xong import kham_xong_sql

DICH_VU = "dich_vu"
#: Trần danh sách truy thu trên báo cáo (tổng không bị cắt).
_TRAN_DS = 500
THUOC = "thuoc"

#: Chỉ định đã/đang làm — khách đã nhận dịch vụ (không tính đã huỷ / không làm).
_DA_LAM_SQL = """
SELECT o.id::text AS id, o.selection_status
  FROM public.service_order o
 WHERE o.clinic_id = $1::uuid AND o.visit_id = $2::uuid
   AND o.exec_status IN ('in_progress', 'performed')
   AND coalesce(o.execution_status, 'PENDING')
       IN ('PENDING', 'IN_PROGRESS', 'COMPLETED')
   AND o.selection_status IN ('SELECTED', 'PENDING')
"""

#: Dòng thuốc khách đã mua / đã cấp mà chưa có lần thu nào giữ phủ.
_THUOC_CHUA_THU_SQL = """
SELECT r.id::text AS id
  FROM public.prescription r
 WHERE r.clinic_id = $1::uuid AND r.visit_id = $2::uuid
   AND r.removed_at IS NULL
   AND r.refusal_reason IS NULL
   AND (coalesce(r.purchased_qty, 0) > 0 OR coalesce(r.dispensed_qty, 0) > 0)
   AND NOT EXISTS (
       SELECT 1 FROM public.payment_bill_line bl
         JOIN public.payment_cycle c
           ON c.clinic_id = bl.clinic_id AND c.payment_cycle_id = bl.payment_cycle_id
        WHERE bl.clinic_id = r.clinic_id
          AND bl.source_type = 'prescription' AND bl.source_id = r.id::text
          AND c.status IN ('PENDING_VERIFICATION', 'PAID'))
   -- Lần thu thuốc ĐỜI CŨ không có dòng hoá đơn: không truy được dòng nào đã
   -- trả — không đoán thành nợ (đối soát tài chính lo).
   AND NOT EXISTS (
       SELECT 1 FROM public.payment_cycle c
        WHERE c.clinic_id = r.clinic_id AND c.visit_id = r.visit_id
          AND c.kind = 'thuoc' AND c.status IN ('PENDING_VERIFICATION', 'PAID')
          AND NOT EXISTS (
              SELECT 1 FROM public.payment_bill_line bl
               WHERE bl.clinic_id = c.clinic_id
                 AND bl.payment_cycle_id = c.payment_cycle_id))
"""

#: Quầy thu DỊCH VỤ nhận lượt này chưa — cùng điều kiện danh sách quầy
#: (`cashier_board_service`) và lệnh thu (`_kiem_luot_thu`): đã khám xong, hoặc
#: đã có chỉ định. Chưa → nút "Thu ngay" không dẫn vào ngõ cụt; chỉ còn Ghi nợ.
_QUAY_NHAN_DV_SQL = (
    """
SELECT ("""
    + kham_xong_sql("v")
    + """
        OR EXISTS (SELECT 1 FROM public.service_order o
                    WHERE o.clinic_id = v.clinic_id AND o.visit_id = v.visit_id
                      AND o.selection_status IS NOT NULL
                      AND o.exec_status NOT IN ('draft', 'cancelled')))
  FROM public.visit v
 WHERE v.clinic_id = $1::uuid AND v.visit_id = $2::uuid
"""
)

_GHI_NO_MO_SQL = """
SELECT n.id::text AS id, n.so_tien, n.ly_do, n.ghi_luc, n.dong,
       s.full_name AS nguoi_ghi
  FROM public.cong_no n
  LEFT JOIN public.staff s ON s.id = n.ghi_boi
 WHERE n.clinic_id = $1::uuid AND n.visit_id = $2::uuid
   AND n.trang_thai = 'CHUA_THU'
"""


def tien_vn(so: int | float | None) -> str:
    """1234000 → "1.234.000"."""
    return f"{int(so or 0):,}".replace(",", ".")


@dataclass(frozen=True)
class DongNo:
    loai: str  # dich_vu | thuoc
    source_type: str  # exam | service_order | phu_thu | vat_tu | prescription
    source_id: str
    ten: str
    #: None = chưa có giá (vẫn là nợ, số tiền chưa rõ).
    so_tien: int | None
    van_de: str | None = None

    def cho_api(self) -> dict[str, Any]:
        return {
            "loai": self.loai,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "ten": self.ten,
            "so_tien": self.so_tien,
            "van_de": self.van_de,
        }


@dataclass
class NoKhiVe:
    visit_id: str
    dong: list[DongNo] = field(default_factory=list)
    #: Khoản nợ đã ghi, còn CHƯA THU (tối đa một dòng mỗi lượt).
    ghi_no: dict[str, Any] | None = None
    #: Quầy thu nhận được lượt này ngay chưa, theo loại (dich_vu / thuoc).
    thu_ngay: dict[str, bool] = field(default_factory=dict)

    @property
    def tong(self) -> int:
        return sum(d.so_tien or 0 for d in self.dong)

    @property
    def phu_boi_ghi_no(self) -> bool:
        """Mọi khoản nợ HIỆN TẠI đều nằm trong lần ghi nợ còn hiệu lực."""
        if not self.dong or self.ghi_no is None:
            return False
        da_ghi = {str(d.get("source_id")) for d in self.ghi_no.get("dong") or []}
        return all(d.source_id in da_ghi for d in self.dong)

    @property
    def chan(self) -> bool:
        """Còn nợ mà chưa ghi nợ phủ đủ → check-out bị chặn."""
        return bool(self.dong) and not self.phu_boi_ghi_no

    def loai_co_no(self) -> set[str]:
        return {d.loai for d in self.dong}

    def cau_chan(self) -> str:
        chua_gia = sum(1 for d in self.dong if d.so_tien is None)
        them = f" (+{chua_gia} khoản chưa có giá)" if chua_gia else ""
        return (
            f"Khách còn nợ {tien_vn(self.tong)}đ{them} — thu ngay ở quầy hoặc"
            ' bấm "Ghi nợ" (kèm lý do) rồi mới check-out được.'
        )

    def cho_api(self) -> dict[str, Any]:
        return {
            "tong": self.tong,
            "dong": [d.cho_api() for d in self.dong],
            "chan": self.chan,
            "thu_ngay": self.thu_ngay,
            "ghi_no": (
                None
                if self.ghi_no is None
                else {
                    "id": self.ghi_no["id"],
                    "so_tien": int(self.ghi_no["so_tien"]),
                    "ly_do": self.ghi_no["ly_do"],
                    "nguoi_ghi": self.ghi_no.get("nguoi_ghi"),
                    "luc": self.ghi_no["ghi_luc"].isoformat()
                    if self.ghi_no.get("ghi_luc")
                    else None,
                    "phu_du": self.phu_boi_ghi_no,
                }
            ),
        }


def loc_no_dich_vu(hd: HoaDon, da_lam: Iterable[str]) -> list[DongNo]:
    """Khoản DỊCH VỤ của hoá đơn còn nợ mà là NỢ khi khách về. Thuần.

    ``da_lam`` = id chỉ định đang/đã làm. Xem luật ở đầu file.
    """
    lam = {str(i) for i in da_lam}
    out: list[DongNo] = []
    for d in hd.dong:
        if d.ben_thu != CLINIC:
            continue
        if d.source_type == "exam":
            # Chỉ dịch vụ khám con ĐÃ CHỌN (`exam-{visit}-selected-{id}`).
            if "-selected-" not in d.source_id:
                continue
        elif d.source_type == "service_order":
            if d.source_id not in lam:
                continue
        elif d.source_type == "phu_thu":
            if d.order_id not in lam:
                continue
        elif d.source_type == "vat_tu":
            # Vật tư khách đã được thêm vào hoá đơn (C13, 01/10/2026): đã lấy
            # là đã nhận — còn nợ thì chặn check-out như mọi khoản dịch vụ.
            pass
        else:
            # Trả trước liệu trình chưa thu (08/10/2026) không phải nợ: khách
            # chưa nhận buổi nào bằng khoản ấy — bỏ dòng là xong.
            continue
        so = None if d.thanh_tien is None else int(d.thanh_tien)
        if so is not None and so <= 0:
            continue
        out.append(
            DongNo(
                loai=DICH_VU,
                source_type=d.source_type,
                source_id=d.source_id,
                ten=d.ten,
                so_tien=so,
                van_de=d.van_de,
            )
        )
    return out


def loc_no_thuoc(hd: HoaDon, chua_thu: Iterable[str]) -> list[DongNo]:
    """Khoản THUỐC còn nợ: dòng hoá đơn thuốc thuộc tập đã mua/cấp chưa thu."""
    ids = {str(i) for i in chua_thu}
    out: list[DongNo] = []
    for d in hd.dong:
        if d.source_id not in ids:
            continue
        so = None if d.thanh_tien is None else int(d.thanh_tien)
        if so is not None and so <= 0:
            continue
        out.append(
            DongNo(
                loai=THUOC,
                source_type=d.source_type,
                source_id=d.source_id,
                ten=d.ten,
                so_tien=so,
                van_de=d.van_de,
            )
        )
    return out


async def no_khi_ve(
    conn: asyncpg.Connection,
    *,
    clinic_id: str,
    visit_id: str,
    hd_dich_vu: HoaDon | None = None,
) -> NoKhiVe:
    """Khách còn nợ gì nếu về bây giờ — cùng một hàm cho check-out, ghi nợ,
    bên nhận ``cong_no`` và báo cáo.

    ``hd_dich_vu``: hoá đơn còn nợ nơi gọi đã dựng (không ``coi_nhu_chon``) —
    dùng lại khi lượt không có chỉ định đã làm mà khách chưa chốt.
    """
    da_lam = await conn.fetch(_DA_LAM_SQL, clinic_id, visit_id)
    chua_chot = [r["id"] for r in da_lam if r["selection_status"] == "PENDING"]
    if hd_dich_vu is None or chua_chot:
        hd_dich_vu = await hoa_don_con_no(
            conn, clinic_id=clinic_id, visit_id=visit_id, coi_nhu_chon=chua_chot
        )
    no = NoKhiVe(
        visit_id=visit_id,
        dong=loc_no_dich_vu(hd_dich_vu, [r["id"] for r in da_lam]),
    )
    thuoc_ids = [
        r["id"] for r in await conn.fetch(_THUOC_CHUA_THU_SQL, clinic_id, visit_id)
    ]
    if thuoc_ids:
        hd_thuoc = await tinh_hoa_don(
            conn, clinic_id=clinic_id, visit_id=visit_id, kind=THUOC
        )
        no.dong.extend(loc_no_thuoc(hd_thuoc, thuoc_ids))
    loai = no.loai_co_no()
    if DICH_VU in loai:
        no.thu_ngay[DICH_VU] = bool(
            await conn.fetchval(_QUAY_NHAN_DV_SQL, clinic_id, visit_id)
        )
    if THUOC in loai:
        # Dòng thuốc nợ là dòng của đơn còn hiệu lực → quầy thuốc nhận.
        no.thu_ngay[THUOC] = True
    ghi = await conn.fetchrow(_GHI_NO_MO_SQL, clinic_id, visit_id)
    if ghi is not None:
        g = dict(ghi)
        if isinstance(g.get("dong"), str):
            g["dong"] = json.loads(g["dong"])
        no.ghi_no = g
    return no


#: Lọc khoản nợ theo cơ sở của lượt ($2 rỗng = mọi cơ sở). Hằng cố định, không
#: ghép đầu vào người dùng vào chuỗi SQL.
_NO_CO_SO_JOIN = """
          LEFT JOIN public.visit nv
            ON nv.visit_id = n.visit_id AND nv.clinic_id = n.clinic_id
          LEFT JOIN public.appointment na
            ON na.id = nv.appointment_id AND na.clinic_id = nv.clinic_id"""
_NO_CO_SO_LOC = (
    "($2::uuid IS NULL OR coalesce(nv.location_id, na.location_id) = $2::uuid)"
)


async def doc_khach_con_no(
    conn: asyncpg.Connection,
    clinic_id: str,
    *,
    kem_ds: bool = True,
    location_id: str | None = None,
) -> dict[str, Any]:
    """ "Khách còn nợ: n — x đ" — mọi khoản đã ghi nợ còn CHƯA THU.

    Tổng đếm bằng SQL (không bị trần danh sách cắt); ``kem_ds`` thêm danh sách
    truy thu (mới nhất trước, tối đa ``_TRAN_DS`` dòng, ``bi_cat`` nói ra).
    ``location_id`` (08/10/2026): chỉ khoản nợ của lượt thuộc cơ sở ấy (cơ sở
    của lượt = ``coalesce(visit.location_id, appointment.location_id)``).
    """
    tong = await conn.fetchrow(
        f"""
        SELECT count(DISTINCT n.clinic_patient_id) AS so_khach,
               count(*) AS so_luot, coalesce(sum(n.so_tien), 0) AS so_tien
          FROM public.cong_no n
          {_NO_CO_SO_JOIN}
         WHERE n.clinic_id = $1::uuid AND n.trang_thai = 'CHUA_THU'
           AND {_NO_CO_SO_LOC}
        """,
        clinic_id,
        location_id,
    )
    out: dict[str, Any] = {
        "so_khach": int(tong["so_khach"] or 0) if tong else 0,
        "so_luot": int(tong["so_luot"] or 0) if tong else 0,
        "so_tien": int(tong["so_tien"] or 0) if tong else 0,
    }
    if not kem_ds:
        return out
    rows = await conn.fetch(
        f"""
        SELECT n.id::text AS id, n.visit_id::text AS visit_id,
               n.so_tien, n.ly_do, n.ghi_luc,
               p.full_name AS khach, p.patient_code AS ma_bn,
               s.full_name AS nguoi_ghi
          FROM public.cong_no n
          LEFT JOIN public.patient p ON p.clinic_patient_id = n.clinic_patient_id
          LEFT JOIN public.staff s ON s.id = n.ghi_boi
          {_NO_CO_SO_JOIN}
         WHERE n.clinic_id = $1::uuid AND n.trang_thai = 'CHUA_THU'
           AND {_NO_CO_SO_LOC}
         ORDER BY n.ghi_luc DESC
         LIMIT $3
        """,
        clinic_id,
        location_id,
        _TRAN_DS,
    )
    out["bi_cat"] = canh_bao_neu_day("cong_no.khach_con_no", len(rows), _TRAN_DS)
    out["ds"] = [
        {
            "id": r["id"],
            "visit_id": r["visit_id"],
            "khach": r["khach"],
            "ma_bn": r["ma_bn"],
            "so_tien": int(r["so_tien"]),
            "ly_do": r["ly_do"],
            "nguoi_ghi": r["nguoi_ghi"],
            "luc": r["ghi_luc"].isoformat(),
        }
        for r in rows
    ]
    return out


async def _khoa_luot(
    conn: asyncpg.Connection, clinic_id: str, visit_id: str
) -> asyncpg.Record:
    """Cùng khoá lượt với check-out / thu tiền — không có cửa sổ lệch."""
    luot = await conn.fetchrow(
        "SELECT clinic_patient_id::text AS clinic_patient_id, closed_at"
        "  FROM public.visit WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
        "   FOR UPDATE",
        clinic_id,
        visit_id,
    )
    if luot is None:
        raise ValidationError("Không tìm thấy lượt khám ở phòng khám này.")
    return luot


def _ly_do(ly_do: str | None, *, viec: str) -> str:
    s = (ly_do or "").strip()
    if len(s) < 3:
        raise ValidationError(f"{viec} thì phải ghi lý do (ít nhất 3 ký tự).")
    if len(s) > 500:
        raise ValidationError("Lý do dài quá 500 ký tự.")
    return s


class CongNoService:
    """Lệnh của khối Công nợ: Ghi nợ / Huỷ ghi nợ."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def ghi(
        self, *, identity: StaffIdentity, visit_id: str, ly_do: str | None
    ) -> dict[str, Any]:
        """Ghi nợ TOÀN BỘ khoản khách còn nợ của lượt, kèm lý do.

        Đã có khoản ghi nợ CHƯA THU thì ghi đè chính dòng ấy bằng nợ hiện tại
        (nợ phát sinh thêm sau lần ghi trước) — sự kiện giữ dấu từng lần.
        """
        s = _ly_do(ly_do, viec="Ghi nợ")
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                luot = await _khoa_luot(conn, identity.clinic_id, visit_id)
                no = await no_khi_ve(
                    conn, clinic_id=identity.clinic_id, visit_id=visit_id
                )
                if not no.dong:
                    raise ValidationError(
                        "Lượt này không còn khoản nào chưa thu — không cần ghi nợ."
                    )
                dong = json.dumps([d.cho_api() for d in no.dong], ensure_ascii=False)
                if no.ghi_no is not None:
                    cong_no_id = await conn.fetchval(
                        """
                        UPDATE public.cong_no
                           SET so_tien = $3, dong = $4::jsonb, ly_do = $5,
                               ghi_boi = $6::uuid, ghi_luc = now()
                         WHERE clinic_id = $1::uuid AND id = $2::uuid
                           AND trang_thai = 'CHUA_THU'
                        RETURNING id::text
                        """,
                        identity.clinic_id,
                        no.ghi_no["id"],
                        no.tong,
                        dong,
                        s,
                        identity.staff_id,
                    )
                else:
                    cong_no_id = await conn.fetchval(
                        """
                        INSERT INTO public.cong_no
                            (clinic_id, visit_id, clinic_patient_id, so_tien,
                             dong, ly_do, ghi_boi)
                        VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5::jsonb, $6,
                                $7::uuid)
                        RETURNING id::text
                        """,
                        identity.clinic_id,
                        visit_id,
                        luot["clinic_patient_id"],
                        no.tong,
                        dong,
                        s,
                        identity.staff_id,
                    )
                await emit_event(
                    conn,
                    ten="cong_no.ghi",
                    clinic_id=identity.clinic_id,
                    aggregate_id=cong_no_id,
                    payload=CongNoDaGhi(
                        visit_id=visit_id,
                        cong_no_id=cong_no_id,
                        so_tien=no.tong,
                        so_khoan=len(no.dong),
                        ly_do=s,
                    ),
                    boi=nguoi(identity),
                    correlation_id=visit_id,
                )
        return {
            "ok": True,
            "cong_no_id": cong_no_id,
            "so_tien": no.tong,
            "so_khoan": len(no.dong),
        }

    async def huy(
        self, *, identity: StaffIdentity, visit_id: str, ly_do: str | None
    ) -> dict[str, Any]:
        """Huỷ lần ghi nợ (bấm nhầm) — chỉ khi khách CHƯA check-out.

        Lượt đã đóng mà huỷ nợ thì lượt ấy thành "đã về, còn nợ, không ai
        ghi" — đúng thứ luật này chặn. Muốn xoá nợ sau khi về: thu ở quầy.
        """
        s = _ly_do(ly_do, viec="Huỷ ghi nợ")
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                luot = await _khoa_luot(conn, identity.clinic_id, visit_id)
                if luot["closed_at"] is not None:
                    raise ValidationError(
                        "Khách đã check-out — khoản nợ chỉ hết khi thu ở quầy."
                    )
                row = await conn.fetchrow(
                    """
                    UPDATE public.cong_no
                       SET trang_thai = 'HUY', huy_luc = now(),
                           huy_boi = $3::uuid, ly_do_huy = $4
                     WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                       AND trang_thai = 'CHUA_THU'
                    RETURNING id::text AS id, so_tien
                    """,
                    identity.clinic_id,
                    visit_id,
                    identity.staff_id,
                    s,
                )
                if row is None:
                    raise ValidationError("Lượt này không có khoản ghi nợ nào để huỷ.")
                await emit_event(
                    conn,
                    ten="cong_no.huy",
                    clinic_id=identity.clinic_id,
                    aggregate_id=row["id"],
                    payload=CongNoDaHuy(
                        visit_id=visit_id,
                        cong_no_id=row["id"],
                        so_tien=int(row["so_tien"]),
                        ly_do=s,
                    ),
                    boi=nguoi(identity),
                    correlation_id=visit_id,
                )
        return {"ok": True, "cong_no_id": row["id"]}


__all__ = [
    "CongNoService",
    "DongNo",
    "NoKhiVe",
    "doc_khach_con_no",
    "loc_no_dich_vu",
    "loc_no_thuoc",
    "no_khi_ve",
    "tien_vn",
]
