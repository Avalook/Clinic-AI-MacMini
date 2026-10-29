"""MỌI dịch vụ đang bán: chỉ định → mở đúng mẫu máy chọn → Hoàn tất → xong (29/10/2026).

Tuyền: "test full toàn bộ các chỉ định các loại form… xem có loại nào lỗi". Bài
này đi hết danh mục (không chọn mẫu tay): mỗi dịch vụ một chỉ định đã thu, chưa
ai bắt đầu (đúng ca HPV 28/10), mở phiếu theo `mau_cho_dich_vu`, Hoàn tất ở bàn
khám → dịch vụ COMPLETED; dịch vụ thu hộ (EXTERNAL_PARTNER, không làm ngoài) thì
việc đối tác sinh ra sau `service.completed`. Gom lỗi theo dịch vụ, đỏ một lần
với danh sách đủ — không dừng ở dịch vụ đầu tiên hỏng.
"""

from __future__ import annotations

import uuid

import asyncpg
import pytest

from clinicai.events.catalogue import DOI_TAC_NHAN_VIEC
from clinicai.phieu_kham.mau_dieu_tri import MAU_KHONG_HOAN_TAT
from clinicai.phieu_kham.mau_goi_y import mau_cho_dich_vu
from clinicai.services.form_engine_service import FormEngineService
from tests.chay_nguoi_dua_tin import chay_het
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_dieu_tri_ban_kham_db import _lich_ban_kham
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    _benh_nhan,
    _check_in,
    _dung,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _chi_dinh_da_thu(
    conn: asyncpg.Connection,
    *,
    visit: str,
    con: str,
    bac_si: str,
    code: str,
    ten: str,
    node: str,
) -> str:
    oid = await conn.fetchval(
        "INSERT INTO service_order (clinic_id, visit_id, consultation_id,"
        " service_code, service_name, node_code, exec_status, recorded_by,"
        " authorized_by, authorized_at, selection_status, routing_status,"
        " routing_revision, execution_status)"
        " VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6, 'authorized',"
        " $7::uuid, $7::uuid, now(), 'SELECTED', 'UNASSIGNED', 0, 'PENDING')"
        " RETURNING id::text",
        CLINIC,
        visit,
        con,
        code,
        ten,
        node,
        bac_si,
    )
    cycle = str(uuid.uuid4())
    await conn.execute(
        "INSERT INTO payment_cycle (payment_cycle_id, clinic_id, visit_id, kind,"
        " amount, bill_revision, method, status, legacy, created_by, paid_at,"
        " confirmed_by) VALUES ($1::uuid, $2::uuid, $3::uuid, 'dich_vu', 100000,"
        " $5, 'CASH', 'PAID', false, $4::uuid, now(), $4::uuid)",
        cycle,
        CLINIC,
        visit,
        bac_si,
        f"rev-{cycle[:8]}",
    )
    await conn.execute(
        "INSERT INTO payment_bill_line (clinic_id, payment_cycle_id, visit_id,"
        " kind, source_type, source_id, name_snapshot, quantity, unit_price,"
        " line_total, billing_owner) VALUES ($1::uuid, $2::uuid, $3::uuid,"
        " 'dich_vu', 'service_order', $4, $5, 1, 100000, 100000, 'CLINIC')",
        CLINIC,
        cycle,
        visit,
        oid,
        ten,
    )
    return str(oid)


async def test_moi_dich_vu_dang_ban_hoan_tat_o_ban_kham_la_xong(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    await _lich_ban_kham(pool, ca)
    dich_vu = await pool.fetch(
        "SELECT service_code, name, node_code, billing_owner"
        "  FROM service_price"
        " WHERE clinic_id = $1::uuid AND active AND \"group\" = 'dich_vu'"
        "   AND node_code IS NOT NULL ORDER BY service_code",
        CLINIC,
    )
    assert len(dich_vu) > 30, "danh mục test phải có đủ dịch vụ (migration 01/10)"
    fe = FormEngineService(pool)
    loi: list[str] = []
    da_thu_ho = 0
    for dv in dich_vu:
        code, ten = dv["service_code"], dv["name"]
        try:
            visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
            con = str(
                await pool.fetchval(
                    "SELECT id::text FROM consultation WHERE visit_id = $1::uuid"
                    " AND kind = 'PRIMARY'",
                    visit,
                )
            )
            async with pool.acquire() as conn:
                oid = await _chi_dinh_da_thu(
                    conn,
                    visit=visit,
                    con=con,
                    bac_si=ca.bac_si.staff_id,
                    code=code,
                    ten=ten,
                    node=dv["node_code"],
                )
                _mau, chon = await mau_cho_dich_vu(
                    conn, clinic_id=CLINIC, service_code=code
                )
            if not chon:
                loi.append(f"{code} {ten}: không có mẫu chọn sẵn")
                continue
            ph = await fe.mo_phieu(
                service_order_id=oid, form_id=f"KQ_{chon}", identity=ca.bac_si
            )
            kq = await fe.hoan_tat(
                phieu_id=ph["id"],
                expected_revision=int(ph["revision"]),
                identity=ca.bac_si,
            )
            trang_thai = await pool.fetchval(
                "SELECT execution_status FROM service_order WHERE id = $1::uuid", oid
            )
            if trang_thai != "COMPLETED":
                loi.append(
                    f"{code} {ten} (KQ_{chon}): sau Hoàn tất là {trang_thai},"
                    f" dịch vụ={kq.get('dich_vu')}"
                )
                continue
            if f"KQ_{chon}" not in MAU_KHONG_HOAN_TAT and not kq.get("da_hoan_tat"):
                loi.append(f"{code} {ten} (KQ_{chon}): phiếu không chốt")
            if dv["billing_owner"] == "EXTERNAL_PARTNER":
                await chay_het(pool, DOI_TAC_NHAN_VIEC)
                if not await pool.fetchval(
                    "SELECT EXISTS (SELECT 1 FROM doi_tac_nhan_viec"
                    " WHERE service_order_id = $1::uuid)",
                    oid,
                ):
                    loi.append(f"{code} {ten}: thu hộ mà không sinh việc đối tác")
                else:
                    da_thu_ho += 1
        except Exception as e:  # noqa: BLE001 — gom đủ danh sách rồi mới đỏ
            loi.append(f"{code} {ten}: {type(e).__name__}: {str(e)[:160]}")
    print(f"\n{len(dich_vu)} dịch vụ, {da_thu_ho} thu hộ đã lên bàn đối tác")
    assert not loi, f"{len(loi)}/{len(dich_vu)} dịch vụ lỗi:\n" + "\n".join(loi)
