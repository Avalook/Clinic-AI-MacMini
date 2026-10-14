"""SỔ NỢ HAI CHIỀU (Tuyền chốt 14/10/2026 — G4b).

    scripts/test-nhanh.sh src/tests/services/test_so_no_hai_chieu_db.py

Mỗi lối rò bộ giả lập (`test_mo_phong_dong_tien_db.py`) chứng minh được phải
hiện thành dòng trong sổ: đúng chiều, đúng số, đúng vì sao. Sổ chỉ thêm; số dư
sau = trước + chênh (Postgres ép); sự kiện chạy lại không ghi thêm.
"""

from __future__ import annotations

import random
from collections.abc import AsyncIterator
from typing import Any

import asyncpg
import pytest
import pytest_asyncio

from clinicai.core.exceptions import ClinicAIBaseException
from clinicai.events.catalogue import CONG_NO, DANH_MUC, SO_NO
from clinicai.modules import MODULE
from clinicai.services.cong_no_service import CongNoService
from clinicai.services.hoan_tac_service import HoanTacService
from clinicai.services.hoan_tien_service import HoanTienService
from clinicai.services.payment_service import PaymentService
from clinicai.services.service_execution_service import ServiceExecutionService
from clinicai.services.so_no_service import (
    LOAI_THEO_SU_KIEN,
    chenh_lech,
    dau_ky_mot_vong,
    doi_chieu_mot_vong,
    ghi_chenh_lech,
    so_du_hien_tai,
)
from clinicai.services.tien_thua_service import TienThuaService
from tests.chay_nguoi_dua_tin import chay_ben_nhan
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_mo_phong_dong_tien_db import (
    VIEC,
    _huy_cho,
    _huy_phieu,
    _lam_xong,
    _luot,
    _thu,
    _ve,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import _don, _dung, _khoa
from tests.services.test_thu_truoc_lam_truoc_tick_db import day_thu_truoc
from tests.so_ck import so_ck

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest_asyncio.fixture(autouse=True)
async def _lam_truoc_thu_sau(pool: asyncpg.Pool) -> AsyncIterator[None]:  # noqa: F811
    async with day_thu_truoc(pool, False):
        yield


async def so_lai(pool: asyncpg.Pool, visit: str) -> None:  # noqa: F811
    """Đối chiếu lại sổ của MỘT lượt — việc lượt đối chiếu định kỳ làm cho thay
    đổi không phát sự kiện (bài kiểm sửa DB bằng SQL thẳng dùng cái này)."""
    async with pool.acquire() as conn, conn.transaction():
        await ghi_chenh_lech(
            conn,
            clinic_id=CLINIC,
            visit_id=visit,
            loai="DOI_CHIEU",
            luc=await conn.fetchval("SELECT now()"),
        )


async def _so(pool: asyncpg.Pool, visit: str) -> list[tuple[str, int, int, str]]:  # noqa: F811
    """Chạy bên nhận rồi đọc sổ của lượt: [(chiều, chênh, số dư, loại)]."""
    await chay_ben_nhan(pool, CONG_NO, SO_NO)
    return [
        (r["chieu"], int(r["so_tien"]), int(r["so_du"]), r["loai"])
        for r in await pool.fetch(
            "SELECT chieu, so_tien, so_du, loai FROM so_no"
            " WHERE visit_id = $1::uuid ORDER BY seq",
            visit,
        )
    ]


async def test_chenh_lech_va_danh_sach_su_kien_khop_ba_noi() -> None:
    assert chenh_lech(300_000, 0) == -300_000
    assert chenh_lech(0, 0) == 0
    # Danh mục sự kiện (consumers có SO_NO) = module so_no nghe = bảng loại.
    nghe_danh_muc = {k for k, s in DANH_MUC.items() if SO_NO in s.consumers}
    mod = MODULE["so_no"]
    assert nghe_danh_muc == set(mod.nghe) == set(LOAI_THEO_SU_KIEN)


async def test_ghi_no_ve_roi_tra_sau(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    v, o = await _luot(pool, ca)
    await _lam_xong(pool, ca, o)
    await CongNoService(pool).ghi(identity=ca.le_tan, visit_id=v, ly_do="Quên ví")
    # Còn ở phòng khám: chưa là nợ.
    assert await _so(pool, v) == []
    await _ve(pool, ca, v)
    assert await _so(pool, v) == [("PHAI_THU", 300_000, 300_000, "KHI_VE")]
    await _thu(pool, ca, v)
    so = await _so(pool, v)
    assert so[-1] == ("PHAI_THU", -300_000, 0, "THU")
    # Chạy lại bên nhận: không ghi thêm.
    assert await _so(pool, v) == so


async def test_r2_huy_phieu_sau_khi_ve_thanh_no(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    v, o = await _luot(pool, ca)
    await _thu(pool, ca, v)
    await _lam_xong(pool, ca, o)
    await _ve(pool, ca, v)
    assert await _so(pool, v) == []
    await _huy_phieu(pool, ca, v)
    assert await _so(pool, v) == [("PHAI_THU", 300_000, 300_000, "HUY_PHIEU")]


async def test_r11_ck_cho_cho_ve_la_no_tu_luc_ve_huy_cho_van_no(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Tiền chưa về thì vẫn là nợ (Tuyền 14/10): khách về khi CK còn chờ → sổ
    ghi nợ ngay; quầy huỷ lần chờ → nợ còn nguyên, không ghi thêm."""
    ca = await _dung(pool)
    v, o = await _luot(pool, ca)
    await _lam_xong(pool, ca, o)
    await _thu(pool, ca, v, method="TRANSFER")
    await _ve(pool, ca, v)
    assert await _so(pool, v) == [("PHAI_THU", 300_000, 300_000, "KHI_VE")]
    await _huy_cho(pool, ca, v)
    assert await _so(pool, v) == [("PHAI_THU", 300_000, 300_000, "KHI_VE")]


async def test_tra_no_bang_ck_chi_giam_luc_xac_minh(pool: asyncpg.Pool) -> None:  # noqa: F811
    """Khách nợ quay lại chuyển khoản: lúc CHỜ, nợ chưa giảm; xác minh xong mới
    là "nợ thu được" (THU) — đúng ngày tiền vào, không thành "điều chỉnh"."""
    ca = await _dung(pool)
    v, o = await _luot(pool, ca)
    await _lam_xong(pool, ca, o)
    await CongNoService(pool).ghi(identity=ca.le_tan, visit_id=v, ly_do="Quên ví")
    await _ve(pool, ca, v)
    cid = await _thu(pool, ca, v, method="TRANSFER")
    assert await _so(pool, v) == [("PHAI_THU", 300_000, 300_000, "KHI_VE")]
    # Lượt đối chiếu định kỳ cũng không thấy lệch trong lúc chờ.
    await doi_chieu_mot_vong(pool)
    assert len(await _so(pool, v)) == 1
    await PaymentService(pool).xac_minh_dien_tu(
        payment_cycle_id=cid,
        visit_id=v,
        kind="dich_vu",
        reference="FT999",
        identity=ca.thu_ngan,
        so_tien_thuc_nhan=await so_ck(pool, cid),
    )
    assert (await _so(pool, v))[-1] == ("PHAI_THU", -300_000, 0, "THU")


async def test_r13_bam_xong_muon_sau_khi_ve_thanh_no(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    v, o = await _luot(pool, ca)
    await _ve(pool, ca, v)  # chưa làm, chưa thu → không nợ, về được
    assert await _so(pool, v) == []
    await _lam_xong(pool, ca, o)  # kỹ thuật viên bấm Xong muộn
    assert await _so(pool, v) == [("PHAI_THU", 300_000, 300_000, "DOI_CHI_DINH")]


async def test_da_thu_chua_lam_ve_la_no_khach_hoan_xong_het(pool: asyncpg.Pool) -> None:  # noqa: F811
    """Khách D: đã thu, về chưa làm → phòng khám nợ khách. Không làm (vẫn nợ,
    cùng số — không ghi) → hoàn tiền thừa → hết."""
    ca = await _dung(pool)
    v, o = await _luot(pool, ca)
    await _thu(pool, ca, v)
    await _ve(pool, ca, v)
    assert await _so(pool, v) == [("PHAI_TRA", 300_000, 300_000, "KHI_VE")]
    d = await _don(pool, o)
    await ServiceExecutionService(pool).khong_lam(
        order_id=o,
        expected_execution_revision=int(d["execution_revision"]),
        ly_do="PATIENT_DECLINED_AT_ROOM",
        ghi_chu=None,
        identity=ca.dd,
        idempotency_key=_khoa(),
    )
    assert len(await _so(pool, v)) == 1
    await HoanTienService(pool).hoan_tien_thua(identity=ca.thu_ngan, visit_id=v)
    assert (await _so(pool, v))[-1] == ("PHAI_TRA", -300_000, 0, "HOAN_TIEN")


async def test_giu_lai_tien_thua_van_la_no_khach(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    v, o = await _luot(pool, ca)
    await _thu(pool, ca, v)
    await HoanTacService(pool).huy_chi_dinh(
        order_id=o, identity=ca.bac_si, xac_nhan=True, ly_do="Khách đổi ý"
    )
    await TienThuaService(pool).giu_lai(
        identity=ca.thu_ngan, visit_id=v, ly_do="Khách để lại trừ lần sau"
    )
    await _ve(pool, ca, v)
    assert await _so(pool, v) == [("PHAI_TRA", 300_000, 300_000, "KHI_VE")]


async def test_so_chi_them_va_so_du_phai_khop(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    v, o = await _luot(pool, ca)
    await _lam_xong(pool, ca, o)
    await CongNoService(pool).ghi(identity=ca.le_tan, visit_id=v, ly_do="Quên ví")
    await _ve(pool, ca, v)
    await _so(pool, v)
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await pool.execute("UPDATE so_no SET so_tien = 1 WHERE visit_id = $1::uuid", v)
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await pool.execute("DELETE FROM so_no WHERE visit_id = $1::uuid", v)
    # Số dư sau ≠ trước + chênh → Postgres từ chối.
    with pytest.raises(asyncpg.CheckViolationError, match="số dư lệch"):
        await pool.execute(
            "INSERT INTO so_no (clinic_id, visit_id, clinic_patient_id, chieu,"
            " so_tien, so_du, loai, luc)"
            " SELECT clinic_id, visit_id, clinic_patient_id, 'PHAI_THU', -100000,"
            " 0, 'DOI_CHIEU', now() FROM visit WHERE visit_id = $1::uuid",
            v,
        )


async def _chay_dau_ky_het(pool: asyncpg.Pool) -> dict[str, Any]:  # noqa: F811
    ket: dict[str, Any] = {"con": 1}
    for _ in range(200):
        ket = await dau_ky_mot_vong(pool)
        if not ket["con"]:
            break
    return ket


async def test_dau_ky_cho_luot_cu_roi_doi_chieu_bat_thay_doi_khong_su_kien(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    v, o = await _luot(pool, ca)
    await _lam_xong(pool, ca, o)
    await CongNoService(pool).ghi(identity=ca.le_tan, visit_id=v, ly_do="Quên ví")
    await _ve(pool, ca, v)
    await chay_ben_nhan(pool, CONG_NO)
    # Bật sổ SAU khi lượt này đã có nợ, chưa bên nhận sổ nào chạy: bỏ hết việc
    # đang chờ của bên nhận sổ để mô phỏng lượt có trước ngày bật sổ.
    await pool.execute(
        "UPDATE event_delivery SET status = 'DONE', processed_at = now()"
        " WHERE consumer = $1"
        " AND status <> 'DONE'",
        SO_NO,
    )
    await pool.execute(
        "UPDATE so_no_moc SET bat_dau = now(), dau_ky_den = NULL,"
        " dau_ky_den_id = NULL, dau_ky_xong = false WHERE clinic_id = $1::uuid",
        CLINIC,
    )
    # Chưa xong đầu kỳ thì đối chiếu đứng yên.
    assert (await doi_chieu_mot_vong(pool))["doi_chieu"] == 0
    assert (await _chay_dau_ky_het(pool))["con"] == 0
    rows = await pool.fetch(
        "SELECT chieu, so_tien, so_du, loai FROM so_no WHERE visit_id = $1::uuid",
        v,
    )
    assert [(r["chieu"], int(r["so_tien"]), r["loai"]) for r in rows] == [
        ("PHAI_THU", 300_000, "DAU_KY")
    ]
    # Chạy lại: không ghi thêm.
    await _chay_dau_ky_het(pool)
    assert (
        await pool.fetchval("SELECT count(*) FROM so_no WHERE visit_id = $1::uuid", v)
        == 1
    )
    # Thu nợ mà KHÔNG chạy bên nhận sổ (mô phỏng thay đổi không phát sự kiện):
    # lượt đối chiếu định kỳ bắt được.
    await _thu(pool, ca, v)
    await pool.execute(
        "UPDATE event_delivery SET status = 'DONE', processed_at = now()"
        " WHERE consumer = $1"
        " AND status <> 'DONE'",
        SO_NO,
    )
    await doi_chieu_mot_vong(pool)
    cuoi = await pool.fetchrow(
        "SELECT so_tien, so_du, loai FROM so_no WHERE visit_id = $1::uuid"
        " ORDER BY seq DESC LIMIT 1",
        v,
    )
    assert (int(cuoi["so_tien"]), int(cuoi["so_du"]), cuoi["loai"]) == (
        -300_000,
        0,
        "DOI_CHIEU",
    )


async def test_bam_lon_xon_so_luon_khop_so_tinh_lai(pool: asyncpg.Pool) -> None:  # noqa: F811
    """Bấm ngẫu nhiên như người thật (cùng bộ thao tác với bộ giả lập): sau mỗi
    bước, số dư cuối trong sổ = số dư tính lại từ đầu, ở cả hai chiều."""
    ca = await _dung(pool)
    lech: list[str] = []
    for hat in range(40):
        rnd = random.Random(1000 + hat)
        v, o = await _luot(pool, ca)
        da_lam: list[str] = []
        for _ in range(10):
            ten = rnd.choice(sorted(VIEC))
            try:
                await VIEC[ten](pool, ca, v, o)
            except (ClinicAIBaseException, AssertionError):
                continue
            da_lam.append(ten)
            await chay_ben_nhan(pool, CONG_NO, SO_NO)
            async with pool.acquire() as conn:
                sd, _pid = await so_du_hien_tai(
                    conn, CLINIC, v, await conn.fetchval("SELECT now()")
                )
                for chieu in ("PHAI_THU", "PHAI_TRA"):
                    so = int(
                        await conn.fetchval(
                            "SELECT so_du FROM so_no WHERE visit_id = $1::uuid"
                            " AND chieu = $2 ORDER BY seq DESC LIMIT 1",
                            v,
                            chieu,
                        )
                        or 0
                    )
                    if so != sd.cua(chieu):
                        lech.append(
                            f"hạt {hat}: {' → '.join(da_lam)} ⇒ {chieu} sổ {so:,}"
                            f" ≠ tính lại {sd.cua(chieu):,}"
                        )
    assert lech == []
