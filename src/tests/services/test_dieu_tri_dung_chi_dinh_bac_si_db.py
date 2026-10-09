"""Lượt Điều trị DÙNG LUÔN chỉ định bác sĩ đã kê + phiếu điều trị là KẾT QUẢ
(Tuyền chốt 09/10/2026), trên Postgres thật.

    scripts/test-nhanh.sh src/tests/services/test_dieu_tri_dung_chi_dinh_bac_si_db.py

Staging 09/10 (khách ec698aca): lượt Sản khoa kê Ghế điện, khách chưa làm; lễ
tân đặt lượt Điều trị cùng dịch vụ, check-in → chỉ định THỨ HAI ở lượt mới, phòng
điền vào đó, thẻ ở lượt khám vẫn "chưa làm", nguy cơ thu hai lần. Nay: một chỉ
định, ở lượt Điều trị, thu một lần; lượt khám thấy "đã chuyển sang" + kết quả;
hoàn tác check-in trả chỉ định về đúng chỗ.
"""

from __future__ import annotations

import json

import asyncpg
import pytest

from clinicai.events.catalogue import DIEU_TRI_SINH_CHI_DINH
from clinicai.phieu_kham.ket_qua_chi_dinh import doc_ket_qua_theo_chi_dinh
from clinicai.phieu_kham.mau_dieu_tri import phieu_co_ket_qua, phieu_co_ket_qua_sql
from clinicai.services.bill_service import hoa_don_con_no
from clinicai.services.booking_service import BookingService
from clinicai.services.form_engine_service import FormEngineService
from clinicai.services.hang_cho import vao_hang
from tests.chay_nguoi_dua_tin import chay_hanh_trinh, chay_het
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_dieu_tri_ban_kham_db import (
    _don_dat_san,
    _ke,
    _laser,
    _the,
    _vao_kham,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    Ca,
    _benh_nhan,
    _check_in,
    _chon,
    _don,
    _dong_luot,
    _dung,
    _su_kien,
    _thu,
    _thu_khoi_dieu_phoi,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _bac_si_ke(pool: asyncpg.Pool) -> tuple[Ca, asyncpg.Record, str, str, str]:  # noqa: F811
    """Lượt KHÁM: bác sĩ kê dịch vụ điều trị (Laser), khách chưa làm, chưa thu."""
    ca = await _dung(pool)
    laser = await _laser(pool)
    pid = await _benh_nhan(pool, ca)
    kham = await _check_in(pool, ca, pid, ca.loai_kham)
    con = await _vao_kham(pool, ca, kham)
    order = str((await _ke(pool, ca, con, laser["ma"]))["order_ids"][0])
    return ca, laser, pid, kham, order


async def _dieu_tri(pool: asyncpg.Pool, ca: Ca, pid: str, laser: asyncpg.Record) -> str:  # noqa: F811
    """Lễ tân check-in lượt Điều trị cùng dịch vụ; mọi bên nghe chạy xong."""
    dt = await _check_in(pool, ca, pid, laser["loai"])
    await chay_het(pool, DIEU_TRI_SINH_CHI_DINH)
    return dt


async def _chi_dinh_cua_khach(
    pool: asyncpg.Pool,  # noqa: F811
    pid: str,
    ma: str,
) -> list[tuple[str, str]]:
    return [
        (r["id"], r["visit_id"])
        for r in await pool.fetch(
            "SELECT o.id::text AS id, o.visit_id::text AS visit_id"
            "  FROM service_order o JOIN visit v ON v.visit_id = o.visit_id"
            " WHERE v.clinic_patient_id = $1::uuid AND o.service_code = $2"
            "   AND o.exec_status <> 'cancelled' ORDER BY o.created_at",
            pid,
            ma,
        )
    ]


async def _the_cls(pool: asyncpg.Pool, visit: str, order: str) -> dict:  # noqa: F811
    async with pool.acquire() as conn:
        ds = await doc_ket_qua_theo_chi_dinh(conn, clinic_id=CLINIC, visit_id=visit)
    [c] = [x for x in ds if x["service_order_id"] == order]
    return c


async def _dong_hoa_don(pool: asyncpg.Pool, visit: str) -> list[str]:  # noqa: F811
    async with pool.acquire() as conn:
        hd = await hoa_don_con_no(conn, clinic_id=CLINIC, visit_id=visit)
    return [d.source_id for d in hd.dong if d.source_type == "service_order"]


async def test_cung_ngay_luot_kham_con_mo_mot_chi_dinh_thu_mot_lan_ket_qua_ve_the(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca, laser, pid, kham, order = await _bac_si_ke(pool)
    lan = await pool.fetchval(
        "SELECT lan_chi_dinh FROM service_order WHERE id = $1::uuid", order
    )
    dt = await _dieu_tri(pool, ca, pid, laser)

    # MỘT chỉ định — chính cái bác sĩ kê — nay ở lượt Điều trị.
    assert await _chi_dinh_cua_khach(pool, pid, laser["ma"]) == [(order, dt)]
    d = await _don(pool, order)
    assert d["mang_tu"] == kham
    [mang] = await _su_kien(pool, "service_order.carried_over", order)
    p = json.loads(mang["payload"])
    assert p["da_thu_tien"] is False and p["lan_chi_dinh"] == lan

    # Thẻ ở lượt Điều trị (khối 1) là chỉ định ấy; đặt lịch đúng dịch vụ.
    assert (await _the(pool, ca, dt))["order_id"] == order

    # Quầy: lượt Điều trị thu ĐÚNG một dòng; lượt khám không còn dòng ấy.
    await _chon(pool, ca, dt, [order])
    assert await _dong_hoa_don(pool, dt) == [order]
    assert order not in await _dong_hoa_don(pool, kham)

    # Lượt khám cũ: thẻ còn đó, chỉ đọc, "đã chuyển sang lượt Điều trị".
    cu = await _the_cls(pool, kham, order)
    assert cu["chuyen_sang"]["visit_id"] == dt
    assert cu["chuyen_sang"]["ten_luot"] == "Điều trị"
    assert cu["chuyen_sang"]["luc"] is not None
    assert cu["mang_sang"] is False and cu["lan"] == lan
    moi = await _the_cls(pool, dt, order)
    assert moi["chuyen_sang"] is None and moi["mang_sang"] is True

    # Phòng điền phiếu điều trị → kết quả hiện ở CẢ thẻ lượt khám (như CLS).
    fe = FormEngineService(pool)
    ph = await fe.mo_phieu(
        service_order_id=order, form_id="KQ_PHIEU_DIEU_TRI", identity=ca.dd
    )
    await fe.luu_nhap(
        phieu_id=ph["id"],
        du_lieu={"cam_nhan": {"gia_tri": "Đỡ đau lưng", "nguon": "USER"}},
        expected_revision=int(ph["revision"]),
        identity=ca.dd,
    )
    cu = await _the_cls(pool, kham, order)
    assert cu["ket_qua_trang_thai"] == "CO_KET_QUA"
    [k] = [x for x in cu["ket_qua"] if x["loai"] == "PHIEU"]
    assert k["co_ket_qua"] and k["du_lieu"]["cam_nhan"]["gia_tri"] == "Đỡ đau lưng"
    assert k["nguoi_ghi"] and k["ghi_luc"]


async def test_luot_kham_da_check_out_chua_thu_van_dung_chi_dinh_cu(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca, laser, pid, kham, order = await _bac_si_ke(pool)
    await _dong_luot(pool, kham)  # khách về, hẹn hôm khác làm
    dt = await _dieu_tri(pool, ca, pid, laser)
    assert await _chi_dinh_cua_khach(pool, pid, laser["ma"]) == [(order, dt)]
    await _chon(pool, ca, dt, [order])
    assert await _dong_hoa_don(pool, dt) == [order]


async def test_da_thu_o_luot_kham_mang_theo_luat_cu_khong_thu_lai(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca, laser, pid, kham, order = await _bac_si_ke(pool)
    await _chon(pool, ca, kham, [order])
    await _thu_khoi_dieu_phoi(pool, ca.thu_ngan)  # người thu không tự xếp phòng
    await _thu(pool, kham, ca.thu_ngan)
    await chay_hanh_trinh(pool)
    await _dong_luot(pool, kham)
    dt = await _dieu_tri(pool, ca, pid, laser)

    assert await _chi_dinh_cua_khach(pool, pid, laser["ma"]) == [(order, dt)]
    [mang] = await _su_kien(pool, "service_order.carried_over", order)
    assert json.loads(mang["payload"])["da_thu_tien"] is True
    assert order not in await _dong_hoa_don(pool, dt)  # không thu lại


async def test_da_xep_phong_o_luot_kham_khong_mang_khong_de_chi_dinh_thu_hai(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Chỉ định đã vào hàng phòng ở lượt khám còn mở: khách làm ở đó — không
    kéo đi, và lượt Điều trị KHÔNG đẻ cái thứ hai (thu hai lần)."""
    ca, laser, pid, kham, order = await _bac_si_ke(pool)
    async with pool.acquire() as conn:
        await vao_hang(
            conn,
            clinic_id=CLINIC,
            visit_id=kham,
            lane="ROOM",
            reason="SERVICE",
            ref_id=order,
            room_id=ca.phong,
        )
    dt = await _dieu_tri(pool, ca, pid, laser)
    assert await _chi_dinh_cua_khach(pool, pid, laser["ma"]) == [(order, kham)]
    assert dt != kham


async def test_hoan_tac_check_in_luot_dieu_tri_tra_chi_dinh_ve_luot_kham(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca, laser, pid, kham, order = await _bac_si_ke(pool)
    lan = await pool.fetchval(
        "SELECT lan_chi_dinh FROM service_order WHERE id = $1::uuid", order
    )
    dt = await _dieu_tri(pool, ca, pid, laser)
    appt = str(
        await pool.fetchval(
            "SELECT appointment_id::text FROM visit WHERE visit_id = $1::uuid", dt
        )
    )
    await BookingService(pool).apply_action(
        appointment_id=appt, action="undo_checkin", identity=ca.le_tan
    )

    d = await _don(pool, order)
    assert d["visit_id"] == kham and d["mang_tu"] is None
    assert (
        await pool.fetchval(
            "SELECT lan_chi_dinh FROM service_order WHERE id = $1::uuid", order
        )
        == lan
    )
    [tra] = await _su_kien(pool, "service_order.carry_returned", order)
    assert json.loads(tra["payload"])["tu_visit_id"] == dt
    assert tra["ai"] == ca.le_tan.staff_id
    cu = await _the_cls(pool, kham, order)
    assert cu["chuyen_sang"] is None and cu["mang_sang"] is False

    # Check-in lại → lượt Điều trị dùng lại đúng chỉ định ấy, vẫn một dòng.
    await BookingService(pool).apply_action(
        appointment_id=appt, action="checkin", identity=ca.le_tan
    )
    await chay_hanh_trinh(pool)
    await chay_het(pool, DIEU_TRI_SINH_CHI_DINH)
    assert await _chi_dinh_cua_khach(pool, pid, laser["ma"]) == [(order, dt)]


async def test_phieu_dieu_tri_co_chu_moi_la_ket_qua_mot_luat_python_va_sql(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    laser = await _laser(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), laser["loai"])
    order = await _don_dat_san(pool, visit)
    fe = FormEngineService(pool)
    ph = await fe.mo_phieu(
        service_order_id=order, form_id="KQ_PHIEU_DIEU_TRI", identity=ca.dd
    )

    async def _hai_luat() -> tuple[bool, bool]:
        r = await pool.fetchrow(
            "SELECT f.form_id, f.trang_thai, f.revision, f.du_lieu,"
            f"      {phieu_co_ket_qua_sql('f')} AS sql_co"
            "  FROM form_instance f WHERE f.id = $1::uuid",
            ph["id"],
        )
        py = phieu_co_ket_qua(
            form_id=r["form_id"],
            trang_thai=r["trang_thai"],
            revision=r["revision"],
            du_lieu=r["du_lieu"],
        )
        return py, bool(r["sql_co"])

    # Mở mà chưa ai lưu → chưa có kết quả (cả hai luật).
    assert await _hai_luat() == (False, False)
    assert (await _the_cls(pool, visit, order))["ket_qua_trang_thai"] != "CO_KET_QUA"

    # Lưu toàn dấu cách / xuống dòng → vẫn chưa.
    rong = await fe.luu_nhap(
        phieu_id=ph["id"],
        du_lieu={"cam_nhan": {"gia_tri": "  \n\t ", "nguon": "USER"}},
        expected_revision=int(ph["revision"]),
        identity=ca.dd,
    )
    assert await _hai_luat() == (False, False)
    t = await _the(pool, ca, visit)
    assert t["phieu"]["co_ket_qua"] is False

    # Có chữ → CÓ KẾT QUẢ ở mọi nơi đọc, dù phiếu còn DRAFT.
    await fe.luu_nhap(
        phieu_id=ph["id"],
        du_lieu={"van_de_sau": {"gia_tri": "Hơi rát", "nguon": "USER"}},
        expected_revision=int(rong["revision"]),
        identity=ca.dd,
    )
    assert await _hai_luat() == (True, True)
    c = await _the_cls(pool, visit, order)
    assert c["ket_qua_trang_thai"] == "CO_KET_QUA"
    [k] = [x for x in c["ket_qua"] if x["loai"] == "PHIEU"]
    assert k["trang_thai"] == "DRAFT" and k["co_ket_qua"] is True
    t = await _the(pool, ca, visit)
    assert t["phieu"]["co_ket_qua"] is True

    # Bác sĩ mở thẻ = ĐÃ XEM (như kết quả CLS).
    xem = await fe.xem_ket_qua(service_order_id=order, identity=ca.bac_si)
    assert [p["id"] for p in xem["phieu"]] == [ph["id"]]
    assert await pool.fetchval(
        "SELECT da_xem_ket_qua_luc IS NOT NULL FROM service_order WHERE id = $1::uuid",
        order,
    )
