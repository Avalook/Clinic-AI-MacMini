"""Nhật ký XEM hồ sơ khách (24/11/2026, NĐ 356/2025) — trên Postgres thật.

Khoá:
  1. Đọc hồ sơ qua API thật → MỘT dòng: đúng người, vai, khách, loại, MẪU cửa
     (không đường thật có id). Gọi lại trong 5 phút → vẫn một dòng (gộp).
     Cửa đọc THẤT BẠI (403) → không dòng nào.
  2. Gộp ép ở DB: chỉ mục duy nhất theo khung 5 phút (không chỉ bộ nhớ tiến trình).
  3. Sổ CHỈ THÊM: UPDATE / DELETE / TRUNCATE bị chặn.
  4. Chỉ `permission.manage` (Quản lý) đọc được nhật ký qua API — `ops.view` thì
     gần như ai cũng có; vai `authenticated` (đường PostgREST) không SELECT được;
     màn đọc không trả họ tên khách.
  5. Ghi hỏng không làm hỏng lượt đọc — lỗi vào kho lỗi.
  6. Đầu vào rác (id không phải uuid, ngày rác) không ném.
  7. Bảng khai `CUA_XEM` khớp route thật, loại / khoá hợp lệ.
"""

from __future__ import annotations

import asyncio
import re
import time
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import asyncpg
import httpx
import pytest
import pytest_asyncio
from fastapi.routing import APIRoute

from clinicai.api import xem_ho_so
from clinicai.api.identity import StaffIdentity, get_current_identity
from clinicai.api.xem_ho_so import CUA_XEM, CuaXem, ghi_an_toan
from clinicai.core.database import get_db_pool
from clinicai.main import app
from clinicai.services import nhat_ky_xem_ho_so as nk
from tests.goi_mau_cu import ve_goi_mau_cu
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    _nguoi,
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    _benh_nhan,
    _check_in,
    _dung,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest_asyncio.fixture
async def client(pool: asyncpg.Pool) -> AsyncIterator[httpx.AsyncClient]:  # noqa: F811
    app.dependency_overrides[get_db_pool] = lambda: pool
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        yield c
    app.dependency_overrides.pop(get_db_pool, None)
    app.dependency_overrides.pop(get_current_identity, None)


def _ai_la(ai: StaffIdentity) -> None:
    app.dependency_overrides[get_current_identity] = lambda: ai


async def _dong(pool: asyncpg.Pool, khach: str) -> list[asyncpg.Record]:  # noqa: F811
    return list(
        await pool.fetch(
            "SELECT * FROM nhat_ky_xem_ho_so WHERE clinic_patient_id = $1::uuid",
            khach,
        )
    )


async def test_doc_ho_so_qua_api_de_lai_mot_dong_gop_5_phut(
    pool: asyncpg.Pool,  # noqa: F811
    client: httpx.AsyncClient,
) -> None:
    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    visit = await _check_in(pool, ca, pid, ca.loai_kham)
    _ai_la(ca.bac_si)

    for _ in range(3):  # màn tự tải lại theo tin thời gian thực
        r = await client.get(f"/api/v1/phieu-kham/luot/{visit}/don-thuoc")
        assert r.status_code == 200, r.text
    r = await client.get(f"/api/v1/patients/{pid}")
    assert r.status_code == 200, r.text

    dong = await _dong(pool, pid)
    theo_loai = {d["loai"]: d for d in dong}
    assert sorted(theo_loai) == ["don_thuoc", "ho_so_khach"], dong
    d = theo_loai["don_thuoc"]
    assert str(d["staff_id"]) == ca.bac_si.staff_id
    assert d["vai"] == ca.bac_si.vai_goc.value
    assert str(d["clinic_id"]) == CLINIC
    assert d["doi_tuong_id"] == visit
    # MẪU đường dẫn, không id thật (đường thật có thể mang tên/SĐT tìm kiếm).
    assert d["cua"] == "GET /api/v1/phieu-kham/luot/{visit_id}/don-thuoc"
    assert theo_loai["ho_so_khach"]["cua"] == "GET /api/v1/patients/{id:uuid}"


async def test_doc_that_bai_khong_ghi(
    pool: asyncpg.Pool,  # noqa: F811
    client: httpx.AsyncClient,
) -> None:
    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    await ve_goi_mau_cu(pool, ca.le_tan)  # lễ tân gói cũ: không đọc được bệnh án
    _ai_la(ca.le_tan)
    r = await client.get("/api/v1/clinical-records/doc", params={"patient_id": pid})
    assert r.status_code == 403, r.text
    assert await _dong(pool, pid) == []


