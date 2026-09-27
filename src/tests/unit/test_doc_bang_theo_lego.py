"""Bảng / hàng chờ / Xem lượt đọc theo LEGO, không theo vai (đợt 3, 27/09/2026).

Phần THUẦN (không cần database) — bài chạy thật trên Postgres ở
`tests/services/test_quyen_lego_man_db.py`.
"""

from __future__ import annotations

import pytest

from clinicai.api.identity import (
    VAI_LAM_VIEC,
    ClinicRole,
    CuaNoiBo,
    StaffIdentity,
    la_noi_bo,
)
from clinicai.permissions.catalogue import MAN, QUYEN, quyen_cua_khoi
from clinicai.permissions.doc_bang import (
    QUYEN_BANG_LUOT,
    QUYEN_HANG_KHAM,
    QUYEN_HANG_PHONG,
    QUYEN_HANG_TU_VAN,
    quyen_doc_hang_cho,
)
from clinicai.services.xem_luot_service import goi_duoc, muc_duoc_xem


def _ai(vai: ClinicRole, *, lego: frozenset[ClinicRole] | None = None) -> StaffIdentity:
    return StaffIdentity(
        staff_id="s",
        auth_user_id="a",
        full_name="x",
        department=vai.value,
        role=vai,
        clinic_id="c",
        location_id="l",
        location_name="x",
        vai_theo_lego=lego,
    )


def _quyen_lego(*ma: str) -> set[str]:
    return {q for m in ma for k in MAN[m].khoi for q in quyen_cua_khoi(k)}


def test_moi_quyen_khai_trong_doc_bang_co_that() -> None:
    for q in (*QUYEN_BANG_LUOT, *QUYEN_HANG_PHONG, *QUYEN_HANG_TU_VAN):
        assert q in QUYEN, q


@pytest.mark.parametrize(
    ("tu_van", "co_phong", "mong"),
    [
        (True, False, QUYEN_HANG_TU_VAN),
        # Tư vấn là hàng CHUNG — có phòng cũng vẫn hỏi quyền tư vấn.
        (True, True, QUYEN_HANG_TU_VAN),
        (False, True, QUYEN_HANG_PHONG),
        (False, False, QUYEN_HANG_KHAM),
    ],
)
def test_hang_nao_can_quyen_nao(
    tu_van: bool, co_phong: bool, mong: tuple[str, ...]
) -> None:
    assert quyen_doc_hang_cho(tu_van=tu_van, co_phong=co_phong) == mong


@pytest.mark.parametrize(
    ("lego", "hang"),
    [
        ("tu_van", dict(tu_van=True, co_phong=False)),
        ("ban_kham", dict(tu_van=False, co_phong=False)),
        ("ban_kham", dict(tu_van=False, co_phong=True)),
        ("phong", dict(tu_van=False, co_phong=True)),
        ("dieu_phoi", dict(tu_van=True, co_phong=False)),
    ],
)
def test_lego_mo_dung_hang_cua_man_minh(lego: str, hang: dict[str, bool]) -> None:
    """Lego nào có màn đọc hàng chờ thì chính lego ấy mở được hàng ấy + bảng."""
    co = _quyen_lego(lego)
    assert co & set(quyen_doc_hang_cho(**hang)), lego
    assert co & set(QUYEN_BANG_LUOT), lego


def test_lego_khong_lien_quan_khong_mo_hang_kham() -> None:
    for lego in ("tu_van", "phong", "thu_tien_dv", "cham_soc_khach"):
        assert not _quyen_lego(lego) & set(QUYEN_HANG_KHAM), lego
    for lego in ("ban_kham", "phong", "thu_tien_dv", "tiep_don"):
        assert not _quyen_lego(lego) & set(QUYEN_HANG_TU_VAN), lego


