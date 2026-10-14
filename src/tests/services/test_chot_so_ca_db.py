"""G4c · KHOÁ SỔ THEO CA (Tuyền chốt A, 14/10/2026).

    scripts/test-nhanh.sh src/tests/services/test_chot_so_ca_db.py

Trước: huỷ phiếu sau khi ca đã kết thúc trừ LÙI vào ngày / ca thu cũ — báo
cáo đã in ra đổi số khi mở lại. Nay ca đã chốt giữ đúng số lúc chốt; huỷ sau
chốt tính vào ca đang làm ("điều chỉnh ca trước"); Quản lý mở khoá có lý do.

Mỗi bài dùng CƠ SỞ RIÊNG (lượt của bài chuyển sang đó) — khoá ca và số liệu
không chạm bài khác chạy song song trên cùng DB.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import replace
from datetime import date, timedelta
from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.clock import now_vn
from clinicai.core.exceptions import SafetyGateError
from clinicai.core.shifts import CAC_CA, ca_tu_settings, khung_chot_ca
from clinicai.services.bao_cao_cuoi_ngay_service import BaoCaoCuoiNgayService
from clinicai.services.chot_so_ca_service import ChotSoCaService
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_mo_phong_dong_tien_db import (  # noqa: F401
    _huy_phieu,
    _lam_truoc_thu_sau,
    _luot,
    _thu,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import Ca, _dung

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


def _ql(ca: Ca) -> StaffIdentity:
    return replace(ca.thu_ngan, role=ClinicRole.MANAGEMENT)


async def _co_so_rieng(pool: asyncpg.Pool) -> str:  # noqa: F811
    return str(
        await pool.fetchval(
            "INSERT INTO clinic_location (clinic_id, code, name)"
            " VALUES ($1::uuid, $2, 'Cơ sở test chốt ca') RETURNING id::text",
            CLINIC,
            f"CS-{uuid.uuid4().hex[:8]}",
        )
    )


async def _ca_bay_gio(pool: asyncpg.Pool) -> str:  # noqa: F811
    st = await pool.fetchval("SELECT settings FROM clinic WHERE id = $1::uuid", CLINIC)
    bang = ca_tu_settings(st)
    bay_gio = now_vn()
    phut = bay_gio.hour * 60 + bay_gio.minute
    for ma in CAC_CA:
        k = khung_chot_ca(ma, bang)
        if k is not None and k[0] <= phut < k[1]:
            return ma
    raise AssertionError("không ca nào phủ giờ hiện tại")


async def _luot_o(pool: asyncpg.Pool, ca: Ca, cs: str) -> str:  # noqa: F811
    """Lượt 300k đã thu tiền mặt, chuyển sang cơ sở riêng của bài."""
    v, _o = await _luot(pool, ca)
    await _thu(pool, ca, v)
    await pool.execute(
        "UPDATE visit SET location_id = $2::uuid WHERE visit_id = $1::uuid", v, cs
    )
    return v


async def _bc(
    pool: asyncpg.Pool,  # noqa: F811
    ql: StaffIdentity,
    cs: str,
    **kw: object,
) -> dict[str, Any]:
    hom_nay = now_vn().date().isoformat()
    return await BaoCaoCuoiNgayService(pool).bao_cao(
        identity=ql, tu=hom_nay, den=hom_nay, co_so=cs, **kw
    )


async def test_chot_roi_huy_sau_chot_so_ca_cu_khong_doi(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    ql = _ql(ca)
    cs = await _co_so_rieng(pool)
    ma = await _ca_bay_gio(pool)
    v = await _luot_o(pool, ca, cs)
    truoc = await _bc(pool, ql, cs, ca=ma)
    assert truoc["chot"] is None and truoc["xem_mot_ca"] is True
    assert (truoc["tong"]["thu"], truoc["tong"]["huy"]) == (300_000, 0)
    kq = await ChotSoCaService(pool).chot(
        identity=ql, ngay=now_vn().date().isoformat(), ca=ma, co_so=cs
    )
    assert kq["ok"]
    await _huy_phieu(pool, ca, v)  # huỷ SAU khi chốt
    sau = await _bc(pool, ql, cs, ca=ma)
    # Ca đã chốt: đúng số lúc chốt, kèm phần phát sinh sau chốt.
    assert sau["chot"]["id"] == kq["id"]
    assert sau["tong"] == truoc["tong"]
    assert sau["sau_chot"] == {
        "thu": 0,
        "huy": 300_000,
        "hoan": 0,
        "thuc_thu": -300_000,
    }
    # Cả ngày (số sống): thu một lần, huỷ một lần — không trừ hai lần.
    ngay = await _bc(pool, ql, cs)
    assert (ngay["tong"]["thu"], ngay["tong"]["huy"]) == (300_000, 300_000)
    dc = [x for x in ngay["hoan_huy"] if x["loai"] == "huy"]
    assert len(dc) == 1 and dc[0]["dieu_chinh_ca_truoc"] is True
    assert ngay["dieu_chinh_ca_truoc"] == {"so_phieu": 1, "tong": 300_000}
    assert ngay["tai_chinh"]["dong_tien"]["khop"] is True


async def test_huy_truoc_khi_chot_van_tinh_o_ca_thu(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    ql = _ql(ca)
    cs = await _co_so_rieng(pool)
    ma = await _ca_bay_gio(pool)
    v = await _luot_o(pool, ca, cs)
    await _huy_phieu(pool, ca, v)  # huỷ TRƯỚC khi chốt → như cũ
    await ChotSoCaService(pool).chot(
        identity=ql, ngay=now_vn().date().isoformat(), ca=ma, co_so=cs
    )
    sau = await _bc(pool, ql, cs, ca=ma)
    assert (sau["tong"]["thu"], sau["tong"]["huy"]) == (300_000, 300_000)
    assert sau["sau_chot"] == {"thu": 0, "huy": 0, "hoan": 0, "thuc_thu": 0}
    assert all(not x.get("dieu_chinh_ca_truoc") for x in sau["hoan_huy"])


async def test_hai_nguoi_chot_cung_luc_chi_mot_lan(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    ql = _ql(ca)
    cs = await _co_so_rieng(pool)
    ngay = (date.today() - timedelta(days=400)).isoformat()
    ket = await asyncio.gather(
        *[
            ChotSoCaService(pool).chot(identity=ql, ngay=ngay, ca="SANG", co_so=cs)
            for _ in range(3)
        ],
        return_exceptions=True,
    )
    assert sum(isinstance(k, dict) for k in ket) == 1
    assert all(isinstance(k, ConflictError) for k in ket if not isinstance(k, dict))
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM chot_so_ca WHERE location_id = $1::uuid", cs
        )
        == 1
    )


async def test_mo_khoa_chi_quan_ly_co_ly_do_roi_chot_lai(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    ql = _ql(ca)
    cs = await _co_so_rieng(pool)
    ngay = (date.today() - timedelta(days=401)).isoformat()
    svc = ChotSoCaService(pool)
    k = await svc.chot(identity=ql, ngay=ngay, ca="CHIEU", co_so=cs, ghi_chu="Đủ két")
    with pytest.raises(ConflictError, match="đã chốt"):
        await svc.chot(identity=ql, ngay=ngay, ca="CHIEU", co_so=cs)
    with pytest.raises(SafetyGateError):
        await svc.mo_khoa(identity=ca.thu_ngan, chot_id=k["id"], ly_do="Nhầm số")
    with pytest.raises(ValidationError):
        await svc.mo_khoa(identity=ql, chot_id=k["id"], ly_do=" ")
    await svc.mo_khoa(identity=ql, chot_id=k["id"], ly_do="Kế toán cần sửa phiếu")
    tt = await svc.trang_thai(identity=ql, ngay=ngay, ca="CHIEU", co_so=cs)
    assert tt["khoa"] is None and tt["mo_khoa_duoc"] is True
    k2 = await svc.chot(identity=ql, ngay=ngay, ca="CHIEU", co_so=cs)
    assert k2["id"] != k["id"]
    nhat_ky = await pool.fetch(
        "SELECT event_type FROM event_log WHERE aggregate_id::text = ANY($1::text[])"
        " ORDER BY occurred_at",
        [k["id"], k2["id"]],
    )
    assert [r["event_type"] for r in nhat_ky] == [
        "report.shift_closed",
        "report.shift_reopened",
        "report.shift_closed",
    ]


async def test_dau_vao_rac_bi_tu_choi(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    ql = _ql(ca)
    cs = await _co_so_rieng(pool)
    svc = ChotSoCaService(pool)
    for ngay, c, s in (
        ("hôm qua", "SANG", cs),
        ("2026-13-40", "SANG", cs),
        ("2026-01-01", "DEM", cs),
        ("2026-01-01", "SANG", None),
        ("2026-01-01", "SANG", "rác"),
    ):
        with pytest.raises(ValidationError):
            await svc.chot(identity=ql, ngay=ngay, ca=c, co_so=s)
    with pytest.raises(Exception):  # noqa: B017 — id rác: không tìm thấy
        await svc.mo_khoa(identity=ql, chot_id="khong-phai-uuid", ly_do="Thử rác")


async def test_postgres_cam_sua_so_chup_va_xoa(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    ql = _ql(ca)
    cs = await _co_so_rieng(pool)
    ngay = (date.today() - timedelta(days=402)).isoformat()
    k = await ChotSoCaService(pool).chot(identity=ql, ngay=ngay, ca="TOI", co_so=cs)
    with pytest.raises(asyncpg.CheckViolationError):
        await pool.execute(
            "UPDATE chot_so_ca SET so_lieu = '{}'::jsonb WHERE id = $1::uuid", k["id"]
        )
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await pool.execute("DELETE FROM chot_so_ca WHERE id = $1::uuid", k["id"])


async def _lui_gio_thu(pool: asyncpg.Pool, visit: str, so_ngay: int) -> None:  # noqa: F811
    """Lùi GIỜ THU của lượt về `so_ngay` ngày trước — dựng "thu hôm qua, huỷ hôm
    nay" mà không đổi giờ ca của phòng khám (DB test dùng chung giữa các bài
    chạy song song). Postgres cấm sửa phiếu đã PAID, nên chỉ phiên này bỏ trigger."""
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("SET LOCAL session_replication_role = replica")
            for bang in ("payment_cycle", "payment"):
                await conn.execute(
                    f"UPDATE {bang} SET paid_at = paid_at - make_interval(days => $2)"
                    " WHERE visit_id = $1::uuid AND paid_at IS NOT NULL",
                    visit,
                    so_ngay,
                )


async def _bc_ngay(
    pool: asyncpg.Pool,  # noqa: F811
    ql: StaffIdentity,
    cs: str,
    tu: date,
    den: date,
    **kw: object,
) -> dict[str, Any]:
    return await BaoCaoCuoiNgayService(pool).bao_cao(
        identity=ql, tu=tu.isoformat(), den=den.isoformat(), co_so=cs, **kw
    )


async def test_mo_khoa_ca_cu_khong_keo_khoan_huy_ve_lai_ca_cu(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Soát #431 (phiên điều phối): khoản huỷ đã chuyển sang ca đang làm thì ở
    YÊN đó, dù sau này ca cũ được mở khoá. Nếu không: hai bản chụp cùng trừ
    một phiếu, cộng các ca ≠ cả ngày.

    Thu hôm qua 300k → chốt ca hôm qua → huỷ HÔM NAY → chốt ca hôm nay (chụp
    có huỷ) → mở khoá ca hôm qua → huỷ phải vẫn ở hôm nay, đúng một lần."""
    ca = await _dung(pool)
    ql = _ql(ca)
    cs = await _co_so_rieng(pool)
    ma = await _ca_bay_gio(pool)
    hom_nay = now_vn().date()
    hom_qua = hom_nay - timedelta(days=1)
    v = await _luot_o(pool, ca, cs)
    await _lui_gio_thu(pool, v, 1)
    svc = ChotSoCaService(pool)
    chot_qua = await svc.chot(identity=ql, ngay=hom_qua.isoformat(), ca=ma, co_so=cs)
    await _huy_phieu(pool, ca, v)
    chot_nay = await svc.chot(identity=ql, ngay=hom_nay.isoformat(), ca=ma, co_so=cs)
    assert (await _bc_ngay(pool, ql, cs, hom_nay, hom_nay, ca=ma))["tong"]["huy"] == (
        300_000
    )
    await svc.mo_khoa(
        identity=ql, chot_id=chot_qua["id"], ly_do="Sửa một việc khác của ca hôm qua"
    )
    # Ca hôm qua (số sống, đã mở khoá): phiếu vẫn là đã thu, KHÔNG bị trừ lùi.
    qua = await _bc_ngay(pool, ql, cs, hom_qua, hom_qua, ca=ma)
    assert (qua["tong"]["thu"], qua["tong"]["huy"]) == (300_000, 0)
    # Ca hôm nay (bản chụp đã chốt): huỷ đúng một lần.
    nay = await _bc_ngay(pool, ql, cs, hom_nay, hom_nay, ca=ma)
    assert nay["chot"]["id"] == chot_nay["id"] and nay["tong"]["huy"] == 300_000
    # Cộng hai ca = cả khoảng hai ngày: huỷ 1 lần, không 2.
    ca_ca = await _bc_ngay(pool, ql, cs, hom_qua, hom_nay)
    assert ca_ca["tong"]["huy"] == 300_000
    assert qua["tong"]["huy"] + nay["tong"]["huy"] == ca_ca["tong"]["huy"]
    # Chốt lại ca hôm qua → bản chụp mới KHÔNG trừ phiếu ấy.
    await svc.chot(identity=ql, ngay=hom_qua.isoformat(), ca=ma, co_so=cs)
    qua2 = await _bc_ngay(pool, ql, cs, hom_qua, hom_qua, ca=ma)
    assert qua2["tong"]["huy"] == 0 and qua2["chot"] is not None
    assert qua2["sau_chot"]["huy"] == 0


