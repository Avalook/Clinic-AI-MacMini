"""Số thu ngân XÁC NHẬN khi bấm "Đã nhận tiền" (G4d · R1, Tuyền chốt C 14/10):
phần chuyển khoản của lần thu — đúng số màn điền sẵn. Bài kiểm cũ gửi số này
để giữ nguyên ý nghĩa (khớp → không bật cờ đối soát)."""

from __future__ import annotations

import asyncpg

from clinicai.services.phan_thu import doc_phan_db, so_tien_chuyen_khoan


async def so_ck(pool: asyncpg.Pool, payment_cycle_id: object) -> int:
    r = await pool.fetchrow(
        "SELECT method, amount,"
        " phan_thu_hieu_luc(clinic_id, payment_cycle_id, method, amount) AS phan"
        " FROM payment_cycle WHERE payment_cycle_id = $1::uuid",
        str(payment_cycle_id),
    )
    assert r is not None, "không thấy lần thu"
    return so_tien_chuyen_khoan(doc_phan_db(r["phan"]), r["method"], int(r["amount"]))
