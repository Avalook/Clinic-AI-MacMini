"""Lệnh bù 12/11/2026 — tờ email CŨ (thư trước mốc) ⇒ Hợp lệ + "đã trả khách ngoài hệ
thống"; tờ mới / đã gửi thật không đụng; chạy lại không làm gì thêm; hoàn tác theo lô
gỡ đúng mốc bù; không có việc CSKH "Kết quả chưa gửi" cho tờ đã bù."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.core.clock import hom_nay_vn
from clinicai.core.exceptions import SafetyGateError
from clinicai.services.tep_ket_qua_service import TepKetQuaService
from clinicai.services.xet_nghiem import gmail, gmail_bu_cu
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_gmail_g3_db import Ca3, _dong, c3  # noqa: F401
from tests.services.test_gmail_g11_db import _nguoi, _ten, _to

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _tu_gan(pool: asyncpg.Pool, c3: Ca3, ten: str) -> Any:  # noqa: F811
    """Một tờ máy tự gán vào chỉ định (Hợp lệ ngay từ 12/11) — trả dòng thư + tờ."""
    v = await c3.viec(pool, ban_xn=False)
    await _ten(pool, v["kh"], ten)
    c3.thu(ten, v["sdt"])
    await gmail.mot_vong(pool)
    d = await _dong(pool, c3.thu_raw.id)
    to = await _to(pool, d["id"])
    assert to["tt"] == "HOP_LE"
    return d, to, v


async def _gui(pool: asyncpg.Pool, tep: str) -> Any:  # noqa: F811
    return await pool.fetchrow(
        "SELECT xac_nhan_trang_thai AS tt, xac_nhan_ly_do AS ly, gui_kenh,"
        "       gui_luc, gui_boi_staff_id::text AS boi"
        "  FROM tep_ket_qua WHERE id = $1::uuid",
        tep,
    )


async def test_bu_to_cu_khong_dung_to_moi_va_hoan_tac_theo_lo(
    pool: asyncpg.Pool,  # noqa: F811
    c3: Ca3,  # noqa: F811
) -> None:
    await pool.execute(
        "UPDATE luat_cskh SET bat = true WHERE loai_viec = 'KQ_CHUA_GUI'"
    )
    _cu, to_cu, v_cu = await _tu_gan(pool, c3, "Trần Thị Cũ Bù")
    ai = await _nguoi(pool)
    # Mốc = HÔM NAY: thư về hôm nay là thư MỚI ⇒ không đụng (drive_tep khoá ngày thư —
    # không lùi ngày được, nên đổi mốc thay vì đổi thư).
    await gmail_bu_cu.chay(pool, ai, hom_nay_vn())
    moi = await _gui(pool, to_cu["tep"])
    assert (moi["tt"], moi["gui_luc"]) == ("HOP_LE", None)
    # Mốc = NGÀY MAI: thư hôm nay thành thư cũ ⇒ đánh.
    moc = hom_nay_vn() + timedelta(days=1)
    async with pool.acquire() as conn:
        dem = await gmail_bu_cu.xem_truoc(conn, CLINIC, moc)
    assert sum(dem.values()) >= 1
    assert all("CHO_XAC_NHAN" in k or "HOP_LE" in k for k in dem)

    kq = await gmail_bu_cu.chay(pool, ai, moc)
    assert kq["HOP_LE"] >= 1
    sau = await _gui(pool, to_cu["tep"])
    assert (sau["tt"], sau["gui_kenh"], sau["boi"]) == (
        "HOP_LE",
        gmail_bu_cu.KENH,
        ai.staff_id,
    )
    # Không còn việc CSKH "Kết quả chưa gửi" cho khách tờ cũ.
    assert not await pool.fetchval(
        "SELECT count(*) FROM v_viec_cskh WHERE trang_thai = 'KQ_CHUA_GUI'"
        "   AND clinic_patient_id = $1::uuid",
        v_cu["kh"],
    )
    su_kien = await pool.fetchval(
        "SELECT count(*) FROM domain_event"
        " WHERE event_type = 'lab.old_result_marked_delivered'"
        "   AND payload->>'lo' = $1 AND payload->>'tep_id' = $2",
        kq["lo"],
        to_cu["tep"],
    )
    assert su_kien == 1

    # Chạy lại: không đánh thêm tờ nào.
    lai = await gmail_bu_cu.chay(pool, ai, moc)
    assert sum(v for k, v in lai.items() if k != "lo") == 0

    # Hoàn tác: bắt lý do; đúng lô ⇒ gỡ mốc gửi ngoài hệ thống, Hợp lệ giữ; lại ⇒ 0.
    with pytest.raises(ValidationError):
        await gmail_bu_cu.hoan_tac(pool, ai, kq["lo"], "")
    async with pool.acquire() as conn:
        assert await gmail_bu_cu.so_to_cua_lo(conn, CLINIC, kq["lo"]) >= 1
    assert await gmail_bu_cu.hoan_tac(pool, ai, kq["lo"], "Chạy nhầm mốc") >= 1
    hoan = await _gui(pool, to_cu["tep"])
    assert (hoan["tt"], hoan["gui_luc"], hoan["gui_kenh"]) == ("HOP_LE", None, None)
    assert await gmail_bu_cu.hoan_tac(pool, ai, kq["lo"], "Chạy nhầm mốc") == 0
    # Đánh lại ở lô SAU ⇒ hoàn tác lô CŨ lần nữa không gỡ nhầm mốc của lô sau.
    kq2 = await gmail_bu_cu.chay(pool, ai, moc)
    assert kq2["HOP_LE"] >= 1
    assert await gmail_bu_cu.hoan_tac(pool, ai, kq["lo"], "Lô cũ") == 0
    assert (await _gui(pool, to_cu["tep"]))["gui_kenh"] == gmail_bu_cu.KENH
    assert await gmail_bu_cu.hoan_tac(pool, ai, kq2["lo"], "Lô sau") >= 1
    # ĐỐI CHỨNG: Hợp lệ mà chưa gửi ⇒ việc CSKH "Kết quả chưa gửi" CÓ hiện — tức phép
    # kiểm "không có việc" ở trên là thật, không phải do luật CSKH tắt.
    assert await pool.fetchval(
        "SELECT count(*) FROM v_viec_cskh WHERE trang_thai = 'KQ_CHUA_GUI'"
        "   AND clinic_patient_id = $1::uuid",
        v_cu["kh"],
    )


async def test_to_da_gui_that_khong_dung_va_thieu_quyen_thi_khong_doi_gi(
    pool: asyncpg.Pool,  # noqa: F811
    c3: Ca3,  # noqa: F811
) -> None:
    _d, to, _ = await _tu_gan(pool, c3, "Phạm Thị Đã Gửi Thật")
    ai = await _nguoi(pool)
    moc = hom_nay_vn() + timedelta(days=1)
    await pool.execute(
        "UPDATE tep_ket_qua SET gui_luc = now(), gui_boi_staff_id = $2::uuid,"
        "       gui_kenh = 'ZALO' WHERE id = $1::uuid",
        to["tep"],
        ai.staff_id,
    )
    # Tờ thư cũ đã bị THU HỒI (sai người) ⇒ không đánh.
    _d2, to_tc, _ = await _tu_gan(pool, c3, "Võ Thị Thu Hồi Cũ")
    await TepKetQuaService(pool).thu_hoi_tep(
        identity=ai, tep_id=to_tc["tep"], ly_do="Sai người"
    )
    with pytest.raises(SafetyGateError):
        await gmail_bu_cu.chay(pool, await _nguoi(pool, xac_nhan=False), moc)
    await gmail_bu_cu.chay(pool, ai, moc)
    assert (await _gui(pool, to["tep"]))["gui_kenh"] == "ZALO"
    tc = await _gui(pool, to_tc["tep"])
    assert (tc["tt"], tc["gui_luc"]) == ("THU_HOI", None)


@pytest.mark.parametrize(
    ("luc", "trong"),
    [
        ("2026-11-12T09:00:00+07:00", False),  # thứ Năm sáng
        ("2026-11-12T15:29:00+07:00", False),
        ("2026-11-12T15:30:00+07:00", True),  # biên mở ngày thường
        ("2026-11-12T22:59:00+07:00", True),
        ("2026-11-12T23:00:00+07:00", False),  # biên đóng
        ("2026-11-14T06:29:00+07:00", False),  # thứ Bảy
        ("2026-11-14T06:30:00+07:00", True),  # biên mở cuối tuần
        ("2026-11-12T02:00:00+00:00", False),  # 09:00 giờ VN (đổi múi giờ)
    ],
)
async def test_trong_gio_kham(luc: str, trong: bool) -> None:
    assert gmail_bu_cu.trong_gio_kham(datetime.fromisoformat(luc)) is trong
