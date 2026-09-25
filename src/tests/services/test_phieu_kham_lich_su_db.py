"""Lịch sử sửa phiếu khám (Tuyền 25/09/2026 — P4A).

Hoàn tất không khoá phiếu → phải xem được ai sửa, lúc nào, ô nào, trước → sau.
Trigger ghi; cùng người trong 10 phút gộp một dòng (phiếu tự lưu mỗi 1,5 giây).
"""

from __future__ import annotations

import asyncpg
import pytest

from clinicai.core.exceptions import SafetyGateError
from clinicai.phieu_kham.khung import cac_o, dinh_nghia
from clinicai.services.phieu_kham_service import PhieuKhamService, kiem_quyen_core
from tests.services.test_phieu_kham_db import (
    _luot,
    _nguoi,
    _o,
    pool,  # noqa: F401
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


def _svc(pool: asyncpg.Pool) -> PhieuKhamService:  # noqa: F811
    return PhieuKhamService(pool, kiem_quyen=kiem_quyen_core)


def _hai_o_van() -> tuple[str, str]:
    o_pk = cac_o(dinh_nghia("PK")["khung"])
    ds = [ma for ma, o in o_pk.items() if o["kieu"] == "doan_van"]
    return ds[0], ds[1]


async def test_gop_theo_nguoi_va_ghi_truoc_sau(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        tk = await _nguoi(conn, "TKYK")
        luot = await _luot(conn, bs)
    svc = _svc(pool)
    a, b = _hai_o_van()
    v = luot["visit"]

    # Bác sĩ tự lưu 3 nhịp → MỘT dòng "ghi lần đầu", giá trị mới nhất.
    rev = 0
    for chu in ("Đau", "Đau bụng", "Đau bụng dưới"):
        rev = (
            await svc.luu_luot(
                visit_id=v,
                form_id="PK",
                du_lieu={a: _o(chu)},
                expected_revision=rev,
                identity=bs,
            )
        )["revision"]
    ls = await svc.lich_su(visit_id=v, form_id="PK", identity=bs)
    assert len(ls) == 1
    assert ls[0]["tao_moi"] is True
    assert ls[0]["thay_doi"] == [{"ma": a, "truoc": None, "sau": "Đau bụng dưới"}]

    # Thư ký sửa ô a + thêm ô b → dòng mới, của thư ký, trước → sau đúng.
    rev = (
        await svc.luu_luot(
            visit_id=v,
            form_id="PK",
            du_lieu={a: _o("Đau bụng dưới 3 ngày"), b: _o("Không")},
            expected_revision=rev,
            identity=tk,
        )
    )["revision"]
    ls = await svc.lich_su(visit_id=v, form_id="PK", identity=bs)
    assert len(ls) == 2
    moi = ls[0]
    assert moi["tao_moi"] is False and moi["sau_hoan_tat"] is False
    assert {t["ma"]: (t["truoc"], t["sau"]) for t in moi["thay_doi"]} == {
        a: ("Đau bụng dưới", "Đau bụng dưới 3 ngày"),
        b: (None, "Không"),
    }

    # Thư ký trả ô a về như cũ → ô a rời khỏi dòng; chỉ còn ô b.
    rev = (
        await svc.luu_luot(
            visit_id=v,
            form_id="PK",
            du_lieu={a: _o("Đau bụng dưới"), b: _o("Không")},
            expected_revision=rev,
            identity=tk,
        )
    )["revision"]
    ls = await svc.lich_su(visit_id=v, form_id="PK", identity=bs)
    assert [t["ma"] for t in ls[0]["thay_doi"]] == [b]

    # Trả nốt ô b → dòng không còn gì thì biến mất.
    await svc.luu_luot(
        visit_id=v,
        form_id="PK",
        du_lieu={a: _o("Đau bụng dưới")},
        expected_revision=rev,
        identity=tk,
    )
    assert len(await svc.lich_su(visit_id=v, form_id="PK", identity=bs)) == 1


async def test_qua_10_phut_dong_moi_va_danh_dau_sau_hoan_tat(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        luot = await _luot(conn, bs)
    svc = _svc(pool)
    a, _b = _hai_o_van()
    v = luot["visit"]
    await svc.luu_luot(
        visit_id=v, form_id="PK", du_lieu={a: _o("x")}, expected_revision=0, identity=bs
    )
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE phieu_kham_lich_su SET sua_luc = now() - interval '11 minutes'"
            " WHERE visit_id = $1::uuid",
            v,
        )
        await conn.execute(
            "UPDATE visit SET exam_completed_at = now() - interval '5 minutes'"
            " WHERE visit_id = $1::uuid",
            v,
        )
    await svc.luu_luot(
        visit_id=v, form_id="PK", du_lieu={a: _o("y")}, expected_revision=1, identity=bs
    )
    ls = await svc.lich_su(visit_id=v, form_id=None, identity=bs)
    assert len(ls) == 2, "quá 10 phút thì không gộp"
    assert ls[0]["sau_hoan_tat"] is True
    assert ls[0]["thay_doi"] == [{"ma": a, "truoc": "x", "sau": "y"}]
    assert ls[1]["sau_hoan_tat"] is False


async def test_le_tan_khong_xem_lich_su(pool: asyncpg.Pool) -> None:  # noqa: F811
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        lt = await _nguoi(conn, "RECEPTION")
        luot = await _luot(conn, bs)
    with pytest.raises(SafetyGateError):
        await _svc(pool).lich_su(visit_id=luot["visit"], form_id=None, identity=lt)
