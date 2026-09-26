"""Màn Mẫu kết quả (27/09/2026): bảng gắn, tạo mẫu, sửa + xuất bản an toàn.

Mọi phép xuất bản chạy trên mẫu TỰ TẠO trong test — không đụng 19 mẫu thật mà
test khác (mẫu v3, in kết quả) đang dựa vào.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator

import asyncpg
import pytest
import pytest_asyncio

from clinicai.api.exceptions import ConflictError
from clinicai.core.exceptions import SafetyGateError, ValidationError
from clinicai.services.form_engine_service import FormEngineService
from clinicai.services.mau_ket_qua_service import MauKetQuaService
from tests.services.test_form_engine_db import (  # noqa: F401
    CLINIC,
    _don_tron,
    _nguoi,
    pool,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest_asyncio.fixture(autouse=True)
async def _don_mau_da_tao(pool: asyncpg.Pool) -> AsyncIterator[None]:  # noqa: F811
    """Test khác đếm số mẫu ĐANG BẬT (18 + CHUNG) — mẫu tạo trong test này phải
    tắt đi sau khi xong. Tắt chứ không xoá: phiếu thử đã tham chiếu khung."""
    tu = await pool.fetchval("SELECT clock_timestamp()")
    yield
    await pool.execute(
        "UPDATE ket_qua_mau SET active = false"
        " WHERE clinic_id = $1::uuid AND created_at >= $2",
        CLINIC,
        tu,
    )


def _ten() -> str:
    return f"Mẫu thử {uuid.uuid4().hex[:6]}"


async def test_tao_mau_trong_co_ket_luan_va_mo_phieu_duoc(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    async with pool.acquire() as conn:
        ql = await _nguoi(conn, "MANAGEMENT")
        bs = await _nguoi(conn, "DOCTOR")
        order = await _don_tron(conn, bs)
    moi = await MauKetQuaService(pool).tao_mau(ten=_ten(), nhom="Siêu âm", identity=ql)
    assert moi["form_id"] == f"KQ_{moi['ma']}" and moi["version"] == 1
    p = await FormEngineService(pool).mo_phieu(
        service_order_id=order, form_id=moi["form_id"], identity=bs
    )
    assert [m["ma"] for m in p["khung"]] == ["ket_luan"]


async def test_tao_mau_chep_khung_va_trung_ten_khong_trung_ma(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    async with pool.acquire() as conn:
        ql = await _nguoi(conn, "MANAGEMENT")
    svc = MauKetQuaService(pool)
    ten = _ten()
    a = await svc.tao_mau(ten=ten, nhom="XN", chep_tu="KQ_SA_VU", identity=ql)
    b = await svc.tao_mau(ten=ten, nhom="XN", identity=ql)
    assert a["ma"] != b["ma"]
    goc = await pool.fetchval(
        "SELECT khung FROM form_definition WHERE clinic_id = $1::uuid"
        " AND form_id = 'KQ_SA_VU' AND trang_thai = 'PUBLISHED'",
        CLINIC,
    )
    chep = await pool.fetchval(
        "SELECT khung FROM form_definition WHERE clinic_id = $1::uuid"
        " AND form_id = $2 AND trang_thai = 'PUBLISHED'",
        CLINIC,
        a["form_id"],
    )
    assert goc == chep
    with pytest.raises(ValidationError):
        await svc.tao_mau(ten=_ten(), nhom="XN", chep_tu="KQ_KHONG_CO", identity=ql)


async def test_sua_xuat_ban_doi_ten_va_ban_cu_giu_nguyen(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    async with pool.acquire() as conn:
        ql = await _nguoi(conn, "MANAGEMENT")
    moi = await MauKetQuaService(pool).tao_mau(ten=_ten(), nhom="XN", identity=ql)
    eng = FormEngineService(pool)
    doc = await eng.doc_bieu_mau(form_id=moi["form_id"], identity=ql)
    assert doc["version"] == 1 and doc["so_phieu_da_dien"] == 0
    khung = doc["khung"] + [
        {
            "ma": "hpv",
            "ten": "HPV",
            "block": [
                {
                    "ma": "hpv_16",
                    "ten": "HPV 16",
                    "kieu": "chon",
                    "chon": ["Âm", "Dương"],
                }
            ],
        }
    ]
    kq = await eng.xuat_ban(
        form_id=moi["form_id"],
        khung=khung,
        expected_version=1,
        ten="Tên mới đổi",
        identity=ql,
    )
    assert kq["version"] == 2
    ten_dm = await pool.fetchval(
        "SELECT ten FROM ket_qua_mau WHERE clinic_id = $1::uuid AND ma = $2",
        CLINIC,
        moi["ma"],
    )
    assert ten_dm == "Tên mới đổi"
    cu = await pool.fetchval(
        "SELECT trang_thai FROM form_definition WHERE clinic_id = $1::uuid"
        " AND form_id = $2 AND version = 1",
        CLINIC,
        moi["form_id"],
    )
    assert cu == "RETIRED"
    # Sửa trên bản đã cũ (1) trong khi bản đang dùng là 2 → 409, không đè.
    with pytest.raises(ConflictError):
        await eng.xuat_ban(
            form_id=moi["form_id"], khung=khung, expected_version=1, identity=ql
        )
    # Khung sai bị chặn TRƯỚC khi ghi — bản đang dùng vẫn là 2.
    with pytest.raises(ValidationError):
        await eng.xuat_ban(
            form_id=moi["form_id"],
            khung=[{"ma": "x", "ten": "X", "block": [{"ma": "x", "ten": "X"}]}],
            expected_version=2,
            identity=ql,
        )
    dang = await eng.doc_bieu_mau(form_id=moi["form_id"], identity=ql)
    assert dang["version"] == 2


async def test_hai_nguoi_xuat_ban_cung_luc_mot_nguoi_nhan_409(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    async with pool.acquire() as conn:
        ql = await _nguoi(conn, "MANAGEMENT")
    moi = await MauKetQuaService(pool).tao_mau(ten=_ten(), nhom="XN", identity=ql)
    eng = FormEngineService(pool)
    khung = (await eng.doc_bieu_mau(form_id=moi["form_id"], identity=ql))["khung"]
    ra = await asyncio.gather(
        *(
            eng.xuat_ban(
                form_id=moi["form_id"], khung=khung, expected_version=1, identity=ql
            )
            for _ in range(2)
        ),
        return_exceptions=True,
    )
    assert sorted(type(x).__name__ for x in ra) == ["ConflictError", "dict"]


async def test_bang_gan_chi_dich_vu_co_phong_va_theo_quyen(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    async with pool.acquire() as conn:
        ql = await _nguoi(conn, "MANAGEMENT")
        bs = await _nguoi(conn, "DOCTOR")
    svc = MauKetQuaService(pool)
    bang = await svc.bang_gan(identity=ql)
    assert bang["quyen"] == {"gan": True, "sua": True, "xuat_ban": True}
    assert bang["dich_vu"], "seed có dịch vụ có phòng làm"
    ma_phi_kham = {
        r["service_code"]
        for r in await pool.fetch(
            "SELECT service_code FROM service_price WHERE clinic_id = $1::uuid"
            " AND node_code IS NULL",
            CLINIC,
        )
    }
    assert not ({d["service_code"] for d in bang["dich_vu"]} & ma_phi_kham)
    # Gắn một mẫu → bảng thấy ngay.
    dv = bang["dich_vu"][0]["service_code"]
    moi = await svc.tao_mau(ten=_ten(), nhom="XN", identity=ql)
    await svc.gan(service_code=dv, mau=moi["ma"], identity=ql)
    lai = await svc.bang_gan(identity=ql)
    assert moi["ma"] in next(
        d["mau"] for d in lai["dich_vu"] if d["service_code"] == dv
    )
    assert any(m["ma"] == moi["ma"] and m["version"] == 1 for m in lai["mau"])
    await svc.go(service_code=dv, mau=moi["ma"], identity=ql)
    with pytest.raises(SafetyGateError):
        await svc.bang_gan(identity=bs)
    with pytest.raises(SafetyGateError):
        await FormEngineService(pool).doc_bieu_mau(form_id=moi["form_id"], identity=bs)
