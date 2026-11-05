"""Sổ thu hộ xét nghiệm đối tác (kế hoạch 4.4, câu chốt 1 + 6, ADR-0015).

Tiền khách trả cho đối tác, phòng khám THU HỘ. Chỉ ghi `doi_tac_thanh_toan` (+
`doi_tac_hoan_tien`) — KHÔNG BAO GIỜ payment_cycle / payment / payment_bill_line /
két / doanh thu. Giá chỉ là gợi ý: lưu cả `gia_goi_y` và số thật, không bắt khớp.

* **Ghi nhận** — TM + CK (tách được), mã GD, 0đ vẫn là ghi nhận. Một việc một ghi
  nhận còn hiệu lực: Postgres ép (unique có điều kiện); người thua nhận 409 tiếng
  Việt, KHÔNG nhờ khoá dòng (5b: trước đây chỉ nhờ `FOR UPDATE OF o`).
* **Huỷ** = ghi sai (lý do). **Hoàn** = trả tiền thật (dòng mới, lý do). Hai lệnh.
* `ghi_dong` / `huy_dong` là LÕI dùng chung: lệnh cũ của bàn đối tác
  (`doi_tac_service.ghi_nhan_da_thu` / `huy_da_thu`) gọi lại lõi này (luật 2).
"""

from __future__ import annotations

from typing import Any

import asyncpg

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.core.tran import canh_bao_neu_day
from clinicai.events.catalogue import XetNghiemThuHo
from clinicai.events.emit import emit_event, nguoi
from clinicai.services.tai_khoan_nhan_service import doc_id
from clinicai.services.xet_nghiem.o_nhap import doc_ly_do, doc_tien

CAU_DA_CO = "Việc này đã có ghi nhận thu hộ (người khác vừa ghi?) — tải lại màn."


def hinh_thuc_cua(tien_mat: int, chuyen_khoan: int) -> str:
    """Hình thức SUY RA từ hai số (CHECK ở DB cùng luật). 0đ ⇒ CASH."""
    if tien_mat > 0 and chuyen_khoan > 0:
        return "MIXED"
    return "TRANSFER" if chuyen_khoan > 0 else "CASH"


def doc_hai_so(tien_mat: object, chuyen_khoan: object) -> tuple[int, int]:
    """Ô TM / CK: trống ⇒ 0; cả hai trống ⇒ 422 (0đ thì gõ 0). Rác ⇒ 422."""
    tm = doc_tien(tien_mat, "Tiền mặt")
    ck = doc_tien(chuyen_khoan, "Chuyển khoản")
    if tm is None and ck is None:
        raise ValidationError("Nhập số tiền khách trả (miễn phí thì gõ 0).")
    return tm or 0, ck or 0


def _ma_gd(raw: object) -> str | None:
    s = " ".join(raw.split()) if isinstance(raw, str) else ""
    if len(s) > 100:
        raise ValidationError("Mã giao dịch tối đa 100 ký tự.")
    return s or None


async def ghi_dong(
    conn: asyncpg.Connection,
    *,
    clinic_id: str,
    order_id: str,
    tien_mat: int,
    chuyen_khoan: int,
    staff_id: str,
    gia_goi_y: int | None = None,
    ma_giao_dich: str | None = None,
    ghi_chu: str | None = None,
) -> str:
    """LÕI: một dòng sổ. Trùng ghi nhận còn hiệu lực ⇒ 409 (ép ở DB)."""
    try:
        v = await conn.fetchval(
            """
            INSERT INTO public.doi_tac_thanh_toan
                (clinic_id, service_order_id, so_tien, tien_mat, chuyen_khoan,
                 hinh_thuc, gia_goi_y, ma_giao_dich, ghi_chu, ghi_boi)
            VALUES ($1::uuid, $2::uuid, $3::numeric + $4::numeric, $3, $4, $5, $6,
                    $7, $8, $9::uuid)
            RETURNING id::text
            """,
            clinic_id,
            order_id,
            tien_mat,
            chuyen_khoan,
            hinh_thuc_cua(tien_mat, chuyen_khoan),
            gia_goi_y,
            ma_giao_dich,
            ghi_chu,
            staff_id,
        )
    except asyncpg.UniqueViolationError:
        raise ConflictError(CAU_DA_CO) from None
    return str(v)


async def huy_dong(
    conn: asyncpg.Connection,
    *,
    clinic_id: str,
    thanh_toan_id: str,
    staff_id: str,
    ly_do: str,
) -> None:
    """LÕI: đóng một ghi nhận (ghi sai). Đã hoàn tiền ⇒ không huỷ được."""
    if await conn.fetchval(
        "SELECT EXISTS (SELECT 1 FROM public.doi_tac_hoan_tien"
        " WHERE clinic_id = $1::uuid AND thanh_toan_id = $2::uuid)",
        clinic_id,
        thanh_toan_id,
    ):
        raise ConflictError(
            "Khoản này đã hoàn tiền một phần/toàn bộ — không huỷ được (huỷ là ghi sai)."
        )
    await conn.execute(
        "UPDATE public.doi_tac_thanh_toan SET huy_luc = now(), huy_boi = $3::uuid,"
        " ly_do_huy = $4 WHERE clinic_id = $1::uuid AND id = $2::uuid"
        " AND huy_luc IS NULL",
        clinic_id,
        thanh_toan_id,
        staff_id,
        ly_do,
    )


