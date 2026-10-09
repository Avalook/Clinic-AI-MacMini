"""Nhãn đếm LƯỢT (Tuyền chốt 08/10/2026) — một luật cho mọi màn.

    scripts/test-nhanh.sh src/tests/services/test_nhan_luot_db.py

Mỗi lần check-in = MỘT lượt khám, đếm theo thời gian trên TOÀN BỘ lượt của
khách; điều trị đếm theo buổi (không ăn số lượt khám); lịch chưa tới "Lịch hẹn";
huỷ "Đã huỷ". Ca có thật: hai lượt cùng ngày trước đây đều là "Lần đầu".
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import asyncpg
import pytest

from clinicai.services import lich_su_luot
from clinicai.services.man_khach_hang_service import ManKhachHangService
from clinicai.services.nhan_luot import doc_nhan_luot, gan_nhan, tra_nhan
from tests.services.test_lieu_trinh_db import LT, chi_dinh, dung_ca, luot, tao
from tests.services.test_luot_kham_service_db import CLINIC

pytest_plugins = ["tests.services.test_luot_kham_service_db"]

T0 = datetime(2026, 10, 1, 2, 0, tzinfo=UTC)


def _m(khoa: str, gio: int, **kw: Any) -> dict[str, Any]:
    d: dict[str, Any] = {
        "khoa": khoa,
        "moc": T0 + timedelta(hours=gio),
        "da_check_in": True,
        "trang_thai_lich": "COMPLETED",
        "nhom": "KHAM",
        "buoi": None,
    }
    d.update(kw)
    return d


def test_gan_nhan_thuan_dem_theo_thoi_gian_toan_khach() -> None:
    nhan = gan_nhan(
        [
            # Thứ tự đưa vào lộn xộn — đếm theo mốc, không theo thứ tự danh sách.
            _m("kham-chieu", 7),
            _m("dieu-tri", 3, nhom="DIEU_TRI", buoi=(2, 10, True)),
            _m("kham-sang", 1),
            _m("huy", 2, da_check_in=False, trang_thai_lich="CANCELLED"),
            _m("khong-den", 2, da_check_in=False, trang_thai_lich="NO_SHOW"),
            _m("bs-tu-choi", 2, da_check_in=False, trang_thai_lich="DOCTOR_DECLINED"),
            _m("le", 4, nhom="DIEU_TRI"),
            _m("khac", 5, nhom="KHAC"),
            _m("chua-ro", 6, nhom=None, buoi=(1, 5, False)),
            _m("thuoc", 6, nhom="THUOC"),
            _m("sap-toi", 48, da_check_in=False, trang_thai_lich="CONFIRMED"),
        ]
    )
    assert nhan["kham-sang"]["nhan"] == "Lượt khám 1"
    assert nhan["khac"]["nhan"] == "Lượt khám 2"
    assert nhan["chua-ro"]["nhan"] == "Lượt khám 3"
    assert nhan["chua-ro"]["buoi"] == "Buổi 1/5 · chưa làm"  # lượt khám: chip phụ
    assert nhan["kham-chieu"]["nhan"] == "Lượt khám 4"
    assert nhan["kham-chieu"]["so"] == 4
    assert nhan["dieu-tri"] == {
        "nhan": "Buổi 2/10 · đã làm",
        "loai": "DIEU_TRI",
        "so": None,
        "buoi": "Buổi 2/10 · đã làm",
    }
    assert nhan["le"]["nhan"] == "Điều trị · buổi lẻ"
    assert nhan["thuoc"]["nhan"] == "Mua thuốc"
    assert nhan["huy"]["nhan"] == "Đã huỷ" and nhan["huy"]["so"] is None
    assert nhan["bs-tu-choi"]["nhan"] == "Đã huỷ"
    assert nhan["khong-den"]["nhan"] == "Không đến"
    assert nhan["sap-toi"]["nhan"] == "Lịch hẹn"


def test_gan_nhan_dau_vao_rac_khong_nem() -> None:
    assert gan_nhan([]) == {}
    # Thiếu khoá → bỏ; mốc rác → xếp đầu, không ném.
    nhan = gan_nhan([{"moc": "rác", "da_check_in": True}, _m("a", 1), {"khoa": "b"}])
    assert nhan["a"]["nhan"] == "Lượt khám 1"
    assert nhan["b"]["nhan"] == "Lịch hẹn"
    nhan = gan_nhan([_m("x", 1, moc=None), _m("y", 0)])
    assert nhan["x"]["nhan"] == "Lượt khám 1"
    # Mốc trùng nhau (hai lượt cùng giờ) → vẫn hai số khác nhau, ổn định.
    nhan = gan_nhan([_m("p", 1), _m("q", 1)])
    assert {nhan["p"]["so"], nhan["q"]["so"]} == {1, 2}
    assert tra_nhan({}, visit_id="x", appointment_id=None) is None


async def _st_kham(pool: asyncpg.Pool) -> str:
    return str(
        await pool.fetchval(
            "SELECT id::text FROM service_type WHERE clinic_id = $1::uuid"
            " AND nhom = 'KHAM' ORDER BY created_at, id LIMIT 1",
            CLINIC,
        )
    )


async def _lich(
    ca: LT,
    st: str,
    luc: datetime,
    status: str,
    *,
    vao: datetime | None = None,
) -> tuple[str, str | None]:
    """Một lịch (+ lượt check-in lúc ``vao`` nếu có)."""
    appt = str(
        await ca.pool.fetchval(
            "INSERT INTO appointment (clinic_id, clinic_patient_id, location_id,"
            " service_type_id, slot_start, slot_end, status, ly_do_huy_ma)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5, $6, $7, $8)"
            " RETURNING id::text",
            CLINIC,
            ca.khach,
            ca.loc,
            st,
            luc,
            luc + timedelta(minutes=15),
            status,
            "BAO_KHI_XAC_NHAN" if status == "CANCELLED" else None,
        )
    )
    if vao is None:
        return appt, None
    visit = str(
        await ca.pool.fetchval(
            "INSERT INTO visit (clinic_id, clinic_patient_id, appointment_id,"
            " location_id, service_type_id, status, checked_in_at,"
            " exam_completed_at, closed_at)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5::uuid,"
            " 'IN_PROGRESS', $6, $7, $8) RETURNING visit_id::text",
            CLINIC,
            ca.khach,
            appt,
            ca.loc,
            st,
            vao,
            vao + timedelta(minutes=80),
            vao + timedelta(minutes=100),
        )
    )
    return appt, visit


@pytest.mark.db
@pytest.mark.asyncio
async def test_hai_luot_cung_ngay_dieu_tri_xen_giua_lich_huy(
    pool: asyncpg.Pool,
) -> None:
    """Khách: lượt khám 10 ngày trước · buổi liệu trình 5 ngày trước · HAI lượt
    khám hôm qua (cùng ngày, hai dịch vụ) · lịch huỷ · lịch hoàn tác check-in ·
    lịch tuần sau → "Lượt khám 1, 2, 3" + "Buổi 1/10" + "Đã huỷ" + "Lịch hẹn";
    màn khách hàng và popup Lịch sử khám cùng một nhãn; giờ thật đi kèm."""
    ca = await dung_ca(pool)
    st = await _st_kham(pool)
    bay_gio = datetime.now(UTC).replace(microsecond=0)
    hom_qua = bay_gio - timedelta(days=1)

    a1, v1 = await _lich(
        ca,
        st,
        bay_gio - timedelta(days=10),
        "COMPLETED",
        vao=bay_gio - timedelta(days=10),
    )
    # Buổi liệu trình (lượt Điều trị không lịch hẹn) 5 ngày trước.
    vdt = await luot(ca, dieu_tri=True, ngay_truoc=5)
    o = await chi_dinh(ca, vdt)
    await tao(ca, vdt, 10, order=o)
    # Hai lượt khám CÙNG NGÀY: giờ hẹn 20:30 (slot ảo) nhưng tới sáng.
    a3, v3 = await _lich(
        ca, st, hom_qua + timedelta(hours=11), "COMPLETED", vao=hom_qua
    )
    a4, v4 = await _lich(
        ca,
        st,
        hom_qua + timedelta(hours=3),
        "COMPLETED",
        vao=hom_qua + timedelta(hours=2),
    )
    a5, _ = await _lich(ca, st, hom_qua, "CANCELLED")
    # Hoàn tác check-in: lịch về CONFIRMED, lượt còn dòng → không đếm.
    a6, v6 = await _lich(
        ca,
        st,
        bay_gio - timedelta(days=2),
        "CONFIRMED",
        vao=bay_gio - timedelta(days=2),
    )
    a7, _ = await _lich(ca, st, bay_gio + timedelta(days=7), "CONFIRMED")

    async with pool.acquire() as conn:
        nhan = await doc_nhan_luot(conn, CLINIC, [ca.khach])

    def chu(**kw: Any) -> str:
        n = tra_nhan(nhan, **kw)
        assert n is not None, kw
        return str(n["nhan"])

    assert chu(appointment_id=a1) == chu(visit_id=v1) == "Lượt khám 1"
    assert chu(visit_id=vdt) == "Buổi 1/10 · chưa làm"
    assert chu(appointment_id=a3) == "Lượt khám 2"
    assert chu(visit_id=v4) == "Lượt khám 3"
    assert chu(appointment_id=a5) == "Đã huỷ"
    assert chu(appointment_id=a6) == chu(visit_id=v6) == "Lịch hẹn"
    assert chu(appointment_id=a7) == "Lịch hẹn"

    # Màn Quản lý khách hàng: mỗi lịch mang nhãn + giờ THẬT của lượt.
    goi = await ManKhachHangService(pool).goi_du_lieu(clinic_id=CLINIC, ids=[ca.khach])
    theo = {str(a["id"]): a for a in goi["appts"]}
    assert theo[a3]["nhan_luot"]["nhan"] == "Lượt khám 2"
    assert theo[a4]["nhan_luot"]["nhan"] == "Lượt khám 3"
    assert theo[a5]["nhan_luot"]["nhan"] == "Đã huỷ"
    assert theo[a7]["nhan_luot"]["nhan"] == "Lịch hẹn"
    assert theo[a3]["den_luc"] is not None
    assert theo[a3]["kham_xong_luc"] is not None and theo[a3]["ve_luc"] is not None
    assert theo[a7]["den_luc"] is None

    # Popup Lịch sử khám: cùng nhãn cho cùng lượt.
    async with pool.acquire() as conn:
        ls = await lich_su_luot.doc(conn, clinic_id=CLINIC, clinic_patient_id=ca.khach)
    theo_luot = {x["visit_id"]: x for x in ls["luot"]}
    assert theo_luot[v3]["nhan_luot"]["nhan"] == "Lượt khám 2"
    assert theo_luot[vdt]["nhan_luot"]["nhan"] == "Buổi 1/10 · chưa làm"
