"""Gmail G11 (11/11/2026) — GÁN LẠI thư email đã gắn nhầm khách: lệnh bù (tờ cũ
Từ chối / Thu hồi, thư về hàng chờ, gán khách đúng bằng lệnh gán G10).
Dừng sớm ⇒ không đổi gì."""

from __future__ import annotations

from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.services.xet_nghiem import gmail, gmail_gan_lai
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
    """Khách A tự gán (máy, Hợp lệ ngay từ 12/11); khách B có chỉ định đang chờ."""
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
    assert (cu["tt"], cu["kh"]) == ("HOP_LE", a["kh"])
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
    # Tờ máy nhận đã Hợp lệ (12/11) ⇒ bù bằng Thu hồi (Từ chối chỉ cho tờ còn chờ).
    assert tt_cu == "THU_HOI"


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
        (await _nguoi(pool), b["kh"], "", ValidationError),
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


async def test_khach_moi_khong_co_cho_gan_thi_dung_truoc_khi_thu_hoi(
    pool: asyncpg.Pool,  # noqa: F811
    c3: Ca3,  # noqa: F811
) -> None:
    """Soát G11: khách mới không có chỉ định, không có lượt ⇒ biết TRƯỚC ⇒ 409, tờ cũ
    và thư giữ nguyên (không thu hồi rồi mới phát hiện)."""
    a, b, d = await _tu_gan(pool, c3)
    truoc = await _to(pool, d["id"])
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
    assert await _to(pool, d["id"]) == truoc


async def test_to_da_thu_hoi_o_cho_khac_van_gan_lai_duoc_va_phat_su_kien(
    pool: asyncpg.Pool,  # noqa: F811
    c3: Ca3,  # noqa: F811
) -> None:
    """Soát G11 (chặn 1): tờ của thư đã bị thu hồi ở chỗ khác (hồ sơ khách) ⇒ thư
    KHÔNG kẹt: hiện "Tờ đã thu hồi / từ chối — chưa gán lại" và gán lại được (bỏ bước
    bù). Mọi lần gán lại phát `lab.email_result_reassigned`."""
    from clinicai.services.tep_ket_qua_service import TepKetQuaService

    a, b, d = await _tu_gan(pool, c3)
    cu = (await _to(pool, d["id"]))["tep"]
    await TepKetQuaService(pool).thu_hoi_tep(
        identity=await _nguoi(pool), tep_id=cu, ly_do="Sai người"
    )
    ds = await gmail_gan_lai.da_gan(pool, await _nguoi(pool), "")
    dong = next(t for t in ds["thu"] if t["id"] == d["id"])
    assert dong["nhan_to"] == gmail_gan_lai.NHAN_MAT_HIEU_LUC
    kq = await gmail_gan_lai.gan_lai(
        pool,
        await _nguoi(pool),
        {"drive_tep_id": d["id"], "clinic_patient_id": b["kh"], "ly_do": "Gán đúng"},
    )
    assert (await _to(pool, d["id"]))["kh"] == b["kh"]
    su_kien = await pool.fetchrow(
        "SELECT payload FROM domain_event"
        " WHERE event_type = 'lab.email_result_reassigned' AND aggregate_id = $1::uuid",
        d["id"],
    )
    assert su_kien is not None
    assert str(kq["tep_id"]) in str(su_kien["payload"]) and cu in str(
        su_kien["payload"]
    )


async def test_to_da_gui_khach_thi_canh_bao_bao_khach(
    pool: asyncpg.Pool,  # noqa: F811
    c3: Ca3,  # noqa: F811
) -> None:
    a, b, d = await _tu_gan(pool, c3)
    nguoi = await _nguoi(pool)
    await gmail_gan_lai.gan_lai(
        pool,
        nguoi,
        {"drive_tep_id": d["id"], "clinic_patient_id": b["kh"], "ly_do": "Nhầm"},
    )
    tep = (await _to(pool, d["id"]))["tep"]
    await pool.execute(
        "UPDATE tep_ket_qua SET gui_luc = now(), gui_boi_staff_id = $2::uuid,"
        "       gui_kenh = 'ZALO' WHERE id = $1::uuid",
        tep,
        nguoi.staff_id,
    )
    ds = await gmail_gan_lai.da_gan(pool, nguoi, "")
    dong = next(t for t in ds["thu"] if t["id"] == d["id"])
    assert dong["da_gui"] is True and "báo khách" in (dong["canh_bao"] or "")


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
        "Hợp lệ",
        True,
        "Tự ghép",
    )
    assert co["co_quyen_gan_lai"] is True
    khong = await gmail_gan_lai.da_gan(pool, await _nguoi(pool, xac_nhan=False), "")
    assert khong["co_quyen_gan_lai"] is False