# ── Lệnh của bàn XN (luồng mới: việc có `xet_nghiem_viec`) ─────────────────
async def _viec(conn: asyncpg.Connection, cid: str, raw_id: object) -> asyncpg.Record:
    oid = doc_id(raw_id, cau="Việc không hợp lệ.")
    v = await conn.fetchrow(
        """
        SELECT o.id::text AS order_id, o.visit_id::text AS visit_id,
               o.exec_status, x.gia_goi_y_luc_chi_dinh AS gia_goi_y
          FROM public.xet_nghiem_viec x
          JOIN public.service_order o
            ON o.clinic_id = x.clinic_id AND o.id = x.service_order_id
         WHERE x.clinic_id = $1::uuid AND x.service_order_id = $2::uuid
        """,
        cid,
        oid,
    )
    if v is None:
        raise NotFoundError("Không tìm thấy việc xét nghiệm đối tác này.")
    return v


async def _dong_con_hieu_luc(
    conn: asyncpg.Connection, cid: str, oid: str
) -> asyncpg.Record | None:
    return await conn.fetchrow(
        """
        SELECT t.id::text, t.so_tien, t.tien_mat, t.chuyen_khoan,
               coalesce((SELECT sum(h.so_tien) FROM public.doi_tac_hoan_tien h
                          WHERE h.clinic_id = t.clinic_id AND h.thanh_toan_id = t.id),
                        0) AS da_hoan
          FROM public.doi_tac_thanh_toan t
         WHERE t.clinic_id = $1::uuid AND t.service_order_id = $2::uuid
           AND t.huy_luc IS NULL
           FOR UPDATE OF t
        """,
        cid,
        oid,
    )


def _su_kien(
    identity: StaffIdentity, v: asyncpg.Record, tm: int, ck: int
) -> dict[str, Any]:
    """Phần chung của ba sự kiện sổ thu hộ. Tên sự kiện viết TẠI lời gọi
    `emit_event(ten="lab.…")` — test "dây chết" đọc đúng chỗ đó."""
    return {
        "clinic_id": identity.clinic_id,
        "aggregate_id": v["order_id"],
        "so_ke_tiep": True,
        "payload": XetNghiemThuHo(
            visit_id=v["visit_id"],
            service_order_id=v["order_id"],
            so_tien=tm + ck,
            tien_mat=tm,
            chuyen_khoan=ck,
        ),
        "boi": nguoi(identity),
        "correlation_id": v["visit_id"],
    }


async def ghi_nhan(
    conn: asyncpg.Connection, identity: StaffIdentity, data: dict[str, Any]
) -> str:
    """Ghi nhận khách đã trả (số thật, kể cả lệch giá gợi ý / 0đ / CK chưa thấy)."""
    tm, ck = doc_hai_so(data.get("tien_mat"), data.get("chuyen_khoan"))
    ghi = " ".join(str(data.get("ghi_chu") or "").split())[:2000] or None
    v = await _viec(conn, identity.clinic_id, data.get("order_id"))
    if v["exec_status"] == "cancelled":
        raise ConflictError("Chỉ định đã huỷ — không ghi nhận thu được.")
    tt_id = await ghi_dong(
        conn,
        clinic_id=identity.clinic_id,
        order_id=v["order_id"],
        tien_mat=tm,
        chuyen_khoan=ck,
        staff_id=identity.staff_id,
        gia_goi_y=int(v["gia_goi_y"]) if v["gia_goi_y"] is not None else None,
        ma_giao_dich=_ma_gd(data.get("ma_giao_dich")),
        ghi_chu=ghi,
    )
    await emit_event(conn, ten="lab.payment_recorded", **_su_kien(identity, v, tm, ck))
    return tt_id


async def huy(
    conn: asyncpg.Connection, identity: StaffIdentity, data: dict[str, Any]
) -> None:
    """Huỷ ghi nhận (ghi sai) — bắt lý do. Không xoá dòng."""
    ly = doc_ly_do(data.get("ly_do"))
    v = await _viec(conn, identity.clinic_id, data.get("order_id"))
    dong = await _dong_con_hieu_luc(conn, identity.clinic_id, v["order_id"])
    if dong is None:
        raise ConflictError("Việc này không còn ghi nhận thu nào — tải lại màn.")
    await huy_dong(
        conn,
        clinic_id=identity.clinic_id,
        thanh_toan_id=dong["id"],
        staff_id=identity.staff_id,
        ly_do=ly,
    )
    tm, ck = int(dong["tien_mat"]), int(dong["chuyen_khoan"])
    await emit_event(conn, ten="lab.payment_voided", **_su_kien(identity, v, tm, ck))


