"""Gmail G11 (11/11/2026) — GÁN LẠI thư email đã gắn nhầm khách: lệnh bù (tờ cũ
Từ chối / Thu hồi, thư về hàng chờ, gán khách đúng bằng lệnh gán G10).
Dừng sớm ⇒ không đổi gì."""

from __future__ import annotations

from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError
from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.services.xet_nghiem import ghep_tay, gmail, gmail_gan_lai, gmail_goi_y
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_gmail_g3_db import (  # noqa: F401
    Ca3,
    _dong,
    _to_cua,
    c3,
)
from tests.services.test_xac_nhan_tep_ket_qua_db import _tao_staff

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _nguoi(
    pool: asyncpg.Pool,  # noqa: F811
    xac_nhan: bool = True,
) -> StaffIdentity:
    async with pool.acquire() as conn:
        nguoi = await _tao_staff(
            conn, CLINIC, "NURSE", ["ket_qua.xac_nhan"] if xac_nhan else None
        )
        if not xac_nhan:  # nhóm mẫu theo vai có sẵn quyền này ⇒ gỡ cho người thử
            await conn.execute(
                "DELETE FROM capability_grant WHERE staff_id = $1::uuid"
                "   AND capability = 'result.file.confirm'",
                nguoi.staff_id,
            )
        return nguoi


async def _ten(pool: asyncpg.Pool, kh: str, ten: str) -> None:  # noqa: F811
    await pool.execute(
        "UPDATE patient SET full_name = $2 WHERE clinic_patient_id = $1::uuid", kh, ten
    )


async def _to(pool: asyncpg.Pool, dong_id: str) -> Any:  # noqa: F811
    return await pool.fetchrow(
        "SELECT t.tep_ket_qua_id::text AS tep, k.xac_nhan_trang_thai AS tt,"
        "       k.clinic_patient_id::text AS kh, k.service_order_id::text AS oid"
        "  FROM drive_tep t LEFT JOIN tep_ket_qua k ON k.id = t.tep_ket_qua_id"
        " WHERE t.id = $1::uuid",
        dong_id,
    )


async def _tu_gan(pool: asyncpg.Pool, c3: Ca3) -> tuple[Any, Any, Any]:  # noqa: F811
    """Khách A tự gán (máy, CHO_XAC_NHAN); khách B có chỉ định đang chờ, TRƯỚC thư."""
    a = await c3.viec(pool, ban_xn=False)
    b = await c3.viec(pool, ban_xn=False)
    await _ten(pool, b["kh"], "Phạm Thị Bê Gán Lại")
    mid = c3.thu(a["ten"], a["sdt"])
    await gmail.mot_vong(pool)
    d = await _dong(pool, mid)
    assert d["tep_ket_qua_id"] is not None
    return a, b, d


async def test_gan_lai_to_may_tu_gan_thi_tu_choi_cu_va_vao_chi_dinh_khach_dung(
    pool: asyncpg.Pool,  # noqa: F811
    c3: Ca3,  # noqa: F811
) -> None:
    a, b, d = await _tu_gan(pool, c3)
    cu = await _to(pool, d["id"])
    assert (cu["tt"], cu["kh"]) == ("CHO_XAC_NHAN", a["kh"])
    kq = await gmail_gan_lai.gan_lai(
        pool,
        await _nguoi(pool),
        {"drive_tep_id": d["id"], "clinic_patient_id": b["kh"], "ly_do": "Sai người"},
    )
    moi = await _to(pool, d["id"])
    assert moi["tep"] == kq["tep_id"] and moi["tep"] != cu["tep"]
    assert (moi["kh"], moi["oid"], moi["tt"]) == (b["kh"], b["oid"], "HOP_LE")
    tt_cu = await pool.fetchval(
        "SELECT xac_nhan_trang_thai FROM tep_ket_qua WHERE id = $1::uuid", cu["tep"]
    )
    assert tt_cu == "TU_CHOI"


