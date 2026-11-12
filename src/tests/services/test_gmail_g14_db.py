"""Gmail G14 (12/11/2026) chạy thật trên DB: thư SĐT lệch hồ sơ mà tên + năm sinh
khớp đúng MỘT khách duy nhất có chỉ định của lab ⇒ máy TỰ GÁN vào chỉ định đó; lệch
năm sinh / trùng tên ⇒ không (gợi ý G9 như cũ); NGƯỜI gán ⇒ SĐT trên phiếu vào "SĐT
thêm" của khách (tự học), số đã có thì thôi."""

from __future__ import annotations

import uuid
from typing import Any

import asyncpg
import pytest

from clinicai.services.xet_nghiem import ghep_khach, gmail, gmail_goi_y
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_gmail_g3_db import Ca3, _dong, c3  # noqa: F401
from tests.services.test_gmail_g11_db import _nguoi, _ten, _to

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

SDT_PHIEU = "0900000188"  # GIẢ


@pytest.fixture
def ns_tren_phieu(monkeypatch: pytest.MonkeyPatch) -> None:
    """PDF thử không có chữ ⇒ cho chữ PDF mang năm sinh 1983 (như phiếu HighDetect)."""
    monkeypatch.setattr(ghep_khach, "chu_pdf", lambda _b: "Họ và tên: x\nNS: 1983\n")


async def _khach(pool: asyncpg.Pool, c3: Ca3, ns: int = 1983) -> tuple[Any, str]:  # noqa: F811
    v = await c3.viec(pool, ban_xn=False)
    ten = f"Phan Thị Gờ Mười Bốn {uuid.uuid4().hex[:6]}"
    await _ten(pool, v["kh"], ten)
    await pool.execute(
        "UPDATE patient SET birth_year = $2 WHERE clinic_patient_id = $1::uuid",
        v["kh"],
        ns,
    )
    return v, ten


async def test_sdt_lech_ten_va_nam_sinh_khop_thi_tu_gan_vao_chi_dinh(
    pool: asyncpg.Pool,  # noqa: F811
    c3: Ca3,  # noqa: F811
    ns_tren_phieu: None,
) -> None:
    v, ten = await _khach(pool, c3)
    mid = c3.thu(ten, SDT_PHIEU)  # SĐT phiếu KHÁC SĐT hồ sơ
    await gmail.mot_vong(pool)
    d = await _dong(pool, mid)
    to = await _to(pool, d["id"])
    assert (to["kh"], to["oid"], to["tt"]) == (v["kh"], v["oid"], "HOP_LE")


async def test_lech_nam_sinh_hoac_trung_ten_thi_khong_tu_gan(
    pool: asyncpg.Pool,  # noqa: F811
    c3: Ca3,  # noqa: F811
    ns_tren_phieu: None,
) -> None:
    # Năm sinh hồ sơ khác phiếu ⇒ không tự gán, vẫn gợi ý (G9: tên trùng nguyên).
    v, ten = await _khach(pool, c3, ns=1984)
    mid = c3.thu(ten, SDT_PHIEU)
    await gmail.mot_vong(pool)
    d = await _dong(pool, mid)
    assert d["tep_ket_qua_id"] is None and d["ly_do_cho"] == "KHONG_KHOP_KHACH"
    assert d["goi_y_clinic_patient_id"] == v["kh"]
    # Cả phòng khám có HAI hồ sơ đang dùng mang đúng tên này ⇒ không tự gán.
    v2, ten2 = await _khach(pool, c3)
    trung = await c3.viec(pool, ban_xn=False)
    await _ten(pool, trung["kh"], ten2)
    mid2 = c3.thu(ten2, SDT_PHIEU)
    await gmail.mot_vong(pool)
    d2 = await _dong(pool, mid2)
    assert d2["tep_ket_qua_id"] is None


async def test_nguoi_gan_thi_hoc_sdt_tren_phieu(
    pool: asyncpg.Pool,  # noqa: F811
    c3: Ca3,  # noqa: F811
    ns_tren_phieu: None,
) -> None:
    v, ten = await _khach(pool, c3, ns=1984)  # lệch năm sinh ⇒ máy không tự gán
    mid = c3.thu(ten, SDT_PHIEU)
    await gmail.mot_vong(pool)
    d = await _dong(pool, mid)
    assert d["tep_ket_qua_id"] is None
    nguoi = await _nguoi(pool)
    await gmail_goi_y.gan_cho_khach(
        pool, nguoi, {"drive_tep_id": d["id"], "clinic_patient_id": v["kh"]}
    )

    async def so_them() -> list[str]:
        return [
            r["so_dien_thoai"]
            for r in await pool.fetch(
                "SELECT so_dien_thoai FROM patient_sdt_them"
                " WHERE clinic_patient_id = $1::uuid",
                v["kh"],
            )
        ]

    assert await so_them() == [SDT_PHIEU]
    # Học lại cùng số (lần gán sau của cùng khách) ⇒ số đã có: không thêm, không lỗi.
    await gmail_goi_y._hoc_sdt(pool, nguoi, d["id"], v["kh"], b"%PDF")
    assert await so_them() == [SDT_PHIEU]
