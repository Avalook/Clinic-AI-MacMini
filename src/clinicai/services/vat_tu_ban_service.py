"""Bán vật tư trừ kho ĐÚNG PHÒNG + danh sách đối soát (Tuyền 31/10/2026).

"Không thêm việc cho nhân sự lúc vận hành; trừ thật, hoàn tác thì số quay lại
đúng." BS phòng Sản đưa đầu dò, lễ tân thu ở chỗ khác → vẫn trừ ở phòng Sản.

MỖI NGUỒN BÁN MỘT DÒNG `vat_tu_ban` (dòng `luot_vat_tu` của quầy dịch vụ / Bio theo
chỉ định, dòng đơn của quầy thuốc). Dòng là trạng thái hiện tại; lịch sử nằm ở sổ
phiếu chỉ thêm: BAN khi trừ, HOAN khi đảo.

ĐỒNG BỘ, KHÔNG CỘNG TRỪ: `dong_bo_ban_vat_tu` so "số phải đang trừ" với "số đang
trừ" rồi sửa cho khớp, nên thu, hoàn tác, bỏ chỉ định, thu lại, sự kiện giao hai lần
đều gọi đúng một hàm và ra một kết quả. Đổi số = đảo cả phiếu cũ rồi lập phiếu mới:
sổ không cho đảo một phần.

SỐ PHẢI ĐANG TRỪ của một nguồn = số bán − số khách đã trả lại:
  * Lần thu giữ phủ (đã thu HOẶC chuyển khoản chờ xác minh): hàng đã đi theo cùng
    luật khách đi tiếp ở quầy. Huỷ lần chờ / hoàn tác lần thu → số về. Thu 0đ (miễn
    phí 100%) vẫn là một lần thu nên vẫn trừ.
  * Chưa thu mà dịch vụ đã làm ("làm trước, thu sau", ghi nợ): dòng đi theo chỉ định
    vẫn trừ. Vì vậy hoàn tác lần thu của dịch vụ ĐÃ LÀM thì số KHÔNG về: hàng đã
    dùng, khách thành nợ.
  * Chỉ định huỷ / không làm / khách bỏ: 0, kể cả dòng đã thu (tiền hoàn ở quầy).
  * HOÀN TIỀN KHÔNG làm hàng tự về: dòng ghi `so_hoan_tien`, hiện "chờ người kho xử
    lý"; số chỉ về khi có người nhận lại hàng (`nhan_lai_hang`, hoặc tick "Khách trả
    lại hàng" ở Hoàn tiền của cả hai quầy).

Nơi lấy: phòng của chỉ định → phòng bác sĩ khám của lượt → "Chờ gán phòng". Không
đoán: phòng đã tắt / cơ sở khác / phòng đối tác, nhiều bác sĩ trong lượt, bác sĩ hai
phòng không phân được ca đều về chờ gán. Người kho gán rồi (`noi_nguon = KHO`) thì máy
không tự đổi nữa. Chỉ định thường được xếp phòng SAU khi thu (bên nhận `hanh_trinh`),
nên `events/consumers/vat_tu_ban.py` đồng bộ lại khi chỉ định đổi trạng thái.

Chỉ tạo dòng từ LẦN THU MỚI hoặc dòng `luot_vat_tu.tru_kho`: khoản bán trước khi có
tính năng này không bao giờ bị trừ bù.

Khoá theo thứ tự chung: lượt → dòng bán → khoá cơ sở vật tư → tồn.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Any

import asyncpg

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.core.clock import CLINIC_TZ, hom_nay_vn
from clinicai.core.shifts import Window, ca_tu_settings, covers, shift_windows
from clinicai.core.tran import canh_bao_neu_day
from clinicai.services.audit import record_event
from clinicai.services.bac_si_phu_trach import bac_si_cua_phien
from clinicai.services.kho_thuoc_service import _khoa, dau_ngay_vn, khoang_xnt
from clinicai.services.vat_tu_kho_man_service import _ma_hoac_rong
from clinicai.services.vat_tu_kho_service import (
    NguoiKho,
    _dao_phieu,
    _ghi,
    _gia_chua_khai,
    _khoa_co_so,
    _mo_phieu,
    _so,
    _ton,
    _uuid,
    gia_nhap_gan_nhat,
)
from clinicai.services.vat_tu_trung_ma import VAT_TU_CUA_THUOC

DA_TRU = "DA_TRU"
CHO_GAN_PHONG = "CHO_GAN_PHONG"
DA_HOAN = "DA_HOAN"
NHAP_BU = "NHAP_BU"
_TEN_TRANG_THAI = {
    DA_TRU: "Đã trừ kho",
    CHO_GAN_PHONG: "Chờ gán phòng",
    DA_HOAN: "Đã hoàn lại kho",
}
_TEN_NGUON = {
    "QUAY_DICH_VU": "Quầy dịch vụ",
    "CHI_DINH": "Theo chỉ định",
    "QUAY_THUOC": "Quầy thuốc",
    NHAP_BU: "Nhập bù",
}

LY_DO_CHUA_RO_PHONG = "Chưa xác định được lấy từ phòng nào — chọn phòng giúp."
LY_DO_DA_LAM = "Dịch vụ đã làm nên giữ số đã trừ"

#: Trần một lần đọc danh sách. Chạm trần → màn báo thu hẹp ngày, log kêu.
TRAN_DANH_SACH = 1000


@dataclass(frozen=True)
class NguoiGhi:
    """Người ghi sổ + cơ sở của DÒNG BÁN (có thể khác cơ sở người bấm đang đứng)."""

    clinic_id: str
    location_id: str
    staff_id: str


@dataclass(frozen=True)
class Noi:
    lay: str  # PHONG | KHO
    room_id: str | None
    nguon: str  # CHI_DINH | BAC_SI | KHO


def chon_noi(
    hien_tai: Noi | None, phong_chi_dinh: str | None, phong_bac_si: str | None
) -> Noi | None:
    """Nơi lấy của một dòng — hàm thuần. Người kho đã gán thì giữ; phòng chỉ định
    thắng phòng máy suy trước đó; không có gì thì None = "Chờ gán phòng"."""
    if hien_tai is not None and hien_tai.nguon == "KHO":
        return hien_tai
    if phong_chi_dinh:
        return Noi("PHONG", phong_chi_dinh, "CHI_DINH")
    if hien_tai is not None:
        return hien_tai
    return Noi("PHONG", phong_bac_si, "BAC_SI") if phong_bac_si else None


def phong_cua_bac_si(
    dong: list[tuple[str, str, str]], phut: int | None, ca: dict[str, Window]
) -> str | None:
    """Phòng của bác sĩ theo lịch — hàm thuần. `dong`: (phòng, ca, trạng thái).

    Lúc khách khám rơi vào ca nào thì lấy phòng ca đó; ngoài ca thì xét cả ngày.
    Hai phòng mà không phân được → None: thà để người kho gán còn hơn trừ nhầm."""
    song = [d for d in dong if d[2] != "REJECTED"]
    dang = (
        [d for d in song if covers(shift_windows(d[1], 0, 24 * 60, ca), phut)]
        if phut is not None
        else []
    )
    phong = {d[0] for d in (dang or song)}
    return phong.pop() if len(phong) == 1 else None


def so_cho_xu_ly(
    trang_thai: str, so_hoan_tien: Decimal, so_tra: Decimal, so_khong_nhan: Decimal
) -> Decimal:
    """Phần đã hoàn tiền mà người kho chưa nói hàng có về không. Dòng đã hoàn lại
    kho thì không còn gì để xử lý."""
    if trang_thai != DA_TRU:
        return Decimal(0)
    return max(so_hoan_tien - so_tra - so_khong_nhan, Decimal(0))


def _ly_do(raw: Any) -> str:
    ly = " ".join(raw.split()) if isinstance(raw, str) else ""
    if not 5 <= len(ly) <= 500:
        raise ValidationError("Ghi lý do từ 5 đến 500 ký tự.")
    return ly


_DONG_SQL = """
SELECT b.id::text AS id, b.nguon, b.location_id::text AS location_id,
       b.luot_vat_tu_id::text AS luot_vat_tu_id,
       b.prescription_id::text AS prescription_id,
       b.visit_id::text AS visit_id, b.clinic_patient_id::text AS clinic_patient_id,
       b.vat_tu_id::text AS vat_tu_id, b.ten, b.so_luong, b.thanh_tien, b.gia_von,
       b.so_hoan_tien, b.so_tra, b.so_khong_nhan,
       b.payment_cycle_id::text AS payment_cycle_id, b.ban_boi::text AS ban_boi,
       b.noi_lay, b.room_id::text AS room_id, b.noi_nguon, b.trang_thai, b.ly_do,
       b.phieu_id::text AS phieu_id, b.so_phieu
  FROM public.vat_tu_ban b
 WHERE b.clinic_id = $1::uuid AND {dieu_kien}
 ORDER BY b.id
   FOR UPDATE