async def hoan(
    conn: asyncpg.Connection, identity: StaffIdentity, data: dict[str, Any]
) -> str:
    """Hoàn tiền thật cho khách (bỏ chỉ định sau khi đã thu…). Tổng hoàn ≤ đã thu —
    kiểm dưới khoá dòng thu (FOR UPDATE), hai người hoàn cùng lúc chờ nhau."""
    ly = doc_ly_do(data.get("ly_do"))
    tm, ck = doc_hai_so(data.get("tien_mat"), data.get("chuyen_khoan"))
    if tm + ck <= 0:
        raise ValidationError("Số tiền hoàn phải lớn hơn 0.")
    v = await _viec(conn, identity.clinic_id, data.get("order_id"))
    dong = await _dong_con_hieu_luc(conn, identity.clinic_id, v["order_id"])
    if dong is None:
        raise ConflictError("Việc này chưa có ghi nhận thu — không có gì để hoàn.")
    con = int(dong["so_tien"]) - int(dong["da_hoan"])
    if tm + ck > con:
        raise ConflictError(f"Chỉ còn {con:,}đ có thể hoàn.".replace(",", "."))
    h = await conn.fetchval(
        """
        INSERT INTO public.doi_tac_hoan_tien
            (clinic_id, thanh_toan_id, so_tien, tien_mat, chuyen_khoan, ly_do,
             hoan_boi)
        VALUES ($1::uuid, $2::uuid, $3::numeric + $4::numeric, $3, $4, $5, $6::uuid)
        RETURNING id::text
        """,
        identity.clinic_id,
        dong["id"],
        tm,
        ck,
        ly,
        identity.staff_id,
    )
    await emit_event(conn, ten="lab.payment_refunded", **_su_kien(identity, v, tm, ck))
    return str(h)


#: Sổ thu hộ theo NGÀY GHI NHẬN / NGÀY HOÀN (giờ VN) — báo cáo cuối ngày + tab Tiền
#: thu hộ đọc chung câu này (SQL có nhà, luật 6). Dòng hoàn: số ÂM, `loai='HOAN'`.
#: $1 clinic · $2,$3 ngày từ–đến · $4 cơ sở (NULL = mọi) · $5,$6 mốc giờ (NULL = cả
#: ngày).
SO_THEO_NGAY_SQL = """
WITH dong AS (
    SELECT t.id, 'THU' AS loai, t.service_order_id, t.so_tien, t.tien_mat,
           t.chuyen_khoan, t.hinh_thuc, t.ma_giao_dich, t.gia_goi_y,
           t.ghi_luc AS luc, t.ghi_boi AS boi
      FROM doi_tac_thanh_toan t
     WHERE t.clinic_id = $1::uuid AND t.huy_luc IS NULL
    UNION ALL
    SELECT h.id, 'HOAN', t.service_order_id, -h.so_tien, -h.tien_mat,
           -h.chuyen_khoan, 'HOAN', NULL, NULL, h.hoan_luc, h.hoan_boi
      FROM doi_tac_hoan_tien h
      JOIN doi_tac_thanh_toan t ON t.id = h.thanh_toan_id AND t.clinic_id = h.clinic_id
     WHERE h.clinic_id = $1::uuid
)
SELECT d.id::text AS id, d.loai, d.so_tien, d.tien_mat, d.chuyen_khoan, d.hinh_thuc,
       d.ma_giao_dich, d.gia_goi_y, d.luc AS ghi_luc, o.service_name AS ten,
       o.id::text AS service_order_id, s.full_name AS nguoi,
       p.full_name AS ten_khach, p.patient_code AS ma_bn,
       coalesce(v.location_id, ah.location_id)::text AS co_so
  FROM dong d
  LEFT JOIN service_order o ON o.id = d.service_order_id AND o.clinic_id = $1::uuid
  LEFT JOIN visit v ON v.visit_id = o.visit_id AND v.clinic_id = o.clinic_id
  LEFT JOIN appointment ah ON ah.id = v.appointment_id AND ah.clinic_id = v.clinic_id
  LEFT JOIN patient p
    ON p.clinic_patient_id = v.clinic_patient_id AND p.clinic_id = v.clinic_id
  LEFT JOIN staff s ON s.id = d.boi
 WHERE (d.luc AT TIME ZONE 'Asia/Ho_Chi_Minh')::date BETWEEN $2 AND $3
   AND ($5::timestamptz IS NULL OR d.luc >= $5)
   AND ($6::timestamptz IS NULL OR d.luc < $6)
   AND ($4::uuid IS NULL OR coalesce(v.location_id, ah.location_id) = $4::uuid)
 ORDER BY d.luc
 LIMIT 5000
"""
TRAN_SO_THEO_NGAY = 5000


async def doc_so_theo_ngay(
    conn: asyncpg.Connection, cid: str, *tham_so: object
) -> list[asyncpg.Record]:
    """Đọc sổ theo ngày (tham số như `SO_THEO_NGAY_SQL` sau clinic). Chạm trần 5.000
    dòng thì kêu ở log (không cắt im lặng)."""
    rows = list(await conn.fetch(SO_THEO_NGAY_SQL, cid, *tham_so))
    canh_bao_neu_day("doi_tac_thanh_toan", len(rows), TRAN_SO_THEO_NGAY, clinic_id=cid)
    return rows
