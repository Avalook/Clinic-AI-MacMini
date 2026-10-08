"""Chuông "Sắp hết lộ trình" cho CSKH (Tuyền 08/10/2026).

    service.completed (một buổi của liệu trình vừa làm xong)
        → liệu trình chạm ngưỡng ``ly_do_sap_het`` (còn ≤ 1 buổi, hoặc đã dùng
          hết buổi trả trước mà còn buổi chưa trả)
          → MỘT chuông cho vai CSKH (người có lego Chăm sóc khách hàng).

Bên nghe MỚI — không sửa nơi phát (``execution``). Một mốc một chuông: mốc =
(liệu trình, đã làm, số buổi, đã trả) làm ``nguon_id``; đã từng báo mốc này (kể
cả chuông đã đóng) hoặc CSKH đã [Đã xử lý] mốc này thì im. Phát lại thì im.
Chuông KHÔNG sinh dòng ở phòng / hàng chờ / Hành trình / TV.
"""

from __future__ import annotations

import asyncpg

from clinicai.events.catalogue import LIEU_TRINH_SAP_HET
from clinicai.events.consumers.chuong import ghi_chuong_vai
from clinicai.events.worker import SuKienDaNhan, dang_ky
from clinicai.services.lieu_trinh_service import LieuTrinhService, moc_sap_het

NGUON = "lieu_trinh_sap_het"


async def bao_sap_het(conn: asyncpg.Connection, su_kien: SuKienDaNhan) -> None:
    if su_kien.la_phat_lai or not su_kien.actor_staff_id:
        return
    oid = su_kien.payload.get("service_order_id")
    if not oid:
        return
    cid = su_kien.clinic_id
    lt_id = await conn.fetchval(
        "SELECT lieu_trinh_id::text FROM lieu_trinh_buoi"
        " WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid"
        "   AND go_luc IS NULL",
        cid,
        str(oid),
    )
    if lt_id is None:
        return
    ds = await LieuTrinhService.doc_nhieu(
        conn, cid, "lt.id = $2::uuid", lt_id, kem_buoi=False
    )
    if not ds or not ds[0]["sap_het_ly_do"]:
        return
    lt = ds[0]
    moc = moc_sap_het(lt)
    da_co = await conn.fetchval(
        """
        SELECT EXISTS (SELECT 1 FROM thong_bao
                        WHERE clinic_id = $1::uuid AND nguon = $2 AND nguon_id = $3)
            OR EXISTS (SELECT 1 FROM tuong_tac_cskh
                        WHERE clinic_id = $1::uuid AND huy_luc IS NULL
                          AND trang_thai_ma = $3)
        """,
        cid,
        NGUON,
        moc,
    )
    if da_co:
        return
    ly_do = str(lt["sap_het_ly_do"])
    await ghi_chuong_vai(
        conn,
        clinic_id=cid,
        vai="CSKH",
        tieu_de=f"Sắp hết lộ trình {lt['service_name']} — {lt['ten_khach']}"
        f" ({lt['ma_khach']})",
        noi_dung=f"{ly_do[:1].upper()}{ly_do[1:]}. Gọi tư vấn thêm buổi hoặc đặt"
        " lịch buổi kế.",
        nguon=NGUON,
        nguon_id=moc,
        duong_dan="/nhac-tai-kham?tab=lieu-trinh",
        nguoi_goi=su_kien.actor_staff_id,
    )


dang_ky(LIEU_TRINH_SAP_HET, bao_sap_het)

__all__ = ["NGUON", "bao_sap_het"]