"""

#: Các dòng hoá đơn của MỘT lần thu mà là vật tư — cả dòng thuốc trùng mã vật tư.
_NGUON_LAN_THU_SQL = f"""
SELECT bl.source_type, bl.source_id, bl.name_snapshot AS ten, bl.unit AS don_vi,
       bl.unit_price, bl.quantity, bl.line_total,
       lv.order_id::text AS order_id,
       coalesce(lv.service_price_id,
                {VAT_TU_CUA_THUOC.format(thuoc="bl.drug_catalog_id")})::text
           AS vat_tu_id
  FROM public.payment_bill_line bl
  LEFT JOIN public.luot_vat_tu lv
    ON bl.source_type = 'vat_tu' AND lv.clinic_id = bl.clinic_id
   AND lv.id::text = bl.source_id
 WHERE bl.clinic_id = $1::uuid AND bl.payment_cycle_id = $2::uuid
   AND (lv.id IS NOT NULL
        OR (bl.source_type = 'prescription' AND bl.drug_catalog_id IS NOT NULL
            AND {VAT_TU_CUA_THUOC.format(thuoc="bl.drug_catalog_id")} IS NOT NULL))
"""

#: Lần thu GIỮ PHỦ một nguồn: số bán, tiền còn lại sau hoàn, số đã hoàn xong.
_SO_CAN_SQL = """
SELECT coalesce(sum(x.so), 0) AS so, coalesce(sum(x.hoan), 0) AS hoan,
       coalesce(sum(x.tien), 0) AS tien,
       (array_agg(x.lan ORDER BY x.luc DESC))[1] AS lan
  FROM (
      SELECT bl.quantity AS so, coalesce(h.so, 0) AS hoan,
             coalesce(bl.line_total, 0) - coalesce(h.tien, 0) AS tien,
             c.payment_cycle_id::text AS lan, c.created_at AS luc
        FROM public.payment_bill_line bl
        JOIN public.payment_cycle c
          ON c.clinic_id = bl.clinic_id
         AND c.payment_cycle_id = bl.payment_cycle_id
        LEFT JOIN LATERAL (
            SELECT sum(rl.quantity) AS so, sum(rl.amount) AS tien
              FROM public.payment_refund_line rl
              JOIN public.payment_refund rf
                ON rf.refund_id = rl.refund_id AND rf.clinic_id = rl.clinic_id
             WHERE rl.clinic_id = bl.clinic_id AND rl.payment_bill_line_id = bl.id
               AND rf.status = 'COMPLETED') h ON true
       WHERE bl.clinic_id = $1::uuid AND bl.source_type = $2 AND bl.source_id = $3
         AND c.status IN ('PENDING_VERIFICATION', 'PAID')
  ) x
"""

_CON_SONG = """(
    o.exec_status NOT IN ('draft', 'cancelled', 'not_performed')
    AND coalesce(o.execution_status, 'PENDING') NOT IN ('CANCELLED', 'NOT_PERFORMED')
    AND o.selection_status IS DISTINCT FROM 'NOT_SELECTED')"""

#: "Đã làm" = đã bắt đầu tới xong: đầu dò đã tới tay khách từ lúc bắt đầu, và hoàn
#: tác "Xong" không làm số nhảy đi nhảy lại.
_DA_LAM = """(
    o.execution_status IN ('IN_PROGRESS', 'COMPLETED', 'INTERRUPTED')
    OR o.exec_status IN ('in_progress', 'performed'))"""

#: Dòng quầy dịch vụ còn sống không, và chỉ định của nó ở phòng nào. Phòng đã tắt,
#: phòng cơ sở khác, phòng đối tác → `co_phong` mà không có `phong_chi_dinh`.
_LUOT_VAT_TU_SQL = f"""
SELECT v.so_luong, v.tru_kho,
       v.bo_luc IS NULL AND (v.order_id IS NULL OR {_CON_SONG}) AS con_ban,
       v.order_id IS NOT NULL AND coalesce({_DA_LAM}, false) AS da_lam,
       coalesce(o.room_id, o.phong_du_kien_id) IS NOT NULL AS co_phong,
       r.id::text AS phong_chi_dinh, v.bo_ly_do, o.cancel_reason,
       o.not_performed_reason, o.selection_status = 'NOT_SELECTED' AS khach_bo
  FROM public.luot_vat_tu v
  LEFT JOIN public.service_order o
    ON o.id = v.order_id AND o.clinic_id = v.clinic_id
  LEFT JOIN public.clinic_room r
    ON r.id = coalesce(o.room_id, o.phong_du_kien_id) AND r.clinic_id = o.clinic_id
   AND r.location_id = $3::uuid AND r.is_active AND NOT r.la_doi_tac
 WHERE v.clinic_id = $1::uuid AND v.id = $2::uuid
