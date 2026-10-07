"""Ô chữ tự do của hồ sơ lượt "Khác" + dữ liệu bản in gộp một lượt (Tuyền chốt
07/10/2026 tối), trên Postgres thật.

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55600/postgres \\
        poetry run pytest src/tests/services/test_ghi_chu_luot_db.py

Lưu hai lần → hai phiên bản (không đè); màn cầm bản cũ → 409; gửi lại y hệt
không đẻ bản; ô chỉ hiện ở lượt Khác. Bản in gộp đọc được đủ ba loại lượt: lượt
Điều trị (không phiếu khám), lượt khám thường có chỉ định điều trị, lượt Khác.
"""

from __future__ import annotations

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError
from clinicai.events.catalogue import DIEU_TRI_SINH_CHI_DINH
from clinicai.phieu_kham.ket_qua_chi_dinh import doc_ket_qua_theo_chi_dinh
from clinicai.services import ghi_chu_luot
from clinicai.services.chi_dinh_service import ChiDinhService
from clinicai.services.form_engine_service import FormEngineService
from clinicai.services.luot_kham_service import LuotKhamService
from tests.chay_nguoi_dua_tin import chay_het
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    _benh_nhan,
    _check_in,
    _dung,
    _khoa,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _loai(pool: asyncpg.Pool, code: str) -> str:  # noqa: F811
    v = await pool.fetchval(
        "SELECT id::text FROM service_type WHERE clinic_id = $1::uuid AND code = $2"
        " ORDER BY created_at LIMIT 1",
        CLINIC,
        code,
    )
    assert v, f"migration 20261007600000 phải có loại {code}"
    return str(v)


