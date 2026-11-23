"""Liên thông đơn thuốc quốc gia — bất biến ép ở Postgres + soát nhiều trang.

Test chỉ kiểm KẾT QUẢ (SO-LUAT Phần 6):
  · `uq_dtqg_gui_phien_ban` — hai bên cùng vào hàng một nội dung → một dòng.
  · `FOR UPDATE SKIP LOCKED` — hai bên cùng gửi → hệ thống quốc gia nhận một lần.
  · trigger `dtqg_gui_chi_di_tiep` — sự việc đã ghi không sửa / xoá.
  · `dtqg_trang_thai` (SQL) = `trang_thai_dong` (Python).
Dựng dữ liệu dùng chung helper của `test_don_thuoc_quoc_gia_db.py`.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import asyncpg
import pytest

from clinicai.adapters.don_thuoc_quoc_gia.gia_lap import KhongKy, ProviderGiaLap
from clinicai.ports.don_thuoc_quoc_gia import ChuKy, GoiDon, KetQuaGui
from clinicai.services.don_thuoc_quoc_gia import hang_cho
from clinicai.services.don_thuoc_quoc_gia.anh_xa import dau_van_tay, doc_goi_don
from clinicai.services.don_thuoc_quoc_gia.gui import gui_den_han
from tests.services.test_don_thuoc_quoc_gia_anh_xa_db import (
    _canh,
    _go_het,
    _luot,
    _them_dong,
)
from tests.services.test_don_thuoc_quoc_gia_db import _ch, _dong_hang, _vong
from tests.services.test_luot_kham_service_db import CLINIC
from tests.services.test_phieu_kham_db import pool  # noqa: F401

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_su_viec_khong_sua_khong_xoa(pool: asyncpg.Pool) -> None:  # noqa: F811
    c = await _canh(pool)
    vid = await _luot(pool, c)
    await _vong(pool, c, ProviderGiaLap())
    (r,) = await _dong_hang(pool, vid)
    for cau in (
        "UPDATE dtqg_gui SET goi = '{}'::jsonb WHERE id = $1",
        "UPDATE dtqg_gui SET so_lan_thu = so_lan_thu + 1 WHERE id = $1",
        "DELETE FROM dtqg_gui WHERE id = $1",
    ):
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await pool.execute(cau, r["id"])


async def test_tranh_chap_vao_hang_mot_dong(pool: asyncpg.Pool) -> None:  # noqa: F811
    """Giao dịch 1 chèn phiên bản 1 (chưa commit) với ĐÚNG nội dung hiện hành;
    giao dịch 2 soát cùng lúc. Thứ tự nào cũng chỉ còn một dòng."""
    c = await _canh(pool)
    vid = await _luot(pool, c)
    ch = _ch(c)
    async with pool.acquire() as conn:
        g = (
            await doc_goi_don(conn, clinic_id=CLINIC, visit_ids=[vid], ma_lien_thong={})
        )[vid]
        tr = conn.transaction()
        await tr.start()
        await conn.execute(
            "INSERT INTO dtqg_gui (clinic_id, visit_id, phien_ban, ma_don, goi,"
            " dau_van_tay) VALUES ($1::uuid, $2::uuid, 1, '79abc0000001-c', '{}', $3)",
            CLINIC,
            vid,
            dau_van_tay(g),
        )
        viec = asyncio.create_task(hang_cho.vao_hang(pool, ch))
        await tr.commit()
        assert await viec == 0
    assert len(await _dong_hang(pool, vid)) == 1


@dataclass
class _ChoMo(ProviderGiaLap):
    """Giả lập báo "đã vào" rồi giữ lời gọi (đang giữ khoá dòng) tới khi mở cổng."""

    giu_ma: str = ""
    da_vao: asyncio.Event = field(default_factory=asyncio.Event)
    cong: asyncio.Event = field(default_factory=asyncio.Event)

    async def gui(self, goi: GoiDon, chu_ky: ChuKy | None) -> KetQuaGui:
        # Chỉ giữ ĐÚNG đơn của bài này — dòng tới hạn của bài khác trong cùng
        # clinic (nếu có) đi thẳng, không treo.
        if goi.ma_don == self.giu_ma and not self.da_vao.is_set():
            self.da_vao.set()
            await self.cong.wait()
        return await super().gui(goi, chu_ky)


async def test_tranh_chap_gui_mot_lan(pool: asyncpg.Pool) -> None:  # noqa: F811
    """Bên 1 đang gửi (giữ khoá dòng) thì bên 2 rút hàng: bên 2 thấy không có gì
    (SKIP LOCKED) và về trước khi bên 1 xong. Hệ thống quốc gia nhận MỘT lần."""
    c = await _canh(pool)
    vid = await _luot(pool, c)
    ch = _ch(c)
    assert await hang_cho.vao_hang(pool, ch) == 1
    (r,) = await _dong_hang(pool, vid)
    gl = _ChoMo(giu_ma=r["ma_don"])
    a = asyncio.create_task(gui_den_han(pool, ch, gl, KhongKy()))
    await gl.da_vao.wait()
    await gui_den_han(pool, ch, gl, KhongKy())
    gl.cong.set()
    await a
    assert gl.loi_goi.count(r["ma_don"]) == 1
    (r,) = await _dong_hang(pool, vid)
    assert (r["tt"], r["so_lan_thu"]) == ("DA_GUI", 1)


async def test_trang_thai_sql_khop_python(pool: asyncpg.Pool) -> None:  # noqa: F811
    c = await _canh(pool)
    vids = [await _luot(pool, c) for _ in range(2)]
    gl = ProviderGiaLap(tu_choi_lan_toi=1)
    await _vong(pool, c, gl)
    await _go_het(pool, c, vids[1])
    await _them_dong(pool, c, vids[0], "Thêm")
    await _vong(pool, c, ProviderGiaLap(hong_lan_toi=5))
    rows = [r for v in vids for r in await _dong_hang(pool, v)]
    assert len(rows) >= 4
    for r in rows:
        cung_luot = [x for x in rows if x["visit_id"] == r["visit_id"]]
        py = hang_cho.trang_thai_dong(
            da_gui=r["da_gui_luc"] is not None,
            co_ban_moi_hon=any(x["phien_ban"] > r["phien_ban"] for x in cung_luot),
            het_luot=r["het_luot_luc"] is not None,
            la_huy=r["la_huy"],
            da_tung_gui=any(
                x["phien_ban"] < r["phien_ban"] and x["da_gui_luc"] is not None
                for x in cung_luot
            ),
        )
        assert py == r["tt"], (r["phien_ban"], r["tt"], py)


async def test_soat_het_moi_trang_luot_moi_khong_bi_lo_cu_chiem(
    pool: asyncpg.Pool,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nhiều lượt hơn một trang soát: một vòng vẫn vào hàng ĐỦ mọi lượt, kể cả
    lượt đóng sau cùng (trước đây LIMIT không con trỏ → lô cũ chiếm chỗ mãi)."""
    monkeypatch.setattr(hang_cho, "LO_SOAT", 2)
    c = await _canh(pool)
    vids = [await _luot(pool, c) for _ in range(5)]
    gl = ProviderGiaLap()
    ket = await _vong(pool, c, gl)
    assert (ket["vao_hang"], ket["da_gui"]) == (5, 5)
    for v in vids:
        assert [r["tt"] for r in await _dong_hang(pool, v)] == ["DA_GUI"]
    # Vòng sau: 5 lượt đã khớp → không thêm gì.
    assert (await _vong(pool, c, gl))["vao_hang"] == 0