"""

#: Dòng đi theo chỉ định đã làm mà chưa có dòng bán (chưa thu). Chỉ dòng `tru_kho`.
_DA_LAM_CHUA_DONG_SQL = f"""
SELECT v.id::text AS id, v.ten, v.don_vi, v.don_gia, v.so_luong,
       v.service_price_id::text AS vat_tu_id,
       coalesce($3::uuid, v.chon_boi, o.recorded_by)::text AS nguoi
  FROM public.luot_vat_tu v
  JOIN public.service_order o ON o.id = v.order_id AND o.clinic_id = v.clinic_id
 WHERE v.clinic_id = $1::uuid AND v.visit_id = $2::uuid AND v.bo_luc IS NULL
   AND v.tru_kho AND {_CON_SONG} AND {_DA_LAM}
   AND NOT EXISTS (SELECT 1 FROM public.vat_tu_ban b
                    WHERE b.clinic_id = v.clinic_id AND b.luot_vat_tu_id = v.id)
"""

_LICH_BAC_SI_SQL = """
SELECT vt.room_id::text AS phong, w.shift, w.status
  FROM public.work_roster w
  JOIN public.vi_tri_lam_viec vt
    ON vt.clinic_id = w.clinic_id AND vt.code = w.station
  JOIN public.clinic_room r
    ON r.id = vt.room_id AND r.clinic_id = w.clinic_id AND r.location_id = $4::uuid
   AND r.is_active AND NOT r.la_doi_tac
 WHERE w.clinic_id = $1::uuid AND w.staff_id = $2::uuid AND w.work_date = $3::date
   AND vt.room_id IS NOT NULL
 ORDER BY vt.sort NULLS LAST