async def test_gop_ep_o_db_theo_khung_5_phut(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    luc = datetime(2026, 11, 24, 3, 1, tzinfo=UTC)
    goi: dict[str, Any] = {
        "clinic_id": CLINIC,
        "staff_id": ca.dd.staff_id,
        "vai": "NURSE_ULTRASOUND",
        "loai": "ket_qua",
        "cua": "GET /thu/gop",
        "khach": pid,
    }
    assert await nk.ghi_luot_xem(pool, **goi, luc=luc) is True
    nk._DA_GHI.clear()  # bỏ lối tắt bộ nhớ → buộc đi tới chỉ mục DB
    assert await nk.ghi_luot_xem(pool, **goi, luc=luc + timedelta(minutes=3)) is False
    nk._DA_GHI.clear()
    assert await nk.ghi_luot_xem(pool, **goi, luc=luc + timedelta(minutes=5)) is True
    # Bản ghi khác (doi_tuong_id) trong cùng khung là dòng riêng.
    nk._DA_GHI.clear()
    assert await nk.ghi_luot_xem(pool, **goi, doi_tuong_id="tep-2", luc=luc) is True
    assert len(await _dong(pool, pid)) == 3


async def test_so_chi_them_sua_xoa_truncate_bi_chan(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    await nk.ghi_luot_xem(
        pool,
        clinic_id=CLINIC,
        staff_id=ca.le_tan.staff_id,
        vai="RECEPTION",
        loai="ho_so_khach",
        cua="GET /thu/chi-them",
        khach=pid,
    )
    async with pool.acquire() as conn:
        for sql in (
            "UPDATE nhat_ky_xem_ho_so SET vai = 'X' WHERE clinic_patient_id = $1::uuid",
            "DELETE FROM nhat_ky_xem_ho_so WHERE clinic_patient_id = $1::uuid",
        ):
            with pytest.raises(asyncpg.RaiseError, match="chi duoc THEM"):
                await conn.execute(sql, pid)
        with pytest.raises(asyncpg.RaiseError, match="chi duoc THEM"):
            await conn.execute("TRUNCATE nhat_ky_xem_ho_so")
    assert len(await _dong(pool, pid)) == 1


async def test_vai_authenticated_khong_select_duoc_bang(pool: asyncpg.Pool) -> None:  # noqa: F811
    """Đường PostgREST (vai `authenticated`): không GRANT + REVOKE + RLS."""
    async with pool.acquire() as conn, conn.transaction():
        await conn.execute("SET LOCAL ROLE authenticated")
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.fetch("SELECT * FROM nhat_ky_xem_ho_so LIMIT 1")


async def test_chi_quan_ly_doc_duoc_va_khong_lo_ho_ten(
    pool: asyncpg.Pool,  # noqa: F811
    client: httpx.AsyncClient,
) -> None:
    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    ma = str(
        await pool.fetchval(
            "SELECT patient_code FROM patient WHERE clinic_patient_id = $1::uuid", pid
        )
    )
    khai = CuaXem("phieu_kham", "khach", "x")
    await ghi_an_toan(pool, ca.bac_si, "GET /thu/doc", khai, pid)

    for khong_quyen in (ca.bac_si, ca.le_tan, ca.thu_ngan):
        _ai_la(khong_quyen)
        r = await client.get("/api/v1/ops/xem-ho-so")
        assert r.status_code == 403, (khong_quyen.role, r.text)

    async with pool.acquire() as conn:
        ql = await _nguoi(conn, ca.loc, "MANAGEMENT")
    _ai_la(ql)
    r = await client.get("/api/v1/ops/xem-ho-so", params={"ma_khach": ma})
    assert r.status_code == 200, r.text
    body = r.json()
    assert [(d["ma_khach"], d["loai"]) for d in body["dong"]] == [(ma, "phieu_kham")]
    assert body["dong"][0]["nguoi_xem"] == ca.bac_si.full_name
    assert "Chị Lan" not in r.text  # họ tên khách (của `_benh_nhan`) không ra màn
    assert ca.bac_si.staff_id in {n["staff_id"] for n in body["nhan_vien"]}
    r = await client.get(
        "/api/v1/ops/xem-ho-so", params={"ma_khach": ma, "staff_id": ql.staff_id}
    )
    assert r.json()["dong"] == []


async def test_ghi_hong_khong_chan_nguoi_doc_va_vao_kho_loi(
    pool: asyncpg.Pool,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ca = await _dung(pool)
    cua = f"GET /thu/hong-{uuid.uuid4().hex[:6]}"

    async def hong(*_a: Any, **_k: Any) -> bool:
        raise asyncpg.PostgresConnectionError("mất kết nối giả")

    monkeypatch.setattr(nk, "ghi_luot_xem", hong)
    khai = CuaXem("phieu_kham", "khach", "x")
    await ghi_an_toan(pool, ca.bac_si, cua, khai, str(uuid.uuid4()))  # không ném
    n = await pool.fetchval(
        "SELECT count(*) FROM loi_nhom WHERE vi_tri = $1", f"nhat-ky-xem {cua}"
    )
    assert n == 1


async def test_ghi_cham_bi_cat_theo_tran_gio(
    pool: asyncpg.Pool,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bể kết nối đầy → ghi chậm: người đọc không chờ quá trần, lỗi vào kho lỗi."""
    ca = await _dung(pool)
    cua = f"GET /thu/cham-{uuid.uuid4().hex[:6]}"

    async def cham(*_a: Any, **_k: Any) -> bool:
        await asyncio.sleep(5)
        return True

    monkeypatch.setattr(nk, "ghi_luot_xem", cham)
    monkeypatch.setattr(xem_ho_so, "TRAN_GIAY_GHI", 0.05)
    bat_dau = time.monotonic()
    khai = CuaXem("phieu_kham", "khach", "x")
    await ghi_an_toan(pool, ca.bac_si, cua, khai, str(uuid.uuid4()))
    assert time.monotonic() - bat_dau < 1
    n = await pool.fetchval(
        "SELECT count(*) FROM loi_nhom WHERE vi_tri = $1", f"nhat-ky-xem {cua}"
    )
    assert n == 1


@pytest.mark.parametrize("khoa", sorted(nk._SQL_TRA_KHACH))
async def test_moi_sql_tra_khach_chay_duoc(pool: asyncpg.Pool, khoa: str) -> None:  # noqa: F811
    """Mỗi câu tra khách chạy thật trên lược đồ (id không tồn tại → None, không lỗi
    cột / cú pháp) — chặn đổi tên cột về sau."""
    gia_tri = f"{CLINIC}/khong-co.jpg" if khoa == "anh_sieu_am" else str(uuid.uuid4())
    async with pool.acquire() as conn:
        assert await nk.tra_khach(conn, CLINIC, {khoa: gia_tri}) is None


async def test_dau_vao_rac_khong_nem(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    goi: dict[str, Any] = {
        "clinic_id": CLINIC,
        "staff_id": ca.bac_si.staff_id,
        "vai": "DOCTOR",
        "loai": "ket_qua",
    }
    for k in nk._SQL_TRA_KHACH:  # mọi khoá tra, kể cả khoá ảnh siêu âm (chuỗi)
        tra = {k: "khong-phai-uuid"}
        assert await nk.ghi_luot_xem(pool, **goi, cua=f"GET /rac-{k}", tra=tra) is False
    rac_khach = await nk.ghi_luot_xem(pool, **goi, cua="GET /rac-k", khach="abc")
    assert rac_khach is False
    with pytest.raises(ValueError):  # khoá tra lạ = lỗi lập trình
        await nk.ghi_luot_xem(pool, **goi, cua="GET /khoa-la", tra={"khoa_la": "x"})
    kq = await nk.doc_nhat_ky_xem(
        pool, clinic_id=CLINIC, tu="abc", den="32/13/2026", staff_id="x"
    )
    assert kq["tu"] == kq["den"]  # ngày rác → hôm nay


async def test_tra_khach_tu_anh_sieu_am(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    visit = await _check_in(pool, ca, pid, ca.loai_kham)
    khoa = f"{CLINIC}/sieu-am/{uuid.uuid4()}.jpg"
    await pool.execute(
        "INSERT INTO ultrasound_record (clinic_id, visit_id, clinic_patient_id,"
        " ultrasound_type, image_refs) VALUES ($1::uuid, $2::uuid, $3::uuid,"
        " 'Phụ khoa', ARRAY[$4])",
        CLINIC,
        visit,
        pid,
        khoa,
    )
    cua = "GET /api/v1/ultrasound/image"
    await ghi_an_toan(pool, ca.bac_si, cua, CUA_XEM[cua], khoa)
    dong = await _dong(pool, pid)
    assert [(d["loai"], d["doi_tuong_id"]) for d in dong] == [("tep_ket_qua", khoa)]


async def test_cua_xem_khop_route_that() -> None:
    """Đổi đường cửa mà quên sửa `CUA_XEM` → cửa ấy âm thầm thôi ghi. Chặn ở đây."""
    that = {
        f"{m} {r.path}"
        for r in app.routes
        if isinstance(r, APIRoute)
        for m in r.methods
    }
    assert set(CUA_XEM) <= that, sorted(set(CUA_XEM) - that)
    for khai in CUA_XEM.values():
        assert khai.loai in nk.LOAI
        assert khai.khoa == "khach" or khai.khoa in nk._SQL_TRA_KHACH


async def test_loai_khop_check_cua_db(pool: asyncpg.Pool) -> None:  # noqa: F811
    dinh_nghia = str(
        await pool.fetchval(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint"
            " WHERE conname = 'nhat_ky_xem_ho_so_loai_ck'"
        )
    )
    assert set(re.findall(r"'([a-z_]+)'::text", dinh_nghia)) == set(nk.LOAI)


async def test_khung_cua_khop_date_bin() -> None:
    assert nk.khung_cua(datetime(2026, 11, 24, 3, 4, 59, tzinfo=UTC)) == datetime(
        2026, 11, 24, 3, 0, tzinfo=UTC
    )
    assert nk.khung_cua(datetime(2026, 11, 24, 3, 5, tzinfo=UTC)) == datetime(
        2026, 11, 24, 3, 5, tzinfo=UTC
    )
