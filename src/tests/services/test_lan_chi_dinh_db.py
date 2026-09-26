"""Lần chỉ định (26/09/2026 — lát 4 bản giao diện mẫu).

Mỗi lần bấm chốt chỉ định = MỘT lần, kể cả khi cùng một vòng khám (trước đó
lần suy từ vòng khám nên "chỉ định thêm" trong cùng phiên vẫn hiện Lần 1).
Dịch vụ đã chỉ định ở lần trước chỉ định lại được — là một dòng mới, lần mới.
"""

from __future__ import annotations

import asyncio

import asyncpg
import pytest

from clinicai.phieu_kham.ket_qua_chi_dinh import doc_ket_qua_theo_chi_dinh
from clinicai.services.chi_dinh_service import ChiDinhService
from tests.chay_nguoi_dua_tin import chay_hanh_trinh
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    _benh_nhan,
    _check_in,
    _dung,
    _kham_va_chi_dinh,
    _khoa,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _lan(pool: asyncpg.Pool, visit: str) -> dict[str, int | None]:  # noqa: F811
    async with pool.acquire() as conn:
        ds = await doc_ket_qua_theo_chi_dinh(conn, clinic_id=CLINIC, visit_id=visit)
    return {d["service_order_id"]: d["lan"] for d in ds}


async def test_chi_dinh_lai_cung_dich_vu_cung_phien_la_lan_moi(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    await chay_hanh_trinh(pool)
    con, don_1 = await _kham_va_chi_dinh(pool, ca, visit)
    kq = await ChiDinhService(pool).dat_chi_dinh(
        consultation_id=con,
        service_codes=[ca.ma_dv],
        identity=ca.bac_si,
        idempotency_key=_khoa(),
    )
    don_2 = str(kq["order_ids"][0])
    assert don_2 != don_1, "chỉ định lại là một dòng MỚI, không gộp vào dòng cũ"
    lan = await _lan(pool, visit)
    assert lan[don_1] == 1
    assert lan[don_2] == 2, "cùng vòng khám nhưng bấm lần hai → lần 2"


async def test_mot_lan_bam_nhieu_dich_vu_chung_mot_lan(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    await chay_hanh_trinh(pool)
    con, _ = await _kham_va_chi_dinh(pool, ca, visit)
    ma_khac = await pool.fetchval(
        "SELECT service_code FROM service_price WHERE clinic_id = $1::uuid"
        " AND active AND service_code <> $2 AND node_code IS NOT NULL LIMIT 1",
        CLINIC,
        ca.ma_dv,
    )
    assert ma_khac, "cần thêm một dịch vụ có phòng làm trong seed"
    kq = await ChiDinhService(pool).dat_chi_dinh(
        consultation_id=con,
        service_codes=[ca.ma_dv, ma_khac],
        identity=ca.bac_si,
        idempotency_key=_khoa(),
    )
    lan = await _lan(pool, visit)
    assert {lan[str(i)] for i in kq["order_ids"]} == {2}


async def test_hai_nguoi_bam_cung_luc_khong_trung_lan(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    await chay_hanh_trinh(pool)
    con, _ = await _kham_va_chi_dinh(pool, ca, visit)
    svc = ChiDinhService(pool)
    a, b = await asyncio.gather(
        *(
            svc.dat_chi_dinh(
                consultation_id=con,
                service_codes=[ca.ma_dv],
                identity=ca.bac_si,
                idempotency_key=_khoa(),
            )
            for _ in range(2)
        )
    )
    lan = await _lan(pool, visit)
    assert {lan[str(a["order_ids"][0])], lan[str(b["order_ids"][0])]} == {2, 3}


async def test_trigger_nhap_nhan_so_luc_duyet_mang_sang_khong_so(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Luật ở trigger — mọi đường tạo chỉ định (kể cả đường nháp cũ) đi qua."""
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    await chay_hanh_trinh(pool)
    con, _ = await _kham_va_chi_dinh(pool, ca, visit)
    moi = (
        "INSERT INTO service_order (clinic_id, visit_id, consultation_id,"
        " service_code, service_name, node_code, exec_status, mang_tu_visit_id,"
        " recorded_by, authorized_by, authorized_at)"
        " SELECT $1::uuid, $2::uuid, $3::uuid, $4, 'x', o.node_code, $5, $6::uuid,"
        "        o.recorded_by, o.authorized_by, o.authorized_at"
        "   FROM service_order o WHERE o.visit_id = $2::uuid LIMIT 1"
        " RETURNING id::text"
    )
    nhap = await pool.fetchval(
        moi.replace("o.authorized_by, o.authorized_at", "NULL, NULL"),
        CLINIC,
        visit,
        con,
        ca.ma_dv,
        "draft",
        None,
    )
    assert (
        await pool.fetchval(
            "SELECT lan_chi_dinh FROM service_order WHERE id = $1::uuid", nhap
        )
        is None
    ), "nháp chưa duyệt chưa có lần"
    mang = await pool.fetchval(moi, CLINIC, visit, con, ca.ma_dv, "authorized", visit)
    await pool.execute(
        "UPDATE service_order SET exec_status = 'authorized',"
        " authorized_by = recorded_by, authorized_at = now() WHERE id = $1::uuid",
        nhap,
    )
    so = {
        r["id"]: r["lan_chi_dinh"]
        for r in await pool.fetch(
            "SELECT id::text, lan_chi_dinh FROM service_order"
            " WHERE id = ANY($1::uuid[])",
            [nhap, mang],
        )
    }
    assert so[nhap] == 2, "nháp nhận số lúc được duyệt"
    assert so[mang] is None, "mang sang từ lượt trước không thuộc lần nào"


async def test_chi_dinh_lam_o_doi_tac_mang_trang_thai_ban_doi_tac(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Lát 4c: phiếu khám thấy việc ở đối tác tới đâu — cùng hàm với bàn đối tác."""
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    await chay_hanh_trinh(pool)
    _con, don = await _kham_va_chi_dinh(pool, ca, visit)

    async def doi_tac() -> str | None:
        async with pool.acquire() as conn:
            ds = await doc_ket_qua_theo_chi_dinh(conn, clinic_id=CLINIC, visit_id=visit)
        [d] = [d for d in ds if d["service_order_id"] == don]
        return d["doi_tac"]

    assert await doi_tac() is None, "làm tại phòng khám: không có trạng thái đối tác"
    ngoai = await pool.fetchval(
        "SELECT code FROM node_definition WHERE clinic_id = $1::uuid"
        " AND lam_ben_ngoai LIMIT 1",
        CLINIC,
    )
    assert ngoai, "seed cần một phòng làm bên ngoài"
    await pool.execute(
        "UPDATE service_order SET node_code = $2 WHERE id = $1::uuid", don, ngoai
    )
    assert await doi_tac() == "CHO_LAY_MAU"
    await pool.execute(
        "UPDATE service_order SET doi_tac_cho_tai_lieu_luc = now() WHERE id = $1::uuid",
        don,
    )
    assert await doi_tac() == "CHO_TAI_LIEU"
    await pool.execute(
        "UPDATE service_order SET ket_qua_luc = now() WHERE id = $1::uuid", don
    )
    assert await doi_tac() == "DA_GUI_KET_QUA"