"""


async def _phong_bac_si(
    conn: asyncpg.Connection, clinic_id: str, location_id: str, visit_id: str
) -> str | None:
    """Phòng bác sĩ khám của lượt. Lượt qua tay nhiều bác sĩ thì không biết ai đưa
    hàng → None."""
    if (
        await conn.fetchval(
            "SELECT count(DISTINCT doctor_staff_id) FROM public.consultation"
            " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
            "   AND status <> 'cancelled'",
            clinic_id,
            visit_id,
        )
        or 0
    ) > 1:
        return None
    bac_si = await bac_si_cua_phien(conn, clinic_id=clinic_id, visit_id=visit_id)
    if not bac_si:
        return None
    luot = await conn.fetchrow(
        "SELECT coalesce(v.checked_in_at, v.created_at) AS luc, c.settings"
        "  FROM public.visit v JOIN public.clinic c ON c.id = v.clinic_id"
        " WHERE v.clinic_id = $1::uuid AND v.visit_id = $2::uuid",
        clinic_id,
        visit_id,
    )
    if luot is None:
        return None
    luc = luot["luc"].astimezone(CLINIC_TZ)
    dong = await conn.fetch(
        _LICH_BAC_SI_SQL, clinic_id, bac_si, luc.date(), location_id
    )
    return phong_cua_bac_si(
        [(r["phong"], str(r["shift"]), str(r["status"])) for r in dong],
        luc.hour * 60 + luc.minute,
        ca_tu_settings(luot["settings"]),
    )


def _kem(b: dict[str, Any]) -> dict[str, Any]:
    return {
        "ban_id": b["id"],
        "clinic_patient_id": b["clinic_patient_id"],
        "payment_cycle_id": b["payment_cycle_id"],
    }


async def _luu(
    conn: asyncpg.Connection, ai: NguoiKho, b: dict[str, Any], *, ban_moi: bool = False
) -> None:
    """Ghi trạng thái dòng. `ban_moi`: lần thu mới (thu lại) nên ngày bán và người
    bán là của lần này."""
    await conn.execute(
        """
        UPDATE public.vat_tu_ban
           SET so_luong = $3, thanh_tien = $4, payment_cycle_id = $5::uuid,
               noi_lay = $6, room_id = $7::uuid, noi_nguon = $8, trang_thai = $9,
               ly_do = $10, phieu_id = $11::uuid, so_phieu = $12,
               gia_von = $15, so_hoan_tien = $16, so_tra = $17, so_khong_nhan = $18,
               ban_boi = CASE WHEN $14 THEN $13::uuid ELSE ban_boi END,
               ban_luc = CASE WHEN $14 THEN now() ELSE ban_luc END,
               sua_boi = $13::uuid, sua_luc = now()
         WHERE clinic_id = $1::uuid AND id = $2::uuid
        """,
        ai.clinic_id,
        b["id"],
        b["so_luong"],
        b["thanh_tien"],
        b["payment_cycle_id"],
        b["noi_lay"],
        b["room_id"],
        b["noi_nguon"],
        b["trang_thai"],
        b["ly_do"],
        b["phieu_id"],
        b["so_phieu"],
        ai.staff_id,
        ban_moi,
        b["gia_von"],
        b["so_hoan_tien"],
        b["so_tra"],
        b["so_khong_nhan"],
    )


async def _dao(
    conn: asyncpg.Connection, ai: NguoiKho, b: dict[str, Any], ly_do: str | None
) -> None:
    """Đảo phiếu BAN đang có hiệu lực — số về đúng nơi đã trừ."""
    await _khoa_co_so(conn, ai)
    b["so_phieu"] = int(b["so_phieu"]) + 1
    await _dao_phieu(
        conn,
        ai,
        b["phieu_id"],
        f"ban:{b['id']}:{b['so_phieu']}",
        ly_do or "Hoàn lại số đã trừ.",
        ban=_kem(b),
    )
    b["phieu_id"] = None
    b["trang_thai"] = DA_HOAN


async def _tru(
    conn: asyncpg.Connection,
    ai: NguoiKho,
    b: dict[str, Any],
    noi: Noi,
    ly_do: str | None,
) -> None:
    """Lập phiếu BAN `b["so_luong"]` tại nơi lấy. Không chặn tồn âm (Quang 17/10)."""
    await _khoa_co_so(conn, ai)
    b["so_phieu"] = int(b["so_phieu"]) + 1
    phieu = await _mo_phieu(
        conn,
        ai,
        "BAN",
        f"ban:{b['id']}:{b['so_phieu']}",
        ly_do or "Bán cho khách.",
        ban=_kem(b),
    )
    # Giá vốn: lần nhập gần nhất; chưa từng nhập ở cơ sở này thì giá danh mục.
    gia = await gia_nhap_gan_nhat(conn, ai, b["vat_tu_id"]) or await _gia_chua_khai(
        conn, ai, b["vat_tu_id"], "BAN"
    )
    ton = await _ton(conn, ai, b["vat_tu_id"], noi.room_id)
    await _ghi(conn, ai, phieu["id"], b["vat_tu_id"], ton, -b["so_luong"], gia)
    b.update(
        noi_lay=noi.lay,
        room_id=noi.room_id,
        noi_nguon=noi.nguon,
        trang_thai=DA_TRU,
        phieu_id=phieu["id"],
        ly_do=ly_do,
        gia_von=gia,
    )


def _vi_sao_het_ban(lv: Any) -> str | None:
    """Câu nói vì sao dòng thôi bán, đọc từ TRẠNG THÁI chứ không từ sự kiện vừa tới:
    bên nhận có thể xử lý sự kiện cũ khi chỉ định đã bị bỏ."""
    if lv is None:
        return None
    if lv["cancel_reason"]:
        return f"Bỏ chỉ định: {lv['cancel_reason']}"
    if lv["not_performed_reason"]:
        return f"Dịch vụ không làm: {lv['not_performed_reason']}"
    if lv["khach_bo"]:
        return "Khách không làm dịch vụ"
    return str(lv["bo_ly_do"]) if lv["bo_ly_do"] else None


def _noi_hien_tai(b: dict[str, Any]) -> Noi | None:
    return Noi(b["noi_lay"], b["room_id"], b["noi_nguon"]) if b["noi_lay"] else None


async def _dong_bo_mot(
    conn: asyncpg.Connection,
    nguoi: NguoiKho,
    b: dict[str, Any],
    ly_do: str | None,
) -> None:
    """Sửa MỘT dòng cho khớp sổ lần thu + trạng thái chỉ định. Không lệch thì không
    ghi gì."""
    ai = NguoiGhi(
        nguoi.clinic_id, b["location_id"], nguoi.staff_id or str(b["ban_boi"])
    )
    cid = ai.clinic_id
    lv = None
    if b["luot_vat_tu_id"]:
        lv = await conn.fetchrow(
            _LUOT_VAT_TU_SQL, cid, b["luot_vat_tu_id"], b["location_id"]
        )
    can = await conn.fetchrow(
        _SO_CAN_SQL,
        cid,
        "vat_tu" if b["luot_vat_tu_id"] else "prescription",
        b["luot_vat_tu_id"] or b["prescription_id"],
    )
    assert can is not None
    so_ban = Decimal(str(can["so"]))
    chi_da_lam = False
    if b["luot_vat_tu_id"]:
        if lv is None or not lv["con_ban"]:
            so_ban = Decimal(0)
            ly_do = _vi_sao_het_ban(lv) or ly_do
        elif so_ban <= 0 and lv["da_lam"] and lv["tru_kho"]:
            so_ban, chi_da_lam = Decimal(str(lv["so_luong"])), True
    tien = Decimal(str(can["tien"]))
    hoan = Decimal(str(can["hoan"]))
    so = so_ban - Decimal(str(b["so_tra"]))
    tien_doi = tien != b["thanh_tien"] or hoan != b["so_hoan_tien"]
    dang_tru = b["trang_thai"] == DA_TRU

    if so <= 0:
        if b["trang_thai"] == DA_HOAN and not tien_doi:
            return
        if dang_tru:
            await _dao(conn, ai, b, ly_do)
        b.update(
            trang_thai=DA_HOAN,
            thanh_tien=tien,
            so_hoan_tien=hoan,
            ly_do=ly_do or b["ly_do"],
        )
        if so_ban <= 0:
            b.update(so_tra=Decimal(0), so_khong_nhan=Decimal(0))
        await _luu(conn, ai, b)
        return

    hien_tai = _noi_hien_tai(b)
    phong_cd = lv["phong_chi_dinh"] if lv else None
    co_phong = bool(lv and lv["co_phong"])
    noi = chon_noi(
        hien_tai,
        phong_cd,
        None
        if co_phong or hien_tai
        else await _phong_bac_si(conn, cid, b["location_id"], str(b["visit_id"])),
    )
    ban_moi = bool(can["lan"]) and can["lan"] != b["payment_cycle_id"]
    khong_doi_so = so == b["so_luong"]
    if dang_tru and noi == hien_tai and khong_doi_so:
        if tien_doi or ban_moi or b["payment_cycle_id"] != can["lan"]:
            b.update(thanh_tien=tien, so_hoan_tien=hoan, payment_cycle_id=can["lan"])
            if ly_do:
                b["ly_do"] = f"{ly_do} — {LY_DO_DA_LAM}" if chi_da_lam else ly_do
            await _luu(conn, ai, b, ban_moi=ban_moi)
        return
    if (
        b["trang_thai"] == CHO_GAN_PHONG
        and noi is None
        and khong_doi_so
        and not tien_doi
        and not ban_moi
    ):
        return
    if dang_tru:
        await _dao(conn, ai, b, ly_do)
    b.update(
        so_luong=so, thanh_tien=tien, so_hoan_tien=hoan, payment_cycle_id=can["lan"]
    )
    if noi is None:
        b.update(
            trang_thai=CHO_GAN_PHONG,
            noi_lay=None,
            room_id=None,
            noi_nguon=None,
            phieu_id=None,
            ly_do=LY_DO_CHUA_RO_PHONG,
        )
    else:
        await _tru(conn, ai, b, noi, ly_do)
    await _luu(conn, ai, b, ban_moi=ban_moi)


async def _them_dong(
    conn: asyncpg.Connection,
    clinic_id: str,
    location_id: str,
    *,
    nguon: str,
    luot_vat_tu_id: str | None,
    prescription_id: str | None,
    visit_id: str,
    khach: str,
    vat_tu_id: str,
    ten: str,
    don_vi: str | None,
    so_luong: Any,
    don_gia: Any,
    thanh_tien: Any,
    lan_thu: str | None,
    ban_boi: str,
    bac_si: str | None,
) -> None:
    """Một nguồn một dòng — Postgres ép bằng unique index, gửi lại thì không làm gì."""
    await conn.execute(
        """
        INSERT INTO public.vat_tu_ban (
            clinic_id, location_id, nguon, luot_vat_tu_id, prescription_id,
            visit_id, clinic_patient_id, vat_tu_id, ten, don_vi, so_luong,
            don_gia, thanh_tien, payment_cycle_id, ban_boi, bac_si_id, trang_thai,
            ly_do)
        VALUES ($1::uuid, $2::uuid, $3, $4::uuid, $5::uuid, $6::uuid, $7::uuid,
                $8::uuid, $9, $10, $11, $12, $13, $14::uuid, $15::uuid, $16::uuid,
                'CHO_GAN_PHONG', $17)
        ON CONFLICT DO NOTHING
        """,
        clinic_id,
        location_id,
        nguon,
        luot_vat_tu_id,
        prescription_id,
        visit_id,
        khach,
        vat_tu_id,
        ten,
        don_vi,
        so_luong,
        don_gia,
        thanh_tien,
        lan_thu,
        ban_boi,
        bac_si,
        LY_DO_CHUA_RO_PHONG,
    )


async def _tao_dong_moi(
    conn: asyncpg.Connection, nguoi: NguoiKho, visit_id: str, lan_thu: str | None
) -> None:
    """Dòng bán cho nguồn vừa phát sinh: dòng hoá đơn của lần thu `lan_thu`, và dòng
    đi theo chỉ định đã làm mà chưa thu. Nguồn đã có dòng (thu lại sau hoàn tác) giữ
    nguyên dòng — nơi lấy cũ đi theo."""
    cid = nguoi.clinic_id
    nguon = await conn.fetch(_NGUON_LAN_THU_SQL, cid, lan_thu) if lan_thu else []
    da_lam = await conn.fetch(
        _DA_LAM_CHUA_DONG_SQL, cid, visit_id, nguoi.staff_id or None
    )
    if not nguon and not da_lam:
        return
    luot = await conn.fetchrow(
        "SELECT clinic_patient_id::text AS khach,"
        " public.co_so_cua_luot(clinic_id, visit_id)::text AS co_so"
        " FROM public.visit WHERE clinic_id = $1::uuid AND visit_id = $2::uuid",
        cid,
        visit_id,
    )
    assert luot is not None
    co_so = luot["co_so"] or nguoi.location_id
    bac_si = await bac_si_cua_phien(conn, clinic_id=cid, visit_id=visit_id)
    for r in nguon:
        la_quay = r["source_type"] == "vat_tu"
        await _them_dong(
            conn,
            cid,
            co_so,
            nguon=("CHI_DINH" if r["order_id"] else "QUAY_DICH_VU")
            if la_quay
            else "QUAY_THUOC",
            luot_vat_tu_id=r["source_id"] if la_quay else None,
            prescription_id=None if la_quay else r["source_id"],
            visit_id=visit_id,
            khach=luot["khach"],
            vat_tu_id=r["vat_tu_id"],
            ten=r["ten"],
            don_vi=r["don_vi"],
            so_luong=r["quantity"],
            don_gia=r["unit_price"],
            thanh_tien=r["line_total"] or 0,
            lan_thu=lan_thu,
            ban_boi=nguoi.staff_id,
            bac_si=bac_si,
        )
    for r in da_lam:
        if r["nguoi"]:
            await _them_dong(
                conn,
                cid,
                co_so,
                nguon="CHI_DINH",
                luot_vat_tu_id=r["id"],
                prescription_id=None,
                visit_id=visit_id,
                khach=luot["khach"],
                vat_tu_id=r["vat_tu_id"],
                ten=r["ten"],
                don_vi=r["don_vi"],
                so_luong=r["so_luong"],
                don_gia=r["don_gia"],
                thanh_tien=0,
                lan_thu=None,
                ban_boi=r["nguoi"],
                bac_si=bac_si,
            )


async def dong_bo_ban_vat_tu(
    conn: asyncpg.Connection,
    nguoi: NguoiKho,
    visit_id: str,
    *,
    lan_thu: str | None = None,
    ly_do: str | None = None,
) -> None:
    """MÓC DUY NHẤT: gọi sau mọi việc làm đổi tiền / chỉ định của lượt, trong giao
    dịch đang giữ khoá lượt. `lan_thu` = lần thu vừa tạo; `ly_do` = vì sao số đổi, ghi
    vào phiếu đảo. `nguoi.staff_id` rỗng (bên nhận sự kiện do hệ thống gây ra) thì sổ
    đứng tên người đã bán. KHÔNG hỏi quyền kho: người thu không có lego Kho vật tư
    vẫn bán được."""
    await _tao_dong_moi(conn, nguoi, visit_id, lan_thu)
    rows = await conn.fetch(
        _DONG_SQL.format(dieu_kien="b.visit_id = $2::uuid AND b.nguon <> 'NHAP_BU'"),
        nguoi.clinic_id,
        visit_id,
    )
    for r in rows:
        await _dong_bo_mot(conn, nguoi, dict(r), ly_do)


async def _nhan_lai(
    conn: asyncpg.Connection,
    nguoi: NguoiKho,
    b: dict[str, Any],
    so: Decimal,
    ly_do: str,
) -> None:
    """Hàng khách trả về đúng nơi đã lấy: phần còn lại lập phiếu mới."""
    if so > b["so_luong"] or b["trang_thai"] == DA_HOAN:
        raise ValidationError(
            f"“{b['ten']}” chỉ còn {b['so_luong'].normalize():f} đang trừ"
            " — không nhận lại quá số đó."
            if b["trang_thai"] != DA_HOAN
            else f"“{b['ten']}” đã hoàn lại kho — không nhận lại lần nữa."
        )
    b["so_tra"] = Decimal(str(b["so_tra"])) + so
    await _dong_bo_mot(conn, nguoi, b, f"Khách trả hàng: {ly_do}")


async def tra_hang_tai_quay(
    conn: asyncpg.Connection,
    nguoi: NguoiKho,
    payment_bill_line_id: str,
    so: Decimal,
    ly_do: str,
) -> bool:
    """Quầy hoàn tiền kèm "Khách trả lại hàng" — trong giao dịch hoàn tiền (đã khoá
    lượt). Dòng hoá đơn không có dòng bán vật tư → False, không làm gì."""
    r = await conn.fetchrow(
        _DONG_SQL.format(
            dieu_kien="""b.id = (
                SELECT x.id FROM public.vat_tu_ban x
                  JOIN public.payment_bill_line bl
                    ON bl.clinic_id = x.clinic_id AND bl.id = $2::uuid
                   AND ((bl.source_type = 'vat_tu'
                         AND x.luot_vat_tu_id::text = bl.source_id)
                        OR (bl.source_type = 'prescription'
                            AND x.prescription_id::text = bl.source_id))
                 WHERE x.clinic_id = $1::uuid)"""
        ),
        nguoi.clinic_id,
        payment_bill_line_id,
    )
    if r is None:
        return False
    await _nhan_lai(conn, nguoi, dict(r), so, ly_do)
    return True


async def dong_la_vat_tu(
    conn: asyncpg.Connection, clinic_id: str, cycle_ids: list[str]
) -> set[str]:
    """Dòng hoá đơn nào của các lần thu là vật tư còn đang bán — màn Hoàn tiền hỏi
    thêm "Khách trả lại hàng" cho đúng các dòng ấy."""
    if not cycle_ids:
        return set()
    rows = await conn.fetch(
        """
        SELECT bl.id::text AS id
          FROM public.payment_bill_line bl
          JOIN public.vat_tu_ban b
            ON b.clinic_id = bl.clinic_id AND b.trang_thai <> 'DA_HOAN'
           AND ((bl.source_type = 'vat_tu' AND b.luot_vat_tu_id::text = bl.source_id)
                OR (bl.source_type = 'prescription'
                    AND b.prescription_id::text = bl.source_id))
         WHERE bl.clinic_id = $1::uuid AND bl.payment_cycle_id = ANY($2::uuid[])
        """,
        clinic_id,
        cycle_ids,
    )
    return {r["id"] for r in rows}


# ── Thao tác của người kho ─────────────────────────────────────────────────
async def _doc_dong_khoa(
    conn: asyncpg.Connection, identity: StaffIdentity, ban_id: str
) -> dict[str, Any]:
    """Khoá lượt → khoá dòng (cùng thứ tự với lần thu). Chỉ dòng cơ sở đang làm."""
    goc = await conn.fetchrow(
        "SELECT visit_id::text AS visit_id FROM public.vat_tu_ban"
        " WHERE clinic_id = $1::uuid AND location_id = $2::uuid AND id = $3::uuid",
        identity.clinic_id,
        identity.location_id,
        ban_id,
    )
    if goc is None:
        raise NotFoundError("Không tìm thấy dòng bán vật tư của cơ sở.")
    if goc["visit_id"]:
        await conn.execute(
            "SELECT 1 FROM public.visit WHERE clinic_id = $1::uuid"
            " AND visit_id = $2::uuid FOR UPDATE",
            identity.clinic_id,
            goc["visit_id"],
        )
    r = await conn.fetchrow(
        _DONG_SQL.format(dieu_kien="b.id = $2::uuid"), identity.clinic_id, ban_id
    )
    assert r is not None
    return dict(r)


async def _vet(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    event_type: str,
    ban_id: str,
    payload: dict[str, Any],
) -> None:
    await record_event(
        conn,
        event_type=event_type,
        aggregate_type="vat_tu_ban",
        aggregate_id=ban_id,
        identity=identity,
        origin="api:vat-tu-kho",
        payload=payload,
    )


async def gan_noi_lay(
    pool: asyncpg.Pool,
    *,
    identity: StaffIdentity,
    ban_id: Any,
    room_id: Any,
    ly_do: Any,
) -> dict[str, Any]:
    """Người kho gán / đổi nơi lấy (`room_id` rỗng = Kho cơ sở), kèm lý do: trừ NGAY
    ở nơi đó; đổi = đảo chỗ cũ + trừ chỗ mới. Gửi lại cùng nơi thì không ghi sổ."""
    bid = _uuid(ban_id)
    room = _uuid(room_id) if room_id else None
    ly = _ly_do(ly_do)
    noi = Noi("PHONG" if room else "KHO", room, "KHO")
    async with pool.acquire() as conn, conn.transaction():
        b = await _doc_dong_khoa(conn, identity, bid)
        if b["trang_thai"] == DA_HOAN:
            raise ConflictError(
                "Dòng này đã hoàn lại kho — không còn gì để gán nơi lấy."
            )
        ai = NguoiGhi(identity.clinic_id, identity.location_id, identity.staff_id)
        hien_tai = _noi_hien_tai(b)
        if (
            b["trang_thai"] == DA_TRU
            and hien_tai is not None
            and (hien_tai.lay, hien_tai.room_id) == (noi.lay, noi.room_id)
        ):
            if hien_tai.nguon == "KHO":
                return {"ok": True, "gui_lai": True, "id": bid}
            b.update(noi_nguon="KHO", ly_do=ly)
            await _luu(conn, ai, b)
        else:
            if b["trang_thai"] == DA_TRU:
                await _dao(conn, ai, b, f"Đổi nơi lấy: {ly}")
            await _tru(conn, ai, b, noi, ly)
            await _luu(conn, ai, b)
        await _vet(
            conn,
            identity,
            "vat_tu.ban_gan_noi_lay",
            bid,
            {"room_id": room, "noi_lay": noi.lay, "ly_do": ly},
        )
        return {"ok": True, "gui_lai": False, "id": bid}


async def nhan_lai_hang(
    pool: asyncpg.Pool,
    *,
    identity: StaffIdentity,
    ban_id: Any,
    so_luong: Any,
    ly_do: Any,
) -> dict[str, Any]:
    """Người kho nhận lại hàng khách trả: số về đúng nơi đã lấy. Tiền là việc của
    quầy (Hoàn tiền), lệnh này không đụng. Gửi lại do Idempotency-Key ở router."""
    bid = _uuid(ban_id)
    so = _so(so_luong)
    ly = _ly_do(ly_do)
    async with pool.acquire() as conn, conn.transaction():
        b = await _doc_dong_khoa(conn, identity, bid)
        if b["nguon"] == NHAP_BU:
            raise ConflictError("Dòng nhập bù dùng nút Hoàn tác, không nhận lại hàng.")
        await _nhan_lai(conn, identity, b, so, ly)
        await _vet(
            conn,
            identity,
            "vat_tu.ban_nhan_lai",
            bid,
            {"so_luong": str(so), "ly_do": ly},
        )
        return {"ok": True, "id": bid}


async def khong_nhan_lai(
    pool: asyncpg.Pool, *, identity: StaffIdentity, ban_id: Any, ly_do: Any
) -> dict[str, Any]:
    """Đã hoàn tiền nhưng hàng không về (đã dùng, hỏng): đóng phần chờ xử lý, tồn
    giữ nguyên, lý do hiện ở danh sách. Gửi lại = không đổi gì."""
    bid = _uuid(ban_id)
    ly = _ly_do(ly_do)
    async with pool.acquire() as conn, conn.transaction():
        b = await _doc_dong_khoa(conn, identity, bid)
        con = so_cho_xu_ly(
            b["trang_thai"], b["so_hoan_tien"], b["so_tra"], b["so_khong_nhan"]
        )
        if con <= 0:
            return {"ok": True, "gui_lai": True, "id": bid}
        b["so_khong_nhan"] = Decimal(str(b["so_khong_nhan"])) + con
        b["ly_do"] = f"Không nhận lại hàng: {ly}"
        ai = NguoiGhi(identity.clinic_id, identity.location_id, identity.staff_id)
        await _luu(conn, ai, b)
        await _vet(
            conn,
            identity,
            "vat_tu.ban_khong_nhan_lai",
            bid,
            {"so_luong": str(con), "ly_do": ly},
        )
        return {"ok": True, "gui_lai": False, "id": bid}


async def nhap_bu(
    pool: asyncpg.Pool,
    *,
    identity: StaffIdentity,
    khoa_gui: str | None,
    clinic_patient_id: Any,
    vat_tu_id: Any,
    so_luong: Any,
    room_id: Any,
    ly_do: Any,
) -> dict[str, Any]:
    """Dòng quầy quên ghi (Tuyền chốt A): CHỈ trừ kho, không phát sinh tiền. Gửi lại
    cùng khoá = cùng dòng. `room_id` rỗng = Kho cơ sở."""
    khoa = _khoa(khoa_gui)
    khach, vt = _uuid(clinic_patient_id), _uuid(vat_tu_id)
    room = _uuid(room_id) if room_id else None
    so = _so(so_luong)
    ly = _ly_do(ly_do)
    noi = Noi("PHONG" if room else "KHO", room, "KHO")
    cid = identity.clinic_id
    async with pool.acquire() as conn, conn.transaction():
        await _khoa_co_so(conn, identity)
        cu = await conn.fetchval(
            "SELECT id::text FROM public.vat_tu_ban WHERE clinic_id = $1::uuid"
            " AND location_id = $2::uuid AND khoa_gui = $3",
            cid,
            identity.location_id,
            khoa,
        )
        if cu:
            return {"ok": True, "gui_lai": True, "id": cu}
        if not await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM public.patient WHERE clinic_id = $1::uuid"
            " AND clinic_patient_id = $2::uuid)",
            cid,
            khach,
        ):
            raise NotFoundError("Không tìm thấy khách này.")
        hang = await conn.fetchrow(
            "SELECT name, don_vi FROM public.service_price WHERE clinic_id = $1::uuid"
            " AND id = $2::uuid AND \"group\" = 'vat_tu'",
            cid,
            vt,
        )
        if hang is None:
            raise NotFoundError("Không tìm thấy vật tư của phòng khám.")
        bid = str(
            await conn.fetchval(
                """
                INSERT INTO public.vat_tu_ban (
                    clinic_id, location_id, nguon, khoa_gui, clinic_patient_id,
                    vat_tu_id, ten, don_vi, so_luong, ban_boi, trang_thai, ly_do)
                VALUES ($1::uuid, $2::uuid, 'NHAP_BU', $3, $4::uuid, $5::uuid, $6, $7,
                        $8, $9::uuid, 'CHO_GAN_PHONG', $10)
                RETURNING id
                """,
                cid,
                identity.location_id,
                khoa,
                khach,
                vt,
                hang["name"],
                hang["don_vi"],
                so,
                identity.staff_id,
                ly,
            )
        )
        r = await conn.fetchrow(_DONG_SQL.format(dieu_kien="b.id = $2::uuid"), cid, bid)
        assert r is not None
        b = dict(r)
        ai = NguoiGhi(cid, identity.location_id, identity.staff_id)
        await _tru(conn, ai, b, noi, ly)
        await _luu(conn, ai, b)
        await _vet(
            conn,
            identity,
            "vat_tu.ban_nhap_bu",
            bid,
            {"so_luong": str(so), "noi_lay": noi.lay, "room_id": room, "ly_do": ly},
        )
        return {"ok": True, "gui_lai": False, "id": bid}


async def hoan_tac_nhap_bu(
    pool: asyncpg.Pool, *, identity: StaffIdentity, ban_id: Any, ly_do: Any
) -> dict[str, Any]:
    """Hoàn tác dòng nhập bù: số về đúng nơi đã trừ. Gửi lại = như cũ. Dòng có tiền
    thì không qua đây — hoàn tác lần thu ở quầy."""
    bid = _uuid(ban_id)
    ly = _ly_do(ly_do)
    async with pool.acquire() as conn, conn.transaction():
        b = await _doc_dong_khoa(conn, identity, bid)
        if b["nguon"] != NHAP_BU:
            raise ConflictError(
                "Dòng này có tiền — hoàn tác lần thu ở quầy, số sẽ tự về kho."
            )
        if b["trang_thai"] == DA_HOAN:
            return {"ok": True, "gui_lai": True, "id": bid}
        ai = NguoiGhi(identity.clinic_id, identity.location_id, identity.staff_id)
        await _dao(conn, ai, b, f"Hoàn tác nhập bù: {ly}")
        b["ly_do"] = ly
        await _luu(conn, ai, b)
        await _vet(conn, identity, "vat_tu.ban_hoan_tac_nhap_bu", bid, {"ly_do": ly})
        return {"ok": True, "gui_lai": False, "id": bid}


# ── Đọc ────────────────────────────────────────────────────────────────────
_DANH_SACH_SQL = """
SELECT b.id::text AS id, b.nguon, b.ban_luc, b.ten, b.don_vi, b.so_luong, b.don_gia,
       b.thanh_tien, b.gia_von, b.so_hoan_tien, b.so_tra, b.so_khong_nhan,
       b.noi_lay, b.room_id::text AS room_id, b.noi_nguon,
       b.trang_thai, b.ly_do, b.vat_tu_id::text AS vat_tu_id,
       b.payment_cycle_id IS NULL AS chua_thu,
       p.full_name AS khach, p.patient_code AS ma_khach,
       nb.full_name AS nguoi_ban, bs.full_name AS bac_si, r.name AS phong,
       m.ma_phieu
  FROM public.vat_tu_ban b
  LEFT JOIN public.patient p
    ON p.clinic_patient_id = b.clinic_patient_id AND p.clinic_id = b.clinic_id
  LEFT JOIN public.staff nb ON nb.id = b.ban_boi
  LEFT JOIN public.staff bs ON bs.id = b.bac_si_id
  LEFT JOIN public.clinic_room r ON r.id = b.room_id AND r.clinic_id = b.clinic_id
  LEFT JOIN public.vat_tu_phieu m ON m.id = b.phieu_id AND m.clinic_id = b.clinic_id
 WHERE b.clinic_id = $1::uuid AND b.location_id = $2::uuid
   AND b.ban_luc >= $3 AND b.ban_luc < $4
   AND ($5::text IS NULL OR b.trang_thai = $5)
   AND ($6::uuid IS NULL OR b.room_id = $6::uuid)
   AND (NOT $7 OR b.noi_lay = 'KHO')
 ORDER BY b.ban_luc DESC, b.id
 LIMIT $8
