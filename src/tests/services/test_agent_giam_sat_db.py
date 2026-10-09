"""Agent giám sát trên Postgres thật (09/10/2026).

Lượt khám tạo bằng check-in thật; mọi khẳng định chỉ nhìn nhận định có khoá là
lượt của chính bài (tệp khác chạy song song cũng có lượt trong cùng phòng khám).
"""

from __future__ import annotations

from datetime import timedelta

import asyncpg
import pytest

from clinicai.services import agent_giam_sat as ag
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    _benh_nhan,
    _check_in,
    _dung,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

_MO = (
    "SELECT * FROM agent_nhan_dinh WHERE clinic_id = $1::uuid AND loai = $2"
    " AND khoa = $3 AND dong_luc IS NULL"
)


async def _luot(pool: asyncpg.Pool) -> tuple[str, str]:  # noqa: F811
    ca = await _dung(pool)
    vid = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    return vid, ca.bac_si.staff_id


async def _don(pool: asyncpg.Pool, vid: str) -> None:  # noqa: F811
    await pool.execute("DELETE FROM agent_nhan_dinh WHERE khoa = $1", vid)


async def test_cho_lau_mo_cong_don_roi_tu_dong(pool: asyncpg.Pool) -> None:  # noqa: F811
    vid, _ = await _luot(pool)
    try:
        await pool.execute(
            "UPDATE visit SET current_node_since = now() - interval '240 minutes'"
            " WHERE visit_id = $1::uuid",
            vid,
        )
        await ag.mot_vong_phong_kham(pool, CLINIC)
        await ag.mot_vong_phong_kham(pool, CLINIC)
        r = await pool.fetchrow(_MO, CLINIC, "khach_cho_qua_nguong", vid)
        assert r is not None, "chờ 240 phút > ngưỡng → phải có nhận định"
        assert r["so_lan"] == 2, "chạy lại chỉ cộng dồn, không đẻ dòng"
        assert r["muc_bang_chung"] == "quan_sat"
        assert r["agent_version"] == ag.PHIEN_BAN
        assert "Lan" not in r["noi_dung"], "không tên khách trong nhận định"

        # Hết chuyện (khách vừa được chuyển bước) → vòng sau tự đóng 'HET'.
        await pool.execute(
            "UPDATE visit SET current_node_since = now() WHERE visit_id = $1::uuid",
            vid,
        )
        await ag.mot_vong_phong_kham(pool, CLINIC)
        assert await pool.fetchrow(_MO, CLINIC, "khach_cho_qua_nguong", vid) is None
        ly_do = await pool.fetchval(
            "SELECT ly_do_dong FROM agent_nhan_dinh WHERE khoa = $1"
            " AND loai = 'khach_cho_qua_nguong'",
            vid,
        )
        assert ly_do == "HET"
    finally:
        await _don(pool, vid)


