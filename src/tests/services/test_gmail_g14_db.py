"""Gmail G14 (12/11/2026) chạy thật trên DB: thư SĐT lệch hồ sơ mà tên + năm sinh
khớp đúng MỘT khách duy nhất có chỉ định của lab ⇒ máy TỰ GÁN vào chỉ định đó; lệch
năm sinh / trùng tên ⇒ không (gợi ý G9 như cũ); NGƯỜI gán ⇒ SĐT trên phiếu vào "SĐT
thêm" của khách (tự học), số đã có thì thôi."""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

import asyncpg
import pytest

from clinicai.core.clock import hom_nay_vn
from clinicai.services.xet_nghiem import (
    ghep_khach,
    gmail,
    gmail_bu_cu,
    gmail_goi_y,
    gmail_ten_nam_sinh,
)
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


async def test_thu_khong_co_sdt_ten_va_nam_sinh_khop_thi_tu_gan(
    pool: asyncpg.Pool,  # noqa: F811
    c3: Ca3,  # noqa: F811
    ns_tren_phieu: None,
) -> None:
    # Phiếu không ghi SĐT: chỉ còn tên + năm sinh — khớp đúng một khách ⇒ vẫn tự gán.
    v, ten = await _khach(pool, c3)
    mid = c3.thu(ten, "")
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
    # Cả phòng khám có HAI hồ sơ đang dùng mang đúng tên + năm sinh này ⇒ không tự gán.
    v2, ten2 = await _khach(pool, c3)
    trung = await c3.viec(pool, ban_xn=False)
    await _ten(pool, trung["kh"], ten2)
    await _nam(pool, trung["kh"], 1983)
    mid2 = c3.thu(ten2, SDT_PHIEU)
    await gmail.mot_vong(pool)
    d2 = await _dong(pool, mid2)
    assert d2["tep_ket_qua_id"] is None


async def test_trung_ten_khac_nam_hoac_khong_ro_nam_van_tu_gan(
    pool: asyncpg.Pool,  # noqa: F811
    c3: Ca3,  # noqa: F811
    ns_tren_phieu: None,
) -> None:
    # Tuyền 12/11: nhiều hồ sơ cùng tên, chỉ MỘT người đúng năm sinh phiếu ⇒ tự gán.
    # Hồ sơ cùng tên không rõ năm sinh không tính. Năm của khách lấy từ NGÀY sinh khi
    # cột năm sinh trống (có ca prod như vậy).
    v, ten = await _khach(pool, c3)
    await pool.execute(
        "UPDATE patient SET birth_year = NULL, date_of_birth = '1983-05-02'"
        " WHERE clinic_patient_id = $1::uuid",
        v["kh"],
    )
    khac_nam = await c3.viec(pool, ban_xn=False)
    await _ten(pool, khac_nam["kh"], ten)
    await _nam(pool, khac_nam["kh"], 1990)
    khong_ro = await c3.viec(pool, ban_xn=False)
    await _ten(pool, khong_ro["kh"], ten)
    await _nam(pool, khong_ro["kh"], None)
    mid = c3.thu(ten, SDT_PHIEU)
    await gmail.mot_vong(pool)
    to = await _to(pool, (await _dong(pool, mid))["id"])
    assert (to["kh"], to["oid"]) == (v["kh"], v["oid"])