async def test_huy_trong_luc_ca_dang_mo_khoa_ve_ca_goc(pool: asyncpg.Pool) -> None:  # noqa: F811
    """Huỷ xảy ra LÚC ca đang mở khoá thì thuộc ca gốc (như chưa từng chốt)."""
    ca = await _dung(pool)
    ql = _ql(ca)
    cs = await _co_so_rieng(pool)
    ma = await _ca_bay_gio(pool)
    hom_nay = now_vn().date()
    hom_qua = hom_nay - timedelta(days=1)
    v = await _luot_o(pool, ca, cs)
    await _lui_gio_thu(pool, v, 1)
    svc = ChotSoCaService(pool)
    chot = await svc.chot(identity=ql, ngay=hom_qua.isoformat(), ca=ma, co_so=cs)
    await svc.mo_khoa(identity=ql, chot_id=chot["id"], ly_do="Cần sửa sổ hôm qua")
    await _huy_phieu(pool, ca, v)  # huỷ khi ca hôm qua ĐANG MỞ KHOÁ
    qua = await _bc_ngay(pool, ql, cs, hom_qua, hom_qua, ca=ma)
    assert (qua["tong"]["thu"], qua["tong"]["huy"]) == (300_000, 300_000)
    nay = await _bc_ngay(pool, ql, cs, hom_nay, hom_nay, ca=ma)
    assert nay["tong"]["huy"] == 0 and nay["dieu_chinh_ca_truoc"]["so_phieu"] == 0
