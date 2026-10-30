"""Lưu hội thoại trợ lý trên DB thật (bảng tro_ly_hoi_thoai / tro_ly_tin).

    scripts/test-nhanh.sh src/tests/services/test_tro_ly_hoi_thoai_db.py

Model giả theo kịch bản, công cụ mẫu — kiểm phần LƯU: thứ tự tin, dòng nháp,
duyệt/sửa/chuyển/hoàn tác, lịch sử lượt sau dùng đúng chữ khách đã nhận, và
ràng buộc Postgres chặn trạng thái sai.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

import asyncpg
import pytest

from clinicai.ports.mo_hinh import CongCu, GoiCongCu, KetQuaMoHinh, Tin
from clinicai.services.tro_ly_khach import hoi_thoai
from clinicai.services.tro_ly_khach.cong_cu import CongCuMau
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]
LUC = datetime(2026, 10, 30, 10, 15)
KHAC = "a0000000-0000-4000-8000-0000000000ff"


class MoHinhGia:
    ten = "gia:kich-ban"

    def __init__(self, kich_ban: list[KetQuaMoHinh]) -> None:
        self._kich_ban = list(kich_ban)
        self.da_nhan: list[list[Tin]] = []

    async def tra_loi(
        self,
        *,
        he_thong: str,
        tin: Sequence[Tin],
        cong_cu: Sequence[CongCu] = (),
        max_tokens: int = 1024,
        tinh_nang: str = "tro_ly_khach",
    ) -> KetQuaMoHinh:
        self.da_nhan.append(list(tin))
        return self._kich_ban.pop(0)

    async def dong(self) -> None:
        return None


async def _gui(p: asyncpg.Pool, mh: MoHinhGia, ht: str, tin: str) -> dict[str, Any]:
    return await hoi_thoai.gui_tin(
        p,
        mh,
        CongCuMau(lambda: LUC),
        clinic_id=CLINIC,
        hoi_thoai_id=ht,
        noi_dung=tin,
        luc=LUC,
    )


async def test_mot_luot_ghi_du_tin_va_nhap(pool: asyncpg.Pool) -> None:  # noqa: F811
    ht = (await hoi_thoai.tao(pool, clinic_id=CLINIC, staff_id=None, tieu_de=None))[
        "id"
    ]
    goi = GoiCongCu("c1", "tra_gia_dich_vu", {"tu_khoa": "hpv"})
    mh = MoHinhGia([KetQuaMoHinh("", (goi,)), KetQuaMoHinh("Dạ HPV 650.000đ ạ.")])

    ra = await _gui(pool, mh, ht, "xn hpv bao nhieu")

    assert [t["vai"] for t in ra["tin"]] == [
        "khach",
        "tro_ly",
        "ket_qua_cong_cu",
        "tro_ly",
    ]
    assert [t["thu_tu"] for t in ra["tin"]] == [1, 2, 3, 4]
    nhap = ra["tin"][-1]
    assert nhap["la_nhap"] and nhap["duyet"] is None
    assert nhap["meta"]["buoc"][0]["ten"] == "tra_gia_dich_vu"
    assert ra["tin"][1]["goi_cong_cu"][0]["ten"] == "tra_gia_dich_vu"
    assert ra["tieu_de"] == "xn hpv bao nhieu"

    # Lượt sau: model nhận lại đủ 4 tin cũ + tin mới, theo đúng thứ tự.
    mh2 = MoHinhGia([KetQuaMoHinh("Dạ vâng ạ.")])
    ra2 = await _gui(pool, mh2, ht, "ok c")
    assert [t.vai for t in mh2.da_nhan[0]] == [
        "khach",
        "tro_ly",
        "ket_qua_cong_cu",
        "tro_ly",
        "khach",
    ]
    assert [t["thu_tu"] for t in ra2["tin"]][-2:] == [5, 6]


async def test_duyet_sua_chuyen_hoan_tac(pool: asyncpg.Pool) -> None:  # noqa: F811
    ht = (await hoi_thoai.tao(pool, clinic_id=CLINIC, staff_id=None, tieu_de="t"))["id"]
    ra = await _gui(pool, MoHinhGia([KetQuaMoHinh("Nháp gốc")]), ht, "alo")
    nhap_id = ra["tin"][-1]["id"]

    sua = await hoi_thoai.duyet(
        pool,
        clinic_id=CLINIC,
        tin_id=nhap_id,
        staff_id=None,
        hanh_dong="sua",
        noi_dung="Bản đã sửa",
    )
    assert sua["duyet"] == "sua" and sua["noi_dung_gui"] == "Bản đã sửa"

    # Lượt sau, model thấy BẢN SỬA (chữ khách đã nhận), không phải nháp gốc.
    mh = MoHinhGia([KetQuaMoHinh("ok")])
    await _gui(pool, mh, ht, "tiếp")
    assert mh.da_nhan[0][1].noi_dung == "Bản đã sửa"

    lai = await hoi_thoai.duyet(
        pool, clinic_id=CLINIC, tin_id=nhap_id, staff_id=None, hanh_dong="hoan_tac"
    )
    assert lai["duyet"] is None and lai["noi_dung_gui"] is None

    chuyen = await hoi_thoai.duyet(
        pool, clinic_id=CLINIC, tin_id=nhap_id, staff_id=None, hanh_dong="chuyen"
    )
    assert chuyen["duyet"] == "chuyen"
    lich_su = hoi_thoai.dung_lich_su(
        (await hoi_thoai.doc(pool, clinic_id=CLINIC, hoi_thoai_id=ht))["tin"]  # type: ignore[index]
    )
    assert lich_su[1].noi_dung == hoi_thoai.CAU_DA_CHUYEN


async def test_khong_duyet_duoc_tin_khong_phai_nhap_hay_khac_phong_kham(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ht = (await hoi_thoai.tao(pool, clinic_id=CLINIC, staff_id=None, tieu_de="t"))["id"]
    ra = await _gui(pool, MoHinhGia([KetQuaMoHinh("x")]), ht, "alo")
    tin_khach, nhap = ra["tin"][0]["id"], ra["tin"][-1]["id"]
    with pytest.raises(hoi_thoai.TroLyError):
        await hoi_thoai.duyet(
            pool, clinic_id=CLINIC, tin_id=tin_khach, staff_id=None, hanh_dong="duyet"
        )
    with pytest.raises(hoi_thoai.TroLyError):
        await hoi_thoai.duyet(
            pool, clinic_id=KHAC, tin_id=nhap, staff_id=None, hanh_dong="duyet"
        )
    assert await hoi_thoai.doc(pool, clinic_id=KHAC, hoi_thoai_id=ht) is None
    with pytest.raises(hoi_thoai.TroLyError):
        await hoi_thoai.duyet(
            pool, clinic_id=CLINIC, tin_id=nhap, staff_id=None, hanh_dong="xoa"
        )
    with pytest.raises(hoi_thoai.TroLyError):
        await _gui(pool, MoHinhGia([]), ht, "   ")


async def test_rang_buoc_postgres(pool: asyncpg.Pool) -> None:  # noqa: F811
    ht = (await hoi_thoai.tao(pool, clinic_id=CLINIC, staff_id=None, tieu_de="t"))["id"]
    await _gui(pool, MoHinhGia([KetQuaMoHinh("x")]), ht, "alo")
    # Trùng thứ tự trong một hội thoại.
    with pytest.raises(asyncpg.UniqueViolationError):
        await pool.execute(
            "INSERT INTO tro_ly_tin (hoi_thoai_id, thu_tu, vai)"
            " VALUES ($1::uuid, 1, 'khach')",
            ht,
        )
    # Duyệt một dòng không phải nháp.
    with pytest.raises(asyncpg.CheckViolationError):
        await pool.execute(
            "UPDATE tro_ly_tin SET duyet = 'duyet' WHERE hoi_thoai_id = $1::uuid"
            " AND NOT la_nhap",
            ht,
        )
    # 'sua' mà không có bản sửa.
    with pytest.raises(asyncpg.CheckViolationError):
        await pool.execute(
            "UPDATE tro_ly_tin SET duyet = 'sua' WHERE hoi_thoai_id = $1::uuid"
            " AND la_nhap",
            ht,
        )