async def test_lang_im_la_suy_ra_va_tat_thi_dong_tat(
    pool: asyncpg.Pool,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vid, sid = await _luot(pool)
    # Không đẩy giờ `luc` sang tương lai: chạy lúc gần nửa đêm thì "hôm nay" của
    # `luc` là ngày mai và lượt rơi khỏi điều kiện — bài sẽ chập chờn theo giờ.
    monkeypatch.setattr(ag, "LANG_IM_PHUT", 0)
    try:
        # Khách rời mọi hàng chờ mà lượt vẫn mở = đúng tình huống "bị quên".
        await pool.execute(
            "UPDATE queue_entry SET status = 'left', done_at = now()"
            " WHERE visit_id = $1::uuid"
            "   AND status IN ('blocked', 'waiting', 'called', 'serving')",
            vid,
        )
        luc = await pool.fetchval("SELECT now() + interval '1 second'")
        await ag.mot_vong_phong_kham(pool, CLINIC, luc)
        r = await pool.fetchrow(_MO, CLINIC, "khach_lang_im", vid)
        assert r is not None
        assert r["muc_bang_chung"] == "suy_ra", "đoán từ chỗ vắng sự kiện (§8)"

        # Công tắc: tắt loại này → đóng 'TAT', vòng sau không mở lại.
        await ag.dat_che_do(
            pool, clinic_id=CLINIC, loai="khach_lang_im", che_do="tat", staff_id=sid
        )
        await ag.mot_vong_phong_kham(pool, CLINIC, luc)
        await ag.mot_vong_phong_kham(pool, CLINIC, luc)
        assert await pool.fetchrow(_MO, CLINIC, "khach_lang_im", vid) is None
        assert (
            await pool.fetchval(
                "SELECT ly_do_dong FROM agent_nhan_dinh WHERE khoa = $1"
                " AND loai = 'khach_lang_im'",
                vid,
            )
            == "TAT"
        )
    finally:
        await pool.execute(
            "DELETE FROM agent_cau_hinh WHERE clinic_id = $1::uuid"
            " AND loai = 'khach_lang_im'",
            CLINIC,
        )
        await _don(pool, vid)


async def test_bo_phat_hien_hong_khong_dong_nham(
    pool: asyncpg.Pool,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vid, _ = await _luot(pool)
    monkeypatch.setattr(ag, "LANG_IM_PHUT", 0)
    try:
        await pool.execute(
            "UPDATE queue_entry SET status = 'left', done_at = now()"
            " WHERE visit_id = $1::uuid"
            "   AND status IN ('blocked', 'waiting', 'called', 'serving')",
            vid,
        )
        luc = await pool.fetchval("SELECT now() + interval '1 second'")
        await ag.mot_vong_phong_kham(pool, CLINIC, luc)
        assert await pool.fetchrow(_MO, CLINIC, "khach_lang_im", vid) is not None

        async def hong(*_: object) -> dict[str, list[ag.NhanDinh]]:
            raise RuntimeError("DB chập")

        monkeypatch.setattr(ag, "phat_hien_sql", hong)
        await ag.mot_vong_phong_kham(pool, CLINIC, luc)
        assert await pool.fetchrow(_MO, CLINIC, "khach_lang_im", vid) is not None, (
            "loại không xét được thì giữ nguyên, không coi là 'hết chuyện'"
        )
    finally:
        await _don(pool, vid)


async def test_cham_dung_sai_va_bo_cham(pool: asyncpg.Pool) -> None:  # noqa: F811
    vid, sid = await _luot(pool)
    try:
        await pool.execute(
            "UPDATE visit SET current_node_since = now() - interval '240 minutes'"
            " WHERE visit_id = $1::uuid",
            vid,
        )
        await ag.mot_vong_phong_kham(pool, CLINIC)
        nd = await pool.fetchval(
            "SELECT id::text FROM agent_nhan_dinh WHERE khoa = $1"
            " AND loai = 'khach_cho_qua_nguong'",
            vid,
        )
        assert nd
        ok = await ag.danh_gia(
            pool,
            clinic_id=CLINIC,
            nhan_dinh_id=nd,
            gia_tri="sai",
            ghi_chu="  khách đang làm thủ thuật  ",
            staff_id=sid,
        )
        assert ok
        ds = await ag.danh_sach(pool, clinic_id=CLINIC, chi_dang_mo=True)
        dong = next(x for x in ds["nhan_dinh"] if x["id"] == nd)
        assert dong["danh_gia"] == "sai"
        assert dong["danh_gia_ghi_chu"] == "khách đang làm thủ thuật"
        tk = next(t for t in ds["thong_ke"] if t["loai"] == "khach_cho_qua_nguong")
        assert tk["sai"] >= 1 and tk["che_do"] == "shadow"

        # Bỏ chấm (hoàn tác) xoá sạch cả người chấm.
        await ag.danh_gia(
            pool,
            clinic_id=CLINIC,
            nhan_dinh_id=nd,
            gia_tri=None,
            ghi_chu="x",
            staff_id=sid,
        )
        r = await pool.fetchrow(
            "SELECT danh_gia, danh_gia_boi, danh_gia_luc, danh_gia_ghi_chu"
            " FROM agent_nhan_dinh WHERE id = $1::uuid",
            nd,
        )
        assert r is not None and all(v is None for v in r.values())

        with pytest.raises(ValueError):
            await ag.danh_gia(
                pool,
                clinic_id=CLINIC,
                nhan_dinh_id=nd,
                gia_tri="rác",
                ghi_chu=None,
                staff_id=sid,
            )
    finally:
        await _don(pool, vid)


async def test_vong_toan_he_khong_nem_va_chay_moi_cau_sql(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Ba câu SQL riêng (lặng im / không rõ cơ sở / việc quá hạn) chạy thật trên
    lược đồ hiện hành — đổi tên cột ở migration khác là bài này đỏ."""
    async with pool.acquire() as conn:
        luc = await conn.fetchval("SELECT now()")
        ra = await ag.phat_hien_sql(conn, CLINIC, luc + timedelta(seconds=1))
    assert set(ra) == {"khach_lang_im", "luot_khong_ro_co_so", "viec_qua_han"}
    await ag.mot_vong(pool)


async def test_tat_het_la_dung_han(pool: asyncpg.Pool) -> None:  # noqa: F811
    """Công tắc '*' = tắt HẲN: đóng ngay nhận định đang mở (không chờ vòng sau),
    vòng sau không quét gì, và tóm tắt AI từ chối (không tốn tiền)."""
    from datetime import date

    from clinicai.services import agent_tom_tat

    vid, sid = await _luot(pool)
    try:
        await pool.execute(
            "UPDATE visit SET current_node_since = now() - interval '240 minutes'"
            " WHERE visit_id = $1::uuid",
            vid,
        )
        await ag.mot_vong_phong_kham(pool, CLINIC)
        assert await pool.fetchrow(_MO, CLINIC, "khach_cho_qua_nguong", vid)

        await ag.dat_che_do(
            pool, clinic_id=CLINIC, loai="*", che_do="tat", staff_id=sid
        )
        # Đóng NGAY trong lệnh bấm.
        assert await pool.fetchrow(_MO, CLINIC, "khach_cho_qua_nguong", vid) is None
        # Vòng sau không mở lại dù khách vẫn chờ quá ngưỡng.
        await ag.mot_vong_phong_kham(pool, CLINIC)
        assert await pool.fetchrow(_MO, CLINIC, "khach_cho_qua_nguong", vid) is None

        async def khong_duoc_goi(**_: object) -> object:
            raise AssertionError("agent tắt mà vẫn gọi LLM")

        with pytest.raises(agent_tom_tat.LlmTatError):
            await agent_tom_tat.tao(
                pool, clinic_id=CLINIC, ngay=date(2026, 1, 5), goi=khong_duoc_goi
            )
    finally:
        await pool.execute(
            "DELETE FROM agent_cau_hinh WHERE clinic_id = $1::uuid AND loai = '*'",
            CLINIC,
        )
        await _don(pool, vid)
