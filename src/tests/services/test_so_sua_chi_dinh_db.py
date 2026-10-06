"""SỔ SỬA / BỎ CHỈ ĐỊNH (Khối 2, Tuyền chốt 06/10/2026).

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55600/postgres \\
        .venv/bin/pytest src/tests/services/test_so_sua_chi_dinh_db.py

Trưởng ca bỏ tích một chỉ định siêu âm đã thu tiền → có hiệu lực ngay, quầy thấy
tiền thừa, bác sĩ chính nhận thông báo (nút DUY NHẤT là Hoàn tác), sổ ghi đủ
cột. Bác sĩ chính bấm Hoàn tác → chỉ định quay lại, sổ thêm dòng. Bỏ một thuốc
trong đơn rồi lưu → sổ có dòng "bỏ thuốc". Lượt hồ sơ cũ chỉ xem.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import NotFoundError, ValidationError
from clinicai.api.identity import ClinicRole
from clinicai.core.exceptions import SafetyGateError
from clinicai.services.cashier_board_service import CashierBoardService
from clinicai.services.dinh_chinh_don import luu_don_chua_ky
from clinicai.services.hoan_tac_service import HoanTacService, tien_thua_cua_luot
from clinicai.services.lenh_kham_core import (
    LuotKhamConflictError,
    LuotKhamValidationError,
)
from clinicai.services.phi_kham_service import PhiKhamService
from clinicai.services.so_sua_chi_dinh_service import SoSuaChiDinhService
from clinicai.services.thong_bao_service import ThongBaoService
from tests.chay_nguoi_dua_tin import chay_hanh_trinh
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    _nguoi,
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    Ca,
    _benh_nhan,
    _check_in,
    _chon,
    _don,
    _dung,
    _kham_va_chi_dinh,
    _thu,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _so(pool: asyncpg.Pool, visit: str) -> list[asyncpg.Record]:  # noqa: F811
    return list(
        await pool.fetch(
            "SELECT * FROM so_sua_chi_dinh WHERE visit_id = $1::uuid ORDER BY stt",
            visit,
        )
    )


async def _bat_bien(pool: asyncpg.Pool, visit: str) -> list[asyncpg.Record]:  # noqa: F811
    return [
        r
        for r in await pool.fetch(
            "SELECT * FROM bat_bien_tien_chi_dinh($1::uuid, $2)",
            CLINIC,
            datetime.now(UTC) - timedelta(hours=1),
        )
        if str(r["visit_id"]) == visit
    ]


def _ct(r: asyncpg.Record) -> dict[str, Any]:
    ct = r["chi_tiet"]
    return dict(ct) if isinstance(ct, dict) else json.loads(ct)


async def _da_thu_xep_phong(pool: asyncpg.Pool) -> tuple[Ca, str, str]:  # noqa: F811
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    _con, order = await _kham_va_chi_dinh(pool, ca, visit)
    await _chon(pool, ca, visit, [order])
    await _thu(pool, visit, ca.thu_ngan)
    await chay_hanh_trinh(pool)
    return ca, visit, order


async def test_truong_ca_bo_cls_da_thu_bac_si_chinh_hoan_tac(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca, visit, order = await _da_thu_xep_phong(pool)
    async with pool.acquire() as conn:
        tc = await _nguoi(conn, ca.loc, "TRUONG_CA")

    # Lúc chỉ định: sổ có dòng THÊM của bác sĩ.
    [them] = await _so(pool, visit)
    assert (them["hanh_dong"], them["nhom"], them["boi_staff_id"]) == (
        "THEM",
        "CLS",
        uuid.UUID(ca.bac_si.staff_id),
    )

    # Trưởng ca bỏ — có hiệu lực NGAY (không chờ ai duyệt).
    kq = await HoanTacService(pool).huy_chi_dinh(
        order_id=order, identity=tc, xac_nhan=True, ly_do="Khách đổi ý siêu âm"
    )
    assert kq["tien_thua"] == 300000 and kq["da_bao_bac_si_chinh"] is True
    assert (await _don(pool, order))["exec_status"] == "cancelled"

    # Sổ đủ cột: ai + vai, bàn bác sĩ nào, ai chỉ định gốc, tiền, lý do, báo lúc nào.
    bo = (await _so(pool, visit))[-1]
    assert bo["hanh_dong"] == "BO" and bo["nhom"] == "CLS"
    assert str(bo["id"]) == kq["so_sua_id"]
    assert (bo["boi_ten"], bo["boi_vai"]) == (tc.full_name, "TRUONG_CA")
    assert bo["bac_si_chinh_id"] == uuid.UUID(ca.bac_si.staff_id)
    assert bo["bac_si_chinh_ten"] == ca.bac_si.full_name
    assert bo["chi_dinh_goc_boi_ten"] == ca.bac_si.full_name
    assert (bo["da_thu"], bo["tien_thua"]) == (300000, 300000)
    assert bo["ly_do"] == "Khách đổi ý siêu âm"
    assert bo["da_bao_bac_si_luc"] is not None and bo["thong_bao_id"] is not None
    assert bo["luc"] is not None and bo["hoan_tac_luc"] is None

    # Quầy thu thấy tiền thừa; bất biến tiền vẫn khớp.
    bang = await CashierBoardService(pool).board(
        identity=ca.thu_ngan, modes=["dich_vu"]
    )
    [item] = [i for i in bang["items"] if i["visit_id"] == visit]
    assert item["tien_thua"]["tong"] == 300000
    assert await _bat_bien(pool, visit) == []

    # Bác sĩ chính nhận thông báo — chỉ có Hoàn tác, không đóng bằng "Xong".
    ds = await ThongBaoService(pool).cua_toi(identity=ca.bac_si)
    [tb] = [t for t in ds if t["hoan_tac_so_id"] == kq["so_sua_id"]]
    assert tb["nguon"] == "bo_chi_dinh"
    assert tc.full_name in tb["noi_dung"] and "300.000đ" in tb["noi_dung"]
    with pytest.raises(ValidationError):
        await ThongBaoService(pool).da_xu_ly(
            identity=ca.bac_si, thong_bao_id=str(tb["id"]), ghi_chu=None
        )
    # Trưởng ca (người bỏ) không tự nhận thông báo.
    assert not [
        t
        for t in await ThongBaoService(pool).cua_toi(identity=tc)
        if t["hoan_tac_so_id"] == kq["so_sua_id"]
    ]

    # Lịch sử của lượt: dòng BỎ hoàn tác được.
    doc = await SoSuaChiDinhService(pool).doc(visit_id=visit, identity=ca.le_tan)
    assert doc["chi_xem"] is False
    assert doc["dong"][0]["hanh_dong"] == "BO" and doc["dong"][0]["hoan_tac_duoc"]
    assert "tiền thừa 300.000đ" in doc["dong"][0]["cau"]

    # Bác sĩ chính bấm Hoàn tác → chỉ định quay lại, sổ thêm dòng.
    lai = await SoSuaChiDinhService(pool).hoan_tac(
        so_id=kq["so_sua_id"], identity=ca.bac_si
    )
    assert lai["ok"] is True and not lai.get("already")
    d = await _don(pool, order)
    assert d["exec_status"] == "authorized" and d["selection_status"] == "SELECTED"
    so = await _so(pool, visit)
    assert so[-1]["hanh_dong"] == "HOAN_TAC"
    assert so[-1]["hoan_tac_cua"] == bo["id"]
    assert so[-1]["boi_staff_id"] == uuid.UUID(ca.bac_si.staff_id)
    bo2 = next(r for r in so if r["id"] == bo["id"])
    assert bo2["hoan_tac_boi_ten"] == ca.bac_si.full_name
    assert bo2["hoan_tac_luc"] is not None
    # Thông báo đóng; tiền thừa hết; bất biến khớp; khách được xếp phòng lại.
    assert not [
        t
        for t in await ThongBaoService(pool).cua_toi(identity=ca.bac_si)
        if str(t["id"]) == str(tb["id"])
    ]
    async with pool.acquire() as conn:
        assert visit not in await tien_thua_cua_luot(conn, CLINIC, [visit])
    assert await _bat_bien(pool, visit) == []
    await chay_hanh_trinh(pool)
    assert (await _don(pool, order))["routing_status"] == "ASSIGNED"

    # Bấm lần hai (máy khác): không làm gì thêm.
    lai2 = await SoSuaChiDinhService(pool).hoan_tac(
        so_id=kq["so_sua_id"], identity=ca.bac_si
    )
    assert lai2["already"] is True
    assert len(await _so(pool, visit)) == len(so)
    doc = await SoSuaChiDinhService(pool).doc(visit_id=visit, identity=ca.bac_si)
    assert not any(x["hoan_tac_duoc"] for x in doc["dong"])

    # Bỏ lại lần nữa được (không khoá), sổ ghi tiếp.
    await HoanTacService(pool).huy_chi_dinh(
        order_id=order, identity=tc, xac_nhan=True, ly_do="Bỏ lần hai"
    )
    assert (await _so(pool, visit))[-1]["hanh_dong"] == "BO"


async def test_bac_si_chinh_tu_bo_khong_bao(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    _con, order = await _kham_va_chi_dinh(pool, ca, visit)
    kq = await HoanTacService(pool).huy_chi_dinh(order_id=order, identity=ca.bac_si)
    assert kq["da_bao_bac_si_chinh"] is False
    bo = (await _so(pool, visit))[-1]
    assert (bo["hanh_dong"], bo["da_thu"], bo["tien_thua"]) == ("BO", 0, 0)
    assert bo["da_bao_bac_si_luc"] is None
    # Bác sĩ chính tự hoàn tác từ Lịch sử sửa cũng được.
    await SoSuaChiDinhService(pool).hoan_tac(so_id=str(bo["id"]), identity=ca.bac_si)
    assert (await _don(pool, order))["exec_status"] == "authorized"


async def test_le_tan_khong_co_quyen_chi_dinh_thi_khong_hoan_tac(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    _con, order = await _kham_va_chi_dinh(pool, ca, visit)
    kq = await HoanTacService(pool).huy_chi_dinh(order_id=order, identity=ca.bac_si)
    # Nhân sự chưa được cấp khối nào (không có "Chỉ định dịch vụ").
    async with pool.acquire() as conn:
        sid = await conn.fetchval(
            "INSERT INTO staff (full_name, primary_department, primary_location_id,"
            " is_active) VALUES ('Chưa cấp quyền', 'CSKH', $1::uuid, true)"
            " RETURNING id::text",
            ca.loc,
        )
        await conn.execute(
            "INSERT INTO clinic_membership (clinic_id, staff_id, role, is_active)"
            " VALUES ($1::uuid, $2::uuid, 'CSKH', true)"
            " ON CONFLICT (clinic_id, staff_id, role) DO NOTHING",
            CLINIC,
            sid,
        )
    ai = dataclasses.replace(
        ca.le_tan, staff_id=sid, role=ClinicRole.CSKH, full_name="Chưa cấp quyền"
    )
    with pytest.raises(SafetyGateError):
        await SoSuaChiDinhService(pool).hoan_tac(so_id=kq["so_sua_id"], identity=ai)
    assert (await _don(pool, order))["exec_status"] == "cancelled"


async def test_dau_vao_rac(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    svc = SoSuaChiDinhService(pool)
    for rac in ("", "abc", "1; DROP TABLE visit", "x" * 500):
        with pytest.raises(ValidationError):
            await svc.hoan_tac(so_id=rac, identity=ca.bac_si)
        with pytest.raises(ValidationError):
            await svc.doc(visit_id=rac, identity=ca.bac_si)
    with pytest.raises(NotFoundError):
        await svc.hoan_tac(so_id=str(uuid.uuid4()), identity=ca.bac_si)
    with pytest.raises(NotFoundError):
        await svc.doc(visit_id=str(uuid.uuid4()), identity=ca.bac_si)
    # Dòng THÊM không phải "bỏ" — không hoàn tác được; lý do rác không làm ném.
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    await _kham_va_chi_dinh(pool, ca, visit)
    [them] = await _so(pool, visit)
    with pytest.raises(LuotKhamValidationError) as e:
        await svc.hoan_tac(so_id=str(them["id"]), identity=ca.bac_si, ly_do=["rác"])
    assert e.value.error_code == "KHONG_HOAN_TAC_DUOC"


async def test_so_khong_xoa_khong_sua(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    await _kham_va_chi_dinh(pool, ca, visit)
    [them] = await _so(pool, visit)
    with pytest.raises(asyncpg.CheckViolationError):
        await pool.execute("DELETE FROM so_sua_chi_dinh WHERE id = $1", them["id"])
    with pytest.raises(asyncpg.CheckViolationError):
        await pool.execute(
            "UPDATE so_sua_chi_dinh SET hanh_dong = 'DOI' WHERE id = $1", them["id"]
        )
    with pytest.raises(asyncpg.CheckViolationError):
        await pool.execute(
            "UPDATE so_sua_chi_dinh SET ten_muc = 'khác' WHERE id = $1", them["id"]
        )


async def test_ho_so_cu_chi_xem(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    visit = await _check_in(pool, ca, pid, ca.loai_kham)
    _con, order = await _kham_va_chi_dinh(pool, ca, visit)
    async with pool.acquire() as conn:
        nhap = await conn.fetchval(
            "INSERT INTO lich_su_notion.lan_nhap (clinic_id, goi) VALUES ($1::uuid,"
            " 'thu') RETURNING id",
            CLINIC,
        )
        nid = uuid.uuid4()
        await conn.execute(
            "INSERT INTO lich_su_notion.luot_kham (notion_id, clinic_id,"
            " clinic_patient_id, lan_nhap_id, ngay_kham, nguon_ngay)"
            " VALUES ($1, $2::uuid, $3::uuid, $4, current_date, 'thu')",
            nid,
            CLINIC,
            pid,
            nhap,
        )
        chuyen = await conn.fetchval(
            "INSERT INTO lich_su_notion.lan_chuyen (clinic_id) VALUES ($1::uuid)"
            " RETURNING id",
            CLINIC,
        )
        await conn.execute(
            "INSERT INTO lich_su_notion.luot_that (notion_id, clinic_id,"
            " lan_chuyen_id, visit_id) VALUES ($1, $2::uuid, $3, $4::uuid)",
            nid,
            CLINIC,
            chuyen,
            visit,
        )
    with pytest.raises(LuotKhamConflictError) as e:
        await HoanTacService(pool).huy_chi_dinh(order_id=order, identity=ca.bac_si)
    assert e.value.error_code == "HO_SO_CU"
    assert (await _don(pool, order))["exec_status"] != "cancelled"
    doc = await SoSuaChiDinhService(pool).doc(visit_id=visit, identity=ca.bac_si)
    assert doc["chi_xem"] is True
    assert not any(x["hoan_tac_duoc"] for x in doc["dong"])
    with pytest.raises(LuotKhamConflictError):
        await _luu_don(
            pool, ca, visit, pid, [{"drug_name": "Thuốc thử", "quantity": "1 hộp"}]
        )


async def _luu_don(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
    visit: str,
    pid: str,
    don: list[dict[str, Any]],
    ai: Any = None,
) -> None:
    ai = ai or ca.bac_si
    async with pool.acquire() as conn, conn.transaction():
        await luu_don_chua_ky(
            conn,
            visit_id=visit,
            clinic_id=CLINIC,
            clinic_patient_id=pid,
            prescriptions=don,
            created_by=ai.staff_id,
            identity=ai,
            ly_do=None,
        )


async def _don_hien_hanh(pool: asyncpg.Pool, visit: str) -> list[dict[str, Any]]:  # noqa: F811
    return [
        {
            "id": str(r["id"]),
            "drug_name": r["drug_name_raw"],
            "quantity": r["quantity"],
            "dosage": r["dosage_instructions"],
            "caution": r["caution"],
        }
        for r in await pool.fetch(
            "SELECT id, drug_name_raw, quantity, dosage_instructions, caution"
            " FROM prescription WHERE visit_id = $1::uuid AND removed_at IS NULL"
            " ORDER BY created_at, id",
            visit,
        )
    ]


async def test_thuoc_so_don_truoc_sau(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    visit = await _check_in(pool, ca, pid, ca.loai_kham)
    a = f"Thuoc A {uuid.uuid4().hex[:5]}"
    b = f"Thuoc B {uuid.uuid4().hex[:5]}"
    await _luu_don(
        pool,
        ca,
        visit,
        pid,
        [
            {"drug_name": a, "quantity": "1 hộp", "dosage": "Sáng 1 viên"},
            {"drug_name": b, "quantity": "2 hộp"},
        ],
    )
    so = [r for r in await _so(pool, visit) if r["nhom"] == "THUOC"]
    assert sorted((r["hanh_dong"], r["ten_muc"]) for r in so) == [
        ("THEM", a),
        ("THEM", b),
    ]
    assert all(r["boi_staff_id"] == uuid.UUID(ca.bac_si.staff_id) for r in so)

    # Lưu lại y nguyên: không thêm dòng sổ.
    don = await _don_hien_hanh(pool, visit)
    await _luu_don(pool, ca, visit, pid, don)
    assert len([r for r in await _so(pool, visit) if r["nhom"] == "THUOC"]) == 2

    # "Bỏ thuốc này" (B) rồi lưu cả đơn → sổ có dòng bỏ thuốc B.
    await _luu_don(pool, ca, visit, pid, [d for d in don if d["drug_name"] == a])
    bo = [
        r
        for r in await _so(pool, visit)
        if r["nhom"] == "THUOC" and r["hanh_dong"] == "BO"
    ]
    assert [r["ten_muc"] for r in bo] == [b]
    doc = await SoSuaChiDinhService(pool).doc(visit_id=visit, identity=ca.bac_si)
    dong_bo = next(x for x in doc["dong"] if x["hanh_dong"] == "BO")
    assert dong_bo["cau"].startswith(f"Bỏ thuốc “{b}”")
    assert dong_bo["hoan_tac_duoc"] is False  # thuốc kê lại ở màn kê đơn

    # Người khác đổi liều A → dòng ĐỔI riêng (không gộp vào dòng THÊM của bác sĩ).
    async with pool.acquire() as conn:
        tk = await _nguoi(conn, ca.loc, "TKYK")
    don = await _don_hien_hanh(pool, visit)
    don[0]["dosage"] = "Sáng 2 viên"
    await _luu_don(pool, ca, visit, pid, don, ai=tk)
    doi = [r for r in await _so(pool, visit) if r["hanh_dong"] == "DOI"]
    assert len(doi) == 1 and doi[0]["ten_muc"] == a
    assert _ct(doi[0])["truoc"]["cach_dung"] == "Sáng 1 viên"
    assert _ct(doi[0])["sau"]["cach_dung"] == "Sáng 2 viên"
    # Cùng người sửa tiếp trong 10 phút: gộp vào dòng ĐỔI đang mở.
    don[0]["dosage"] = "Sáng 3 viên"
    await _luu_don(pool, ca, visit, pid, don, ai=tk)
    doi = [r for r in await _so(pool, visit) if r["hanh_dong"] == "DOI"]
    assert len(doi) == 1
    assert (_ct(doi[0])["truoc"]["cach_dung"], _ct(doi[0])["sau"]["cach_dung"]) == (
        "Sáng 1 viên",
        "Sáng 3 viên",
    )


async def _dich_vu_kham(pool: asyncpg.Pool, visit: str, gia: int) -> str:  # noqa: F811
    async with pool.acquire() as conn:
        st = await conn.fetchval(
            "SELECT coalesce(v.service_type_id, a.service_type_id)::text"
            " FROM visit v LEFT JOIN appointment a ON a.id = v.appointment_id"
            " WHERE v.visit_id = $1::uuid",
            visit,
        )
        ma = f"K{uuid.uuid4().hex[:7]}"
        sp = await conn.fetchval(
            'INSERT INTO service_price (clinic_id, service_code, name, "group",'
            " unit_price, ma_kiotviet) VALUES ($1::uuid, $2, $3, 'dich_vu', $4, $2)"
            " RETURNING id::text",
            CLINIC,
            ma,
            f"Khám thử sổ {ma}",
            gia,
        )
        await conn.execute(
            "INSERT INTO loai_kham_phi (clinic_id, service_type_id, service_price_id)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid)",
            CLINIC,
            st,
            sp,
        )
        return str(sp)


async def test_dich_vu_kham_bo_tick_bao_va_hoan_tac(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    await _kham_va_chi_dinh(pool, ca, visit)
    sp = await _dich_vu_kham(pool, visit, 250000)
    svc = PhiKhamService(pool)
    await svc.chon(visit_id=visit, them_vao=[sp], identity=ca.bac_si)
    them = [r for r in await _so(pool, visit) if r["nhom"] == "KHAM"]
    assert [r["hanh_dong"] for r in them] == ["THEM"]

    async with pool.acquire() as conn:
        tc = await _nguoi(conn, ca.loc, "TRUONG_CA")
    await svc.chon(visit_id=visit, bo_di=[sp], identity=tc)
    bo = [r for r in await _so(pool, visit) if r["nhom"] == "KHAM"][-1]
    assert (bo["hanh_dong"], bo["boi_vai"]) == ("BO", "TRUONG_CA")
    assert bo["da_bao_bac_si_luc"] is not None

    await SoSuaChiDinhService(pool).hoan_tac(so_id=str(bo["id"]), identity=ca.bac_si)
    da_chon = (await svc.doc(visit_id=visit, identity=ca.bac_si))["da_chon"]
    assert sp in da_chon
    cuoi = [r for r in await _so(pool, visit) if r["nhom"] == "KHAM"][-1]
    assert (cuoi["hanh_dong"], cuoi["hoan_tac_cua"]) == ("HOAN_TAC", bo["id"])


async def test_bat_bien_bat_duoc_dong_thu_lac(pool: asyncpg.Pool) -> None:  # noqa: F811
    """Dòng thu trỏ vào chỉ định không tồn tại → bất biến báo LECH_TONG."""
    _ca, visit, order = await _da_thu_xep_phong(pool)
    assert await _bat_bien(pool, visit) == []
    # Ảnh chụp hoá đơn khoá cứng bằng trigger — tắt trigger trong phiên thử
    # để giả một dòng thu lạc (dữ liệu hỏng mà bất biến phải bắt được).
    async with pool.acquire() as conn, conn.transaction():
        await conn.execute("SET LOCAL session_replication_role = replica")
        await conn.execute(
            "UPDATE payment_bill_line SET source_id = $2 WHERE source_type ="
            " 'service_order' AND source_id = $1",
            order,
            str(uuid.uuid4()),
        )
    loi = await _bat_bien(pool, visit)
    assert [r["loai"] for r in loi] == ["LECH_TONG"]


async def test_quan_ly_thay_bac_si_xoa_quay_thay_dong_da_xoa_va_thong_bao_doi_theo(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Kịch bản Tuyền thử thật 06/10: Quản lý thay BS chỉ định 2 mục, xoá 1.

    Quầy thu vẫn thấy dòng đã xoá (ai, thay BS nào, lần mấy); bác sĩ chính nhận
    thông báo nêu đúng người + lần; tick lại chính mục ấy → thông báo cũ đóng
    ("Đã chỉ định lại"), không treo câu cũ. Sổ + thông báo phát NOTIFY.
    """
    from clinicai.core.change_broker import CHANNEL
    from clinicai.services.chi_dinh_service import ChiDinhService

    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    await chay_hanh_trinh(pool)
    con, giu = await _kham_va_chi_dinh(pool, ca, visit)
    async with pool.acquire() as conn:
        ql = await _nguoi(conn, ca.loc, "MANAGEMENT")
    kq = await ChiDinhService(pool).dat_chi_dinh(
        consultation_id=con,
        service_codes=[ca.ma_dv],
        identity=ql,
        idempotency_key=uuid.uuid4().hex,
    )
    assert kq["lan"] == 1, "Quản lý chỉ định thêm (không bấm nút lần mới) = lần 1"
    xoa = str(kq["order_ids"][0])

    tin: list[str] = []

    def nghe(_c: object, _p: object, _ch: object, payload: object) -> None:
        tin.append(str(payload))

    async with pool.acquire() as listener:
        await listener.add_listener(CHANNEL, nghe)
        try:
            bo = await HoanTacService(pool).huy_chi_dinh(
                order_id=xoa, identity=ql, xac_nhan=True, ly_do="Bấm nhầm"
            )
            for _ in range(20):
                if any("so_sua_chi_dinh" in t for t in tin) and any(
                    "thong_bao" in t for t in tin
                ):
                    break
                await asyncio.sleep(0.05)
        finally:
            await listener.remove_listener(CHANNEL, nghe)
    assert any('"so_sua_chi_dinh"' in t for t in tin), tin
    assert any('"thong_bao"' in t for t in tin), tin
    assert bo["da_bao_bac_si_chinh"] is True

    # Quầy thu: dòng đã xoá vẫn thấy, kèm ai xoá (thay BS nào) + lần.
    bang = await CashierBoardService(pool).board(
        identity=ca.thu_ngan, modes=["dich_vu"]
    )
    [item] = [i for i in bang["items"] if i["visit_id"] == visit]
    [d] = item["da_bo_chi_dinh"]
    assert d["order_id"] == xoa and d["lan"] == 1 and d["luc"]
    assert d["cau"].endswith("đã xoá chỉ định này")
    assert ql.full_name in d["cau"] and f"(thay BS {ca.bac_si.full_name})" in d["cau"]
    assert d["ly_do"] == "Bấm nhầm"
    # Dòng còn hiệu lực có nhãn lần.
    dong = {
        x["id"]: x for x in item["quay_thu"]["phong_kham"] if x["loai"] == "chi_dinh"
    }
    assert dong[giu]["lan"] == 1

    # Bác sĩ chính nhận thông báo nêu đúng người + lần.
    [tb] = [
        t
        for t in await ThongBaoService(pool).cua_toi(identity=ca.bac_si)
        if t["hoan_tac_so_id"] == bo["so_sua_id"]
    ]
    assert f"{ql.full_name} đã xoá" in tb["noi_dung"] and "(lần 1)" in tb["noi_dung"]

    # Tick lại chính dịch vụ ấy (chỉ định MỚI) → thông báo cũ đóng ngay.
    await ChiDinhService(pool).dat_chi_dinh(
        consultation_id=con,
        service_codes=[ca.ma_dv],
        identity=ql,
        idempotency_key=uuid.uuid4().hex,
    )
    assert not [
        t
        for t in await ThongBaoService(pool).cua_toi(identity=ca.bac_si)
        if t["hoan_tac_so_id"] == bo["so_sua_id"]
    ]
    assert (
        await pool.fetchval(
            "SELECT ghi_chu_xu_ly FROM thong_bao WHERE nguon = 'bo_chi_dinh'"
            " AND nguon_id = $1",
            bo["so_sua_id"],
        )
        == "Đã chỉ định lại"
    )