def test_moi_lego_man_bang_deu_mo_bang_luot() -> None:
    for lego in (
        "tiep_don",
        "do_sinh_hieu",
        "tu_van",
        "ban_kham",
        "phong",
        "dieu_phoi",
    ):
        assert _quyen_lego(lego) & set(QUYEN_BANG_LUOT), lego
    for lego in ("thu_tien_dv", "thu_tien_thuoc", "cham_soc_khach", "dat_lich"):
        assert not _quyen_lego(lego) & set(QUYEN_BANG_LUOT), lego


# ── Thành viên nội bộ theo VAI TÀI KHOẢN ────────────────────────────────────


def test_noi_bo_xet_vai_tai_khoan_ke_ca_khi_lego_mang_vai_da_tat() -> None:
    """Lễ tân tắt lego Tiếp đón: `cac_vai()` rỗng mà vẫn là người nội bộ."""
    le_tan = _ai(ClinicRole.RECEPTION, lego=frozenset())
    assert le_tan.cac_vai() == frozenset()
    assert la_noi_bo(le_tan) and goi_duoc(le_tan)
    bac_si_chi_tu_van = _ai(ClinicRole.DOCTOR, lego=frozenset())
    assert la_noi_bo(bac_si_chi_tu_van)


def test_doi_tac_va_tv_khong_phai_noi_bo() -> None:
    for vai in (ClinicRole.PARTNER, ClinicRole.DISPLAY):
        assert not la_noi_bo(_ai(vai)) and not goi_duoc(_ai(vai))
    assert CuaNoiBo.allowed_roles == VAI_LAM_VIEC
    assert ClinicRole.PARTNER not in VAI_LAM_VIEC
    assert ClinicRole.DISPLAY not in VAI_LAM_VIEC


async def test_cua_noi_bo_chan_doi_tac() -> None:
    from fastapi import HTTPException

    cua = CuaNoiBo()
    assert await cua(_ai(ClinicRole.CSKH)) is not None
    with pytest.raises(HTTPException) as loi:
        await cua(_ai(ClinicRole.PARTNER))
    assert loi.value.status_code == 403


# ── Xem lượt cắt theo QUYỀN ─────────────────────────────────────────────────


def test_muc_theo_quyen() -> None:
    # Không quyền y khoa → KHÔNG lộ nội dung lâm sàng, dù vai là gì.
    thu_ngan = muc_duoc_xem(_quyen_lego("thu_tien_dv"))
    assert thu_ngan["tai_chinh"] and not thu_ngan["lam_sang"]
    assert not thu_ngan["sinh_hieu"]
    cskh = muc_duoc_xem(_quyen_lego("cham_soc_khach"))
    assert not any(cskh[k] for k in ("lam_sang", "sinh_hieu", "tai_chinh", "thuoc"))
    assert cskh["hanh_chinh"] and cskh["dich_vu"]
    do_sh = muc_duoc_xem(_quyen_lego("do_sinh_hieu"))
    assert do_sh["sinh_hieu"] and not do_sh["lam_sang"]
    # Lego Khám tư vấn / Bàn khám → đọc được lâm sàng.
    for lego in ("tu_van", "ban_kham"):
        m = muc_duoc_xem(_quyen_lego(lego))
        assert m["lam_sang"] and m["sinh_hieu"] and m["thuoc"], lego
    kho = muc_duoc_xem(_quyen_lego("kho_thuoc"))
    assert kho["thuoc"] and not kho["lam_sang"]
    tiep_don = muc_duoc_xem(_quyen_lego("tiep_don"))
    assert tiep_don["tai_chinh"] and not tiep_don["lam_sang"]


@pytest.mark.parametrize("rac", [[], set(), ("khong.co.that",), ["", "  "]])
def test_muc_theo_quyen_dau_vao_rac_khong_mo_gi(rac: object) -> None:
    m = muc_duoc_xem(rac)  # type: ignore[arg-type]
    assert m["hanh_chinh"] and m["dich_vu"]
    assert not any(m[k] for k in ("lam_sang", "sinh_hieu", "tai_chinh", "thuoc"))