async def test_gan_lai_to_hop_le_thi_thu_hoi_co_ly_do(
    pool: asyncpg.Pool,  # noqa: F811
    c3: Ca3,  # noqa: F811
) -> None:
    """Tờ đã HỢP LỆ (người gán G10) ⇒ tờ cũ THU HỒI kèm lý do, không xoá."""
    a, b, d = await _tu_gan(pool, c3)
    nguoi = await _nguoi(pool)
    await gmail_gan_lai.gan_lai(
        pool,
        nguoi,
        {"drive_tep_id": d["id"], "clinic_patient_id": b["kh"], "ly_do": "Nhầm"},
    )
    giua = await _to(pool, d["id"])
    assert giua["tt"] == "HOP_LE"
    await gmail_gan_lai.gan_lai(
        pool,
        nguoi,
        {"drive_tep_id": d["id"], "clinic_patient_id": a["kh"], "ly_do": "Lại nhầm"},
    )
    cu = await pool.fetchrow(
        "SELECT xac_nhan_trang_thai, thu_hoi_ly_do, da_xoa_luc FROM tep_ket_qua"
        " WHERE id = $1::uuid",
        giua["tep"],
    )
    assert cu["xac_nhan_trang_thai"] == "THU_HOI" and "Lại nhầm" in cu["thu_hoi_ly_do"]
    assert cu["da_xoa_luc"] is None
    assert (await _to(pool, d["id"]))["kh"] == a["kh"]


async def test_dung_som_thi_khong_doi_gi(
    pool: asyncpg.Pool,  # noqa: F811
    c3: Ca3,  # noqa: F811
) -> None:
    """Cùng khách / khách rác / thiếu lý do / thiếu quyền Xác nhận kết quả ⇒ dừng,
    tờ cũ và thư giữ nguyên."""
    a, b, d = await _tu_gan(pool, c3)
    truoc = await _to(pool, d["id"])
    ca = [
        (await _nguoi(pool), a["kh"], "Lý do", ConflictError),
        (await _nguoi(pool), "khong-phai-uuid", "Lý do", ConflictError),
        (await _nguoi(pool), b["kh"], "", Exception),
        (await _nguoi(pool, xac_nhan=False), b["kh"], "Lý do", SafetyGateError),
    ]
    for nguoi, kh, ly, loi in ca:
        with pytest.raises(loi):
            await gmail_gan_lai.gan_lai(
                pool,
                nguoi,
                {"drive_tep_id": d["id"], "clinic_patient_id": kh, "ly_do": ly},
            )
        assert await _to(pool, d["id"]) == truoc


async def test_buoc_gan_moi_hong_thi_thu_ve_hang_cho(
    pool: asyncpg.Pool,  # noqa: F811
    c3: Ca3,  # noqa: F811
) -> None:
    """Khách mới không có chỉ định, không có lượt ⇒ tờ cũ đã bù, thư về hàng chờ (gán
    tiếp được bằng ô tìm khách) — không mất thư."""
    a, b, d = await _tu_gan(pool, c3)
    await pool.execute(
        "UPDATE service_order SET created_at = now() - interval '61 days'"
        " WHERE id = $1::uuid",
        b["oid"],
    )
    await pool.execute(
        "UPDATE visit SET checked_in_at = now() - interval '70 days',"
        "       created_at = now() - interval '70 days'"
        " WHERE clinic_patient_id = $1::uuid",
        b["kh"],
    )
    with pytest.raises(ConflictError, match="lượt khám"):
        await gmail_gan_lai.gan_lai(
            pool,
            await _nguoi(pool),
            {"drive_tep_id": d["id"], "clinic_patient_id": b["kh"], "ly_do": "Nhầm"},
        )
    assert (await _to(pool, d["id"]))["tep"] is None
    async with pool.acquire() as conn:
        assert d["id"] in {t["id"] for t in await ghep_tay.ds_cho(conn, CLINIC)}
    # Gán tiếp cho đúng khách cũ bằng lệnh G10.
    kq = await gmail_goi_y.gan_cho_khach(
        pool,
        await _nguoi(pool),
        {"drive_tep_id": d["id"], "clinic_patient_id": a["kh"]},
    )
    assert kq["vao_chi_dinh"] is True


async def test_danh_sach_da_gan_loc_va_co_quyen(
    pool: asyncpg.Pool,  # noqa: F811
    c3: Ca3,  # noqa: F811
) -> None:
    a, b, d = await _tu_gan(pool, c3)
    await _ten(pool, a["kh"], "Lê Thị Đã Gán Mười Một")
    co = await gmail_gan_lai.da_gan(pool, await _nguoi(pool), "da gan muoi mot")
    assert [t["id"] for t in co["thu"]] == [d["id"]]
    t = co["thu"][0]
    assert (t["nhan_to"], t["vao_chi_dinh"], t["ghep_boi"]) == (
        "Chờ xác nhận",
        True,
        "Tự ghép",
    )
    assert co["co_quyen_gan_lai"] is True
    khong = await gmail_gan_lai.da_gan(pool, await _nguoi(pool, xac_nhan=False), "")
    assert khong["co_quyen_gan_lai"] is False