"""

_CAN_XU_LY_SQL = """
SELECT count(*) FILTER (WHERE trang_thai = 'CHO_GAN_PHONG') AS cho_gan,
       count(*) FILTER (WHERE trang_thai = 'DA_TRU'
                          AND so_hoan_tien > so_tra + so_khong_nhan) AS cho_xu_ly
  FROM public.vat_tu_ban
 WHERE clinic_id = $1::uuid AND location_id = $2::uuid
   AND (trang_thai = 'CHO_GAN_PHONG' OR so_hoan_tien > 0)
"""


def _ra_dong(r: asyncpg.Record) -> dict[str, Any]:
    trang_thai = r["trang_thai"]
    la_nhap_bu = r["nguon"] == NHAP_BU
    con_xu_ly = so_cho_xu_ly(
        trang_thai, r["so_hoan_tien"], r["so_tra"], r["so_khong_nhan"]
    )
    return {
        **dict(r),
        "chua_thu": bool(r["chua_thu"]) and not la_nhap_bu,
        "nguon_ten": _TEN_NGUON.get(r["nguon"], r["nguon"]),
        "trang_thai_ten": _TEN_TRANG_THAI.get(trang_thai, trang_thai),
        "noi_lay_ten": "Kho cơ sở"
        if r["noi_lay"] == "KHO"
        else (r["phong"] or "Chưa rõ"),
        "so_cho_xu_ly": con_xu_ly,
        # Nút do máy chủ quyết, TSX chỉ vẽ.
        "gan_duoc": trang_thai != DA_HOAN,
        "hoan_tac_duoc": la_nhap_bu and trang_thai != DA_HOAN,
        "nhan_lai_duoc": not la_nhap_bu and trang_thai == DA_TRU,
        "khong_nhan_duoc": con_xu_ly > 0,
    }


async def doc_ban(
    pool: asyncpg.Pool,
    *,
    identity: StaffIdentity,
    tu: Any = None,
    den: Any = None,
    noi: Any = None,
    trang_thai: Any = None,
) -> dict[str, Any]:
    """Danh sách đối soát theo ngày bán. `noi`: mã phòng hoặc "kho"; rác = không lọc."""
    a, b = khoang_xnt(tu, den, hom_nay_vn())
    tt = trang_thai if trang_thai in _TEN_TRANG_THAI else None
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            _DANH_SACH_SQL,
            identity.clinic_id,
            identity.location_id,
            dau_ngay_vn(a),
            dau_ngay_vn(b + timedelta(days=1)),
            tt,
            _ma_hoac_rong(noi) if noi != "kho" else None,
            noi == "kho",
            TRAN_DANH_SACH,
        )
        dem = await conn.fetchrow(
            _CAN_XU_LY_SQL, identity.clinic_id, identity.location_id
        )
    assert dem is not None
    return {
        "tu": a.isoformat(),
        "den": b.isoformat(),
        "items": [_ra_dong(r) for r in rows],
        "cho_gan": int(dem["cho_gan"]),
        "cho_xu_ly": int(dem["cho_xu_ly"]),
        "bi_cat": canh_bao_neu_day(
            "kho_vat_tu.ban_cho_khach",
            len(rows),
            TRAN_DANH_SACH,
            clinic_id=identity.clinic_id,
        ),
    }


async def tim_khach(
    pool: asyncpg.Pool, *, identity: StaffIdentity, q: Any
) -> dict[str, Any]:
    """Tìm khách để nhập bù — cùng câu tìm với bán lẻ, cửa quyền Kho vật tư."""
    # Import trong hàm: ban_le → … → hoan_tien → file này thành vòng.
    from clinicai.services.ban_le_service import tim_khach_conn

    async with pool.acquire() as conn:
        return {"items": await tim_khach_conn(conn, identity.clinic_id, q)}


__all__ = [
    "CHO_GAN_PHONG",
    "DA_HOAN",
    "DA_TRU",
    "NguoiGhi",
    "Noi",
    "chon_noi",
    "doc_ban",
    "dong_bo_ban_vat_tu",
    "dong_la_vat_tu",
    "gan_noi_lay",
    "hoan_tac_nhap_bu",
    "khong_nhan_lai",
    "nhan_lai_hang",
    "nhap_bu",
    "phong_cua_bac_si",
    "so_cho_xu_ly",
    "tim_khach",
    "tra_hang_tai_quay",
]
