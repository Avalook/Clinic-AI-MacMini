"""Chuông NHẬN CHÉO — phòng A quên Xong (Tuyền chốt 07/10/2026).

Dây ``nhan_tai_phong`` bật, khách đang LÀM ở phòng A mà phòng B bấm Nhận (nhận
chéo): lần làm ở A GIỮ mở — hệ thống không đoán thay A. Bên nghe này réo chuông
cho A tự đóng:

    service.room_released (NHAN_CHEO, trước đó 'lam')
        → chuông đích danh: người bấm Bắt đầu lần làm ấy + nhân sự trực phòng A
          hôm nay (không trùng). Bấm mở đúng phòng A, đúng chỉ định.
    service.completed / service.interrupted / service.start_cancelled
        → lần làm ấy đã Xong / Gián đoạn / huỷ Bắt đầu: chuông của nó tự đóng.

A chỉ đang CHỜ (chưa Bắt đầu) thì không réo — khách rời hàng là đủ. Giao tin
lặp không nhân đôi (khoá "một việc đang mở một lần" của `thong_bao`); lần làm
đã đóng trước khi tin tới thì thôi. Phát lại thì im. Không sửa nơi phát.
"""

from __future__ import annotations

import asyncpg

from clinicai.core.clock import CLINIC_TZ, hom_nay_vn
from clinicai.events.catalogue import CHUONG_NHAN_CHEO
from clinicai.events.consumers.chuong import ghi_chuong_nguoi
from clinicai.events.worker import SuKienDaNhan, dang_ky

# Lịch trực hôm nay (mọi người, mọi phòng) — cùng nguồn cửa ca trực dùng.
from clinicai.permissions.ca_truc import _lich_hom_nay

NGUON = "nhan_cheo"
LY_DO_NHAN_CHEO = "NHAN_CHEO"

#: Sự kiện đóng lần làm → chuông tự đóng, kèm ghi chú.
_DONG: dict[str, str] = {
    "service.completed": "Phòng đã bấm Xong",
    "service.interrupted": "Phòng đã bấm Gián đoạn",
    "service.start_cancelled": "Phòng đã huỷ Bắt đầu",
}


def nguon_id(attempt_id: str) -> str:
    return f"{NGUON}:{attempt_id}"


def nguoi_nhan(nguoi_bat_dau: str | None, truc_phong: list[str]) -> list[str]:
    """Thuần: người bấm Bắt đầu trước, rồi người trực phòng — không trùng."""
    dau = [nguoi_bat_dau] if nguoi_bat_dau else []
    return list(dict.fromkeys([*dau, *truc_phong]))


def cau_chuong(
    *, khach: str, phong_moi: str, luc: str, dich_vu: str, phong_cu: str
) -> str:
    return (
        f"Khách {khach} đã sang {phong_moi} lúc {luc} — bấm Xong hoặc Gián đoạn"
        f" cho {dich_vu} ở {phong_cu}"
    )


async def _reo(conn: asyncpg.Connection, su_kien: SuKienDaNhan) -> None:
    p = su_kien.payload
    if (
        su_kien.la_phat_lai
        or p.get("ly_do") != LY_DO_NHAN_CHEO
        or p.get("trang_thai_truoc") != "lam"
        or not p.get("attempt_id")
        # `thong_bao.nguoi_goi_staff_id` bắt buộc — người bấm Nhận ở phòng B.
        or not su_kien.actor_staff_id
    ):
        return
    cid = su_kien.clinic_id
    r = await conn.fetchrow(
        """
        SELECT t.started_by::text AS bat_dau, o.service_name,
               p.full_name, p.patient_code, a.name AS phong_cu, b.name AS phong_moi
          FROM service_execution_attempt t
          JOIN service_order o
            ON o.clinic_id = t.clinic_id AND o.id = t.service_order_id
          JOIN visit v ON v.clinic_id = o.clinic_id AND v.visit_id = o.visit_id
          JOIN patient p
            ON p.clinic_id = v.clinic_id AND p.clinic_patient_id = v.clinic_patient_id
          LEFT JOIN clinic_room a ON a.clinic_id = t.clinic_id AND a.id = $3::uuid
          LEFT JOIN clinic_room b ON b.clinic_id = t.clinic_id AND b.id = $4::uuid
         WHERE t.clinic_id = $1::uuid AND t.id = $2::uuid
           AND t.status = 'IN_PROGRESS'
        """,
        cid,
        str(p["attempt_id"]),
        str(p["room_id"]),
        p.get("sang_room_id"),
    )
    if r is None:
        # Lần làm đã đóng trước khi tin tới — không còn gì để nhắc.
        return
    truc = [
        c.staff_id
        for c in await _lich_hom_nay(conn, cid, hom_nay_vn())
        if c.room_id == str(p["room_id"])
    ]
    luc = su_kien.occurred_at.astimezone(CLINIC_TZ).strftime("%H:%M")
    phong_cu = r["phong_cu"] or "phòng cũ"
    tieu_de = cau_chuong(
        khach=f"{r['full_name']} ({r['patient_code']})",
        phong_moi=r["phong_moi"] or "phòng khác",
        luc=luc,
        dich_vu=r["service_name"],
        phong_cu=phong_cu,
    )
    for ai in nguoi_nhan(r["bat_dau"], truc):
        await ghi_chuong_nguoi(
            conn,
            clinic_id=cid,
            nguoi_nhan=ai,
            tieu_de=tieu_de,
            noi_dung=(
                f"Lần làm ở {phong_cu} vẫn mở — hệ thống không tự đóng thay phòng."
            ),
            nguon=NGUON,
            nguon_id=nguon_id(str(p["attempt_id"])),
            duong_dan=f"/phong/{p['room_id']}?chi_dinh={p['service_order_id']}",
            nguoi_goi=su_kien.actor_staff_id,
        )


async def _dong(conn: asyncpg.Connection, su_kien: SuKienDaNhan) -> None:
    lan = su_kien.payload.get("attempt_id")
    if not lan:
        return
    await conn.execute(
        """
        UPDATE thong_bao
           SET da_xu_ly_luc = now(),
               da_xu_ly_boi = coalesce($3::uuid, nguoi_goi_staff_id),
               ghi_chu_xu_ly = $4,
               da_doc_luc = coalesce(da_doc_luc, now())
         WHERE clinic_id = $1::uuid AND nguon = $5 AND nguon_id = $2
           AND da_xu_ly_luc IS NULL
        """,
        su_kien.clinic_id,
        nguon_id(str(lan)),
        su_kien.actor_staff_id,
        _DONG[su_kien.event_type],
        NGUON,
    )


async def chuong_nhan_cheo(conn: asyncpg.Connection, su_kien: SuKienDaNhan) -> None:
    if su_kien.event_type == "service.room_released":
        await _reo(conn, su_kien)
    elif su_kien.event_type in _DONG:
        await _dong(conn, su_kien)


dang_ky(CHUONG_NHAN_CHEO, chuong_nhan_cheo)

__all__ = ["NGUON", "cau_chuong", "chuong_nhan_cheo", "nguoi_nhan", "nguon_id"]