async def test_ghi_chu_khac_moi_lan_luu_mot_phien_ban_khong_de(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(
        pool, ca, await _benh_nhan(pool, ca), await _loai(pool, "KHAC")
    )
    dau = await ghi_chu_luot.doc(pool, identity=ca.bac_si, visit_id=visit)
    assert dau["hien"] is True and dau["ghi_duoc"] is True and dau["ban"] is None

    b1 = await ghi_chu_luot.luu(
        pool, identity=ca.bac_si, visit_id=visit, noi_dung="Khách hỏi về", phien_ban=0
    )
    b2 = await ghi_chu_luot.luu(
        pool,
        identity=ca.dd,
        visit_id=visit,
        noi_dung="Khách hỏi về liệu trình Laser",
        phien_ban=b1["ban"]["phien_ban"],
    )
    assert (b1["ban"]["phien_ban"], b2["ban"]["phien_ban"]) == (1, 2)
    # Hai dòng — bản cũ còn nguyên, không UPDATE.
    rows = await pool.fetch(
        "SELECT phien_ban, noi_dung FROM luot_ghi_chu WHERE visit_id = $1::uuid"
        " ORDER BY phien_ban",
        visit,
    )
    assert [(r["phien_ban"], r["noi_dung"]) for r in rows] == [
        (1, "Khách hỏi về"),
        (2, "Khách hỏi về liệu trình Laser"),
    ]
    # Màn cầm bản cũ → 409, không đè.
    with pytest.raises(ConflictError):
        await ghi_chu_luot.luu(
            pool, identity=ca.bac_si, visit_id=visit, noi_dung="đè", phien_ban=1
        )
    # Gửi lại y hệt → không đẻ phiên bản.
    lai = await ghi_chu_luot.luu(
        pool,
        identity=ca.bac_si,
        visit_id=visit,
        noi_dung="Khách hỏi về liệu trình Laser",
        phien_ban=2,
    )
    assert lai["doi"] is False and lai["ban"]["phien_ban"] == 2
    # Bảng chỉ thêm: sửa / xoá bị chặn ở Postgres.
    with pytest.raises(asyncpg.PostgresError):
        await pool.execute(
            "UPDATE luot_ghi_chu SET noi_dung = 'x' WHERE visit_id = $1::uuid", visit
        )
    doc = await ghi_chu_luot.doc(pool, identity=ca.bac_si, visit_id=visit)
    assert doc["ban"]["noi_dung"] == "Khách hỏi về liệu trình Laser"
    assert doc["ban"]["ghi_boi"]


async def test_o_ghi_chu_chi_hien_o_luot_khac(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    assert (await ghi_chu_luot.doc(pool, identity=ca.bac_si, visit_id=visit))[
        "hien"
    ] is False


def test_rac_khong_nem() -> None:
    assert ghi_chu_luot.doc_noi_dung(None) == ""
    assert ghi_chu_luot.doc_noi_dung(123) == ""
    assert ghi_chu_luot.hien_o_ghi_chu("KHAM", True) is True
    assert ghi_chu_luot.hien_o_ghi_chu("KHAM", False) is False


async def test_ban_in_gop_doc_du_ba_loai_luot(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Nguồn của `/print/phieu-kham/{visit}` cho ba loại lượt — không còn lượt
    nào "chưa có gì để in" khi lượt có phiếu điều trị / ghi chú."""
    ca = await _dung(pool)
    fe = FormEngineService(pool)
    laser_loai = await _loai(pool, "DT_LASER_TIEN_DINH")
    ma_laser = await pool.fetchval(
        "SELECT sp.service_code FROM service_type st JOIN service_price sp"
        " ON sp.id = st.service_price_id WHERE st.id = $1::uuid",
        laser_loai,
    )

    async def ghi_phieu(order: str, chu: str) -> None:
        ph = await fe.mo_phieu(
            service_order_id=order, form_id="KQ_PHIEU_DIEU_TRI", identity=ca.bac_si
        )
        await fe.luu_nhap(
            phieu_id=ph["id"],
            du_lieu={"cam_nhan": {"gia_tri": chu, "nguon": "USER"}},
            expected_revision=int(ph["revision"]),
            identity=ca.bac_si,
        )

    async def dieu_tri_co_chu(visit: str, chu: str) -> None:
        async with pool.acquire() as conn:
            ds = await doc_ket_qua_theo_chi_dinh(conn, clinic_id=CLINIC, visit_id=visit)
        dt = [c for c in ds if c["dieu_tri"]]
        assert dt, "phải có chỉ định điều trị để in mục Điều trị"
        assert any(
            (k.get("du_lieu") or {}).get("cam_nhan", {}).get("gia_tri") == chu
            for c in dt
            for k in c["ket_qua"]
        )

    # (1) Lượt ĐIỀU TRỊ — không phiếu khám.
    v1 = await _check_in(pool, ca, await _benh_nhan(pool, ca), laser_loai)
    await chay_het(pool, DIEU_TRI_SINH_CHI_DINH)
    o1 = await pool.fetchval(
        "SELECT id::text FROM service_order WHERE visit_id = $1::uuid", v1
    )
    await ghi_phieu(str(o1), "Đỡ khô")
    assert not await pool.fetchval(
        "SELECT EXISTS (SELECT 1 FROM phieu_kham_luot WHERE visit_id = $1::uuid)", v1
    )
    await dieu_tri_co_chu(v1, "Đỡ khô")

    # (2) Lượt khám thường có chỉ định điều trị (bác sĩ kê Laser).
    v2 = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    con = await pool.fetchval(
        "SELECT id::text FROM consultation WHERE visit_id = $1::uuid"
        " AND kind = 'PRIMARY'",
        v2,
    )
    await LuotKhamService(pool).start_consultation(
        consultation_id=str(con), identity=ca.bac_si
    )
    kq = await ChiDinhService(pool).dat_chi_dinh(
        consultation_id=str(con),
        service_codes=[str(ma_laser)],
        identity=ca.bac_si,
        idempotency_key=_khoa(),
    )
    await ghi_phieu(kq["order_ids"][0], "Hơi rát")
    await dieu_tri_co_chu(v2, "Hơi rát")

    # (3) Lượt KHÁC — ghi chú tự do.
    v3 = await _check_in(
        pool, ca, await _benh_nhan(pool, ca), await _loai(pool, "KHAC")
    )
    await ghi_chu_luot.luu(
        pool, identity=ca.bac_si, visit_id=v3, noi_dung="Tư vấn chung", phien_ban=0
    )
    # Khâu in (lễ tân) đọc được ghi chú cho bản in.
    assert (await ghi_chu_luot.doc(pool, identity=ca.le_tan, visit_id=v3))["ban"][
        "noi_dung"
    ] == "Tư vấn chung"