async def test_nguoi_gan_thu_cu_thi_ghi_da_tra_ngoai_he_thong(
    pool: asyncpg.Pool,  # noqa: F811
    c3: Ca3,  # noqa: F811
    ns_tren_phieu: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Tuyền 12/11: thư về TRƯỚC mốc 11/11 mà giờ mới gán ⇒ tờ "đã trả ngoài hệ thống",
    # không sinh việc CSKH "Kết quả chưa gửi"; thư từ mốc ⇒ tờ chưa gửi như thường.
    # drive_tep khoá ngày thư (không lùi được) ⇒ dời MỐC thay vì lùi thư, như test bù.
    nguoi = await _nguoi(pool)
    ket_qua = {}
    for cu, moc in ((True, hom_nay_vn() + timedelta(days=1)), (False, hom_nay_vn())):
        monkeypatch.setattr(gmail_bu_cu, "MOC_MAC_DINH", moc)
        v, ten = await _khach(pool, c3, ns=1984)  # lệch năm sinh ⇒ máy không tự gán
        mid = c3.thu(ten, SDT_PHIEU)
        await gmail.mot_vong(pool)
        d = await _dong(pool, mid)
        assert d["tep_ket_qua_id"] is None
        kq = await gmail_goi_y.gan_cho_khach(
            pool, nguoi, {"drive_tep_id": d["id"], "clinic_patient_id": v["kh"]}
        )
        ket_qua[cu] = await pool.fetchrow(
            "SELECT xac_nhan_trang_thai AS tt, gui_kenh, gui_boi_staff_id::text AS boi"
            " FROM tep_ket_qua WHERE id = $1::uuid",
            kq["tep_id"],
        )
    thu_cu, moi = ket_qua[True], ket_qua[False]
    assert (thu_cu["tt"], thu_cu["gui_kenh"], thu_cu["boi"]) == (
        "HOP_LE",
        gmail_bu_cu.KENH,
        nguoi.staff_id,
    )
    assert (moi["tt"], moi["gui_kenh"]) == ("HOP_LE", None)


@pytest.mark.parametrize("luot_cach_ngay", [0, 20])
async def test_khong_chi_dinh_neo_luot_kham_trong_14_ngay(
    pool: asyncpg.Pool,  # noqa: F811
    c3: Ca3,  # noqa: F811
    ns_tren_phieu: None,
    luot_cach_ngay: int,
) -> None:
    # G16 (Tuyền 12/11): tên + năm sinh trùng đúng MỘT hồ sơ, khách KHÔNG có chỉ định
    # nào của lab (bác sĩ không nhập) ⇒ neo lượt khám ≤ 14 ngày trước thư: tờ vào hồ
    # sơ theo lượt. Lượt cũ hơn 14 ngày ⇒ không đoán, người gán.
    v, ten = await _khach(pool, c3)
    await pool.execute(
        "UPDATE service_order SET exec_status = 'cancelled' WHERE id = $1::uuid",
        v["oid"],
    )
    vid = await pool.fetchval(
        # Lùi thêm 1 giờ: giờ DB và giờ thư (Python) lệch nhau vài giây.
        "UPDATE visit SET checked_in_at = now() - make_interval(days => $2, hours => 1)"
        " FROM service_order o WHERE o.id = $1::uuid AND visit.visit_id = o.visit_id"
        " RETURNING visit.visit_id::text",
        v["oid"],
        luot_cach_ngay,
    )
    mid = c3.thu(ten, SDT_PHIEU)
    await gmail.mot_vong(pool)
    d = await _dong(pool, mid)
    if luot_cach_ngay > gmail_ten_nam_sinh.NEO_LUOT_NGAY:
        assert d["tep_ket_qua_id"] is None
        return
    to = await pool.fetchrow(
        "SELECT clinic_patient_id::text AS kh, service_order_id, appointment_id::text"
        "  AS ap, xac_nhan_trang_thai AS tt FROM tep_ket_qua WHERE id = $1::uuid",
        d["tep_ket_qua_id"],
    )
    ap = await pool.fetchval(
        "SELECT appointment_id::text FROM visit WHERE visit_id = $1::uuid", vid
    )
    assert (to["kh"], to["service_order_id"], to["ap"], to["tt"]) == (
        v["kh"],
        None,
        ap,
        "HOP_LE",
    )


async def test_khong_chi_dinh_hai_ho_so_cung_ten_nam_thi_khong_neo(
    pool: asyncpg.Pool,  # noqa: F811
    c3: Ca3,  # noqa: F811
    ns_tren_phieu: None,
) -> None:
    # Hai hồ sơ cùng tên + năm sinh, không ai có chỉ định của lab ⇒ không đoán.
    v, ten = await _khach(pool, c3)
    hai = await c3.viec(pool, ban_xn=False)
    await _ten(pool, hai["kh"], ten)
    await _nam(pool, hai["kh"], 1983)
    await pool.execute(
        "UPDATE service_order SET exec_status = 'cancelled' WHERE id = ANY($1::uuid[])",
        [v["oid"], hai["oid"]],
    )
    mid = c3.thu(ten, SDT_PHIEU)
    await gmail.mot_vong(pool)
    assert (await _dong(pool, mid))["tep_ket_qua_id"] is None


async def _nam(pool: asyncpg.Pool, kh: str, nam: int | None) -> None:  # noqa: F811
    await pool.execute(
        "UPDATE patient SET birth_year = $2, date_of_birth = NULL"
        " WHERE clinic_patient_id = $1::uuid",
        kh,
        nam,
    )


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
