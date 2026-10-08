"""LÀM THÊM TẠI QUẦY — nút "+ Nước tiểu"… ở Tiếp đón / Đo sinh hiệu (Tuyền 01/10/2026).

    scripts/test-nhanh.sh src/tests/services/test_lam_them_tai_quay_db.py

Lễ tân check-in chị Lan, chị muốn làm nước tiểu luôn: lễ tân tick "+ Nước tiểu"
→ có chỉ định ngay (không qua bác sĩ), quầy thu thấy dòng, thu xong phòng làm
thấy khách. Khách khác lễ tân quên tick → người đo sinh hiệu tick. Tick nhầm thì
bỏ tick khi chưa làm. Quản lý thêm / tắt nút.
"""

from __future__ import annotations

import asyncio
import uuid

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.services.chi_dinh_service import ChiDinhService
from clinicai.services.hanh_trinh_khach_service import doc_hanh_trinh_khach
from clinicai.services.lam_them_tai_quay_service import LamThemTaiQuayService
from clinicai.services.luot_kham_service import LuotKhamService
from clinicai.services.service_execution_service import ServiceExecutionService
from clinicai.services.service_selection_service import cho_khach_quyet
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
    _don,
    _dung,
    _khoa,
    _su_kien,
    _thu,
)
from tests.services.test_thu_truoc_lam_truoc_tick_db import day_thu_truoc

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _quan_ly(pool: asyncpg.Pool, ca: Ca) -> StaffIdentity:  # noqa: F811
    async with pool.acquire() as conn:
        return await _nguoi(conn, ca.loc, "MANAGEMENT")


async def _san_sang(pool: asyncpg.Pool, **kw: object) -> tuple[Ca, str]:  # noqa: F811
    """Ca thử + nút làm thêm cho dịch vụ của ca + một khách đã check-in."""
    ca = await _dung(pool)
    ql = await _quan_ly(pool, ca)
    await LamThemTaiQuayService(pool).luu_muc(
        identity=ql, service_code=ca.ma_dv, nhan="Nước tiểu thử", **kw
    )
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    return ca, visit


async def _tick(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
    visit: str,
    chon: bool = True,
    noi: str = "tiep_don",
    ai: StaffIdentity | None = None,
    expected_order_id: str | None = None,
    expected_version: int | None = None,
    expected_state_revision: int | None = None,
    idempotency_key: str | None = None,
) -> dict:  # type: ignore[type-arg]
    if expected_state_revision is None and noi in {"tiep_don", "sinh_hieu"}:
        goi = await _nut(pool, ca, visit, noi=noi)
        tt = goi.get("luot", {}).get(visit, {}).get(ca.ma_dv, {})
        expected_state_revision = int(tt.get("state_revision", 0))
        if expected_order_id is None:
            expected_order_id = tt.get("order_id")
        if expected_version is None:
            expected_version = tt.get("order_version")
    return await LamThemTaiQuayService(pool).dat(
        identity=ai or ca.le_tan,
        visit_id=visit,
        service_code=ca.ma_dv,
        noi=noi,
        chon=chon,
        expected_order_id=expected_order_id,
        expected_version=expected_version,
        expected_state_revision=expected_state_revision or 0,
        idempotency_key=idempotency_key or _khoa(),
    )


async def _nut(pool: asyncpg.Pool, ca: Ca, visit: str, noi: str = "tiep_don") -> dict:  # type: ignore[type-arg]  # noqa: F811
    goi = await LamThemTaiQuayService(pool).nut_cho_luot(
        identity=ca.le_tan if noi == "tiep_don" else ca.dd, noi=noi, visit_ids=visit
    )
    return goi


async def test_le_tan_tick_la_chi_dinh_chot_lam_quay_thu_thay_ngay(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca, visit = await _san_sang(pool)
    goi = await _nut(pool, ca, visit)
    assert ca.ma_dv in [n["service_code"] for n in goi["nut"]]
    assert goi["luot"][visit][ca.ma_dv]["chon"] is False

    kq = await _tick(pool, ca, visit)
    assert kq["changed"] is True
    oid = kq["order_id"]
    o = await pool.fetchrow(
        "SELECT consultation_id, nguon_lam_them, selection_status, exec_status,"
        " lan_chi_dinh, recorded_by::text AS ai FROM service_order"
        " WHERE id = $1::uuid",
        oid,
    )
    assert o["consultation_id"] is None
    assert o["nguon_lam_them"] == "tiep_don"
    assert o["selection_status"] == "SELECTED"
    assert o["exec_status"] == "authorized"
    assert o["lan_chi_dinh"] is None  # không đẩy lần đầu của bác sĩ thành "Lần 2"
    assert o["ai"] == ca.le_tan.staff_id
    assert len(await _su_kien(pool, "service_order.desk_added", oid)) == 1

    # Quầy thu thấy dòng, ghi rõ "làm thêm tại quầy", không gán cho bác sĩ.
    async with pool.acquire() as conn:
        cho = (await cho_khach_quyet(conn, CLINIC, [visit]))[visit]
    dong = next(c for c in cho["chi_dinh"] if c["id"] == oid)
    assert dong["selection_status"] == "SELECTED"
    assert dong["lam_them"] == "Làm thêm tại quầy tiếp đón"
    assert dong["bac_si_chi_dinh"] is None

    # Tick lại = không làm gì (chạy lại được), không sự kiện thứ hai.
    lai = await _tick(pool, ca, visit)
    assert lai["ok"] is True and lai["changed"] is False
    assert lai["order_id"] == oid and lai["order_version"] >= 1
    assert len(await _su_kien(pool, "service_order.desk_added", oid)) == 1

    goi = await _nut(pool, ca, visit)
    tt = goi["luot"][visit][ca.ma_dv]
    assert tt["chon"] is True and tt["doi_duoc"] is True and tt["luot_mo"] is True


async def test_thu_truoc_mac_dinh_thu_xong_tu_xep_phong_roi_khong_bo_tick_duoc(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca, visit = await _san_sang(pool)
    async with day_thu_truoc(pool, True):
        oid = (await _tick(pool, ca, visit))["order_id"]
        await chay_hanh_trinh(pool)
        # Chưa thu → chưa xếp phòng (cửa làm của dây thu trước).
        assert (await _don(pool, oid))["routing_status"] == "UNASSIGNED"
        await _thu(pool, visit, ca.thu_ngan)
        await chay_hanh_trinh(pool)
        d = await _don(pool, oid)
        assert d["routing_status"] == "ASSIGNED"
        assert d["room_id"] is not None  # phòng vắng nhất làm được bước này
        with pytest.raises(ConflictError) as loi:
            await _tick(pool, ca, visit, chon=False)
        assert getattr(loi.value, "error_code", None) == "SERVICE_ALREADY_PAID"
        goi = await _nut(pool, ca, visit)
        assert goi["luot"][visit][ca.ma_dv]["doi_duoc"] is False


async def test_bo_tick_truoc_khi_lam_huy_chi_dinh_va_cho_phong(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca, visit = await _san_sang(pool)
    async with day_thu_truoc(pool, False):  # V10: chốt là xếp phòng ngay
        oid = (await _tick(pool, ca, visit))["order_id"]
        await chay_hanh_trinh(pool)
        assert (await _don(pool, oid))["routing_status"] == "ASSIGNED"
        assert await pool.fetchval(
            "SELECT status FROM queue_entry WHERE ref_id = $1::uuid"
            " AND reason = 'SERVICE'",
            oid,
        ) in ("waiting", "blocked")

        kq = await _tick(pool, ca, visit, chon=False)
        assert kq["changed"] is True
    o = await pool.fetchrow(
        "SELECT exec_status, selection_status, room_id, cancelled_by::text AS ai"
        " FROM service_order WHERE id = $1::uuid",
        oid,
    )
    assert o["exec_status"] == "cancelled"
    assert o["selection_status"] == "NOT_SELECTED"
    assert o["room_id"] is None
    assert o["ai"] == ca.le_tan.staff_id
    assert (
        await pool.fetchval(
            "SELECT status FROM queue_entry WHERE ref_id = $1::uuid"
            " AND reason = 'SERVICE'",
            oid,
        )
        == "cancelled"
    )
    assert len(await _su_kien(pool, "service_order.desk_removed", oid)) == 1
    async with pool.acquire() as conn:
        cho = await cho_khach_quyet(conn, CLINIC, [visit])
    assert oid not in [c["id"] for c in cho.get(visit, {}).get("chi_dinh", [])]
    # Bỏ lần nữa: không lỗi, không đổi.
    assert (await _tick(pool, ca, visit, chon=False))["changed"] is False

    # Đổi ý: tick lại → chỉ định MỚI (cái cũ vẫn nằm đó, đã huỷ).
    moi = await _tick(pool, ca, visit)
    assert moi["changed"] is True and moi["order_id"] != oid


async def test_nguoi_do_sinh_hieu_tick_khi_le_tan_chua_tick_va_hanh_trinh_ghi_nhan(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca, visit = await _san_sang(pool)
    kq = await _tick(pool, ca, visit, noi="sinh_hieu", ai=ca.dd)
    oid = kq["order_id"]
    assert (
        await pool.fetchval(
            "SELECT nguon_lam_them FROM service_order WHERE id = $1::uuid", oid
        )
        == "sinh_hieu"
    )
    # Lễ tân thấy trạng thái đã tick, bỏ được (phòng khám mở, sửa sai được).
    goi = await _nut(pool, ca, visit)
    assert goi["luot"][visit][ca.ma_dv]["chon"] is True

    async with pool.acquire() as conn:
        ht = (await doc_hanh_trinh_khach(conn, clinic_id=CLINIC, visit_ids=[visit]))[
            visit
        ]
    lam_dv = next(b for b in ht["buoc"] if b["ma"] == "LAM_DV")
    the = next(t for t in lam_dv["dich_vu"] if t["id"] == oid)
    assert the["lam_them"] == "Làm thêm tại bàn sinh hiệu"
    assert ht["gon"]["lam_them"] == [the["ten"]]
    # "Khám bác sĩ chính — chỉ định N dịch vụ" không tính việc làm thêm.
    kham = next(b for b in ht["buoc"] if b["ma"] == "KHAM")
    assert kham.get("so_chi_dinh", 0) == 0


async def test_khong_co_lego_cua_man_thi_khong_bam_duoc(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca, visit = await _san_sang(pool)
    async with pool.acquire() as conn:
        doi_tac = await _nguoi(conn, ca.loc, "PARTNER")
    with pytest.raises(SafetyGateError):
        await _tick(pool, ca, visit, noi="sinh_hieu", ai=doi_tac)
    goi = await LamThemTaiQuayService(pool).nut_cho_luot(
        identity=doi_tac, noi="tiep_don", visit_ids=visit
    )
    assert goi["nut"] == [] and goi["luot"] == {}
    with pytest.raises(ValidationError):
        await _tick(pool, ca, visit, noi="phong-la")


async def test_quan_ly_tat_nut_hoac_bo_cho_hien_thi_quay_khong_tick_duoc(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca, visit = await _san_sang(pool, o_sinh_hieu=False)
    ql = await _quan_ly(pool, ca)
    svc = LamThemTaiQuayService(pool)
    # Không hiện ở Đo sinh hiệu → màn ấy không có nút, lệnh từ chối.
    goi = await _nut(pool, ca, visit, noi="sinh_hieu")
    assert ca.ma_dv not in [n["service_code"] for n in goi["nut"]]
    with pytest.raises(ConflictError):
        await _tick(pool, ca, visit, noi="sinh_hieu", ai=ca.dd)
    # Tắt hẳn.
    await svc.luu_muc(identity=ql, service_code=ca.ma_dv, bat=False)
    with pytest.raises(ConflictError) as loi:
        await _tick(pool, ca, visit)
    assert getattr(loi.value, "error_code", None) == "DESK_SERVICE_OFF"
    # Bật mà không hiện ở đâu = cấu hình câm → từ chối.
    with pytest.raises(ValidationError):
        await svc.luu_muc(
            identity=ql,
            service_code=ca.ma_dv,
            bat=True,
            o_tiep_don=False,
            o_sinh_hieu=False,
        )
    # Lễ tân không sửa danh sách (cửa `config.wiring.manage`).
    with pytest.raises(SafetyGateError):
        await svc.luu_muc(identity=ca.le_tan, service_code=ca.ma_dv)
    # Dịch vụ không có trong bảng giá.
    with pytest.raises(ValidationError):
        await svc.luu_muc(identity=ql, service_code=f"KHONG-{uuid.uuid4().hex[:6]}")
    # Bớt nút là tắt mềm: giữ nguyên cấu hình để bật lại đúng nhãn / thứ tự.
    await svc.luu_muc(
        identity=ql,
        service_code=ca.ma_dv,
        nhan="Nước tiểu thử",
        bat=True,
        o_sinh_hieu=False,
    )
    kq = await svc.bo_muc(identity=ql, service_code=ca.ma_dv)
    da_tat = next(m for m in kq["muc"] if m["service_code"] == ca.ma_dv)
    assert da_tat["bat"] is False and da_tat["nhan"] == "Nước tiểu thử"
    await svc.luu_muc(
        identity=ql,
        service_code=ca.ma_dv,
        nhan=da_tat["nhan"],
        bat=True,
        thu_tu=da_tat["thu_tu"],
        o_tiep_don=da_tat["o_tiep_don"],
        o_sinh_hieu=da_tat["o_sinh_hieu"],
    )
    ch = await svc.cau_hinh(identity=ql)
    bat_lai = next(m for m in ch["muc"] if m["service_code"] == ca.ma_dv)
    assert bat_lai["bat"] is True and bat_lai["nhan"] == "Nước tiểu thử"


async def test_doi_thu_tu_hai_nut_la_mot_giao_dich(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca, _ = await _san_sang(pool)
    ql = await _quan_ly(pool, ca)
    ma_hai = f"DV2-{uuid.uuid4().hex[:8]}"
    await pool.execute(
        'INSERT INTO service_price (clinic_id, service_code, name, "group",'
        " unit_price, node_code) VALUES ($1::uuid, $2, 'Dịch vụ thứ hai',"
        " 'dich_vu', 10000, 'DICHVU-SIEUAM')",
        CLINIC,
        ma_hai,
    )
    svc = LamThemTaiQuayService(pool)
    await svc.luu_muc(identity=ql, service_code=ma_hai, thu_tu=20)
    await svc.doi_thu_tu(
        identity=ql,
        muc=[
            {"service_code": ca.ma_dv, "thu_tu": 20},
            {"service_code": ma_hai, "thu_tu": 10},
        ],
    )
    assert (
        await pool.fetchval(
            "SELECT thu_tu FROM lam_them_tai_quay WHERE clinic_id = $1::uuid"
            " AND service_code = $2",
            CLINIC,
            ca.ma_dv,
        )
        == 20
    )
    with pytest.raises(NotFoundError):
        await svc.doi_thu_tu(
            identity=ql,
            muc=[
                {"service_code": ca.ma_dv, "thu_tu": 99},
                {"service_code": "KHONG-CO", "thu_tu": 1},
            ],
        )
    # Một mã thiếu làm rollback cả mã hợp lệ, không để thứ tự nửa vời.
    assert (
        await pool.fetchval(
            "SELECT thu_tu FROM lam_them_tai_quay WHERE clinic_id = $1::uuid"
            " AND service_code = $2",
            CLINIC,
            ca.ma_dv,
        )
        == 20
    )


async def test_bac_si_da_chi_dinh_thi_quay_khong_chong_them(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca, visit = await _san_sang(pool)
    con = str(
        await pool.fetchval(
            "SELECT id::text FROM consultation WHERE visit_id = $1::uuid"
            " AND kind = 'PRIMARY'",
            visit,
        )
    )
    await LuotKhamService(pool).start_consultation(
        consultation_id=con, identity=ca.bac_si
    )
    await ChiDinhService(pool).dat_chi_dinh(
        consultation_id=con,
        service_codes=[ca.ma_dv],
        identity=ca.bac_si,
        idempotency_key=_khoa(),
    )
    goi = await _nut(pool, ca, visit)
    tt = goi["luot"][visit][ca.ma_dv]
    assert tt["chon"] is True and tt["doi_duoc"] is False
    assert tt["ghi_chu"] == "bác sĩ đã chỉ định"
    with pytest.raises(ConflictError) as loi:
        await _tick(pool, ca, visit)
    assert getattr(loi.value, "error_code", None) == "ALREADY_ORDERED"


async def test_phong_da_bat_dau_lam_thi_khong_bo_tick_duoc(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca, visit = await _san_sang(pool)
    async with day_thu_truoc(pool, False):
        oid = (await _tick(pool, ca, visit))["order_id"]
        await chay_hanh_trinh(pool)
        d = await pool.fetchrow(
            "SELECT execution_revision, routing_revision FROM service_order"
            " WHERE id = $1::uuid",
            oid,
        )
        await ServiceExecutionService(pool).bat_dau(
            order_id=oid,
            expected_execution_revision=int(d["execution_revision"]),
            expected_routing_revision=int(d["routing_revision"]),
            identity=ca.dd,
            idempotency_key=_khoa(),
        )
        with pytest.raises(ConflictError) as loi:
            await _tick(pool, ca, visit, chon=False)
        assert getattr(loi.value, "error_code", None) == "SERVICE_STARTED"
        tt = (await _nut(pool, ca, visit))["luot"][visit][ca.ma_dv]
        assert tt["chon"] is True and tt["doi_duoc"] is False


async def test_hai_nguoi_tick_cung_luc_chi_mot_chi_dinh(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca, visit = await _san_sang(pool)
    a, b = await asyncio.gather(
        _tick(pool, ca, visit),
        _tick(pool, ca, visit, noi="sinh_hieu", ai=ca.dd),
    )
    assert a["order_id"] == b["order_id"]
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM service_order WHERE visit_id = $1::uuid"
            " AND nguon_lam_them IS NOT NULL AND exec_status <> 'cancelled'",
            visit,
        )
        == 1
    )


async def test_khach_da_check_out_thi_khong_them(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca, visit = await _san_sang(pool)
    await pool.execute(
        "UPDATE visit SET closed_at = now() WHERE visit_id = $1::uuid", visit
    )
    with pytest.raises(ConflictError) as loi:
        await _tick(pool, ca, visit)
    assert getattr(loi.value, "error_code", None) == "VISIT_CHECKED_OUT"
    goi = await _nut(pool, ca, visit)
    assert goi["luot"][visit][ca.ma_dv]["luot_mo"] is False


async def test_chi_dinh_khong_phien_kham_phai_co_nguon_quay(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Postgres giữ luật: chỉ định không gắn phiên khám thì PHẢI là làm thêm."""
    ca, visit = await _san_sang(pool)
    with pytest.raises(asyncpg.CheckViolationError):
        await pool.execute(
            "INSERT INTO service_order (clinic_id, visit_id, service_code,"
            " service_name, node_code, exec_status, recorded_by)"
            " VALUES ($1::uuid, $2::uuid, $3, 'x', $4, 'draft', $5::uuid)",
            CLINIC,
            visit,
            ca.ma_dv,
            "DICHVU-SIEUAM",
            ca.le_tan.staff_id,
        )


async def test_chi_dinh_chi_thuoc_bac_si_hoac_quay_khong_duoc_ca_hai(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Bất biến DB là XOR: phiên bác sĩ và nguồn quầy loại trừ nhau."""
    ca, visit = await _san_sang(pool)
    consultation_id = await pool.fetchval(
        "SELECT id FROM consultation WHERE visit_id = $1::uuid AND kind = 'PRIMARY'",
        visit,
    )
    with pytest.raises(asyncpg.CheckViolationError):
        await pool.execute(
            "INSERT INTO service_order (clinic_id, visit_id, consultation_id,"
            " service_code, service_name, node_code, exec_status, recorded_by,"
            " nguon_lam_them) VALUES ($1::uuid, $2::uuid, $3::uuid, $4, 'x',"
            " $5, 'draft', $6::uuid, 'tiep_don')",
            CLINIC,
            visit,
            consultation_id,
            ca.ma_dv,
            "DICHVU-SIEUAM",
            ca.le_tan.staff_id,
        )


async def test_lenh_cu_khong_huy_chi_dinh_moi_va_gui_lai_khong_nhan_doi(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca, visit = await _san_sang(pool)
    khoa_them = _khoa()
    them = await _tick(
        pool, ca, visit, expected_state_revision=0, idempotency_key=khoa_them
    )
    # Retry đúng khoá trả nguyên biên nhận, không phát thêm sự kiện.
    assert (
        await _tick(
            pool, ca, visit, expected_state_revision=0, idempotency_key=khoa_them
        )
        == them
    )
    assert len(await _su_kien(pool, "service_order.desk_added", them["order_id"])) == 1

    tt = (await _nut(pool, ca, visit))["luot"][visit][ca.ma_dv]
    await _tick(
        pool,
        ca,
        visit,
        chon=False,
        expected_order_id=tt["order_id"],
        expected_version=tt["order_version"],
        expected_state_revision=tt["state_revision"],
        idempotency_key=_khoa(),
    )
    moi = await _tick(pool, ca, visit, idempotency_key=_khoa())
    assert moi["order_id"] != them["order_id"]

    # Gói giao diện cũ của chỉ định đầu tiên đến muộn: không được huỷ dòng mới.
    with pytest.raises(ConflictError) as loi:
        await _tick(
            pool,
            ca,
            visit,
            chon=False,
            expected_order_id=tt["order_id"],
            expected_version=tt["order_version"],
            expected_state_revision=tt["state_revision"],
            idempotency_key=_khoa(),
        )
    assert getattr(loi.value, "error_code", None) == "STALE_DESK_SERVICE"
    assert (
        await pool.fetchval(
            "SELECT exec_status FROM service_order WHERE id = $1::uuid",
            moi["order_id"],
        )
        != "cancelled"
    )


async def test_tick_lai_cap_nhat_dung_nguoi_va_nguon_moi(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca, visit = await _san_sang(pool)
    oid = (await _tick(pool, ca, visit))["order_id"]
    await pool.execute(
        "UPDATE service_order SET selection_status = 'NOT_SELECTED',"
        " version = version + 1 WHERE id = $1::uuid",
        oid,
    )
    tt = (await _nut(pool, ca, visit, noi="sinh_hieu"))["luot"][visit][ca.ma_dv]
    await _tick(
        pool,
        ca,
        visit,
        noi="sinh_hieu",
        ai=ca.dd,
        expected_order_id=oid,
        expected_version=tt["order_version"],
        expected_state_revision=tt["state_revision"],
        idempotency_key=_khoa(),
    )
    o = await pool.fetchrow(
        "SELECT recorded_by::text AS ai, authorized_by::text AS duyet,"
        " nguon_lam_them FROM service_order WHERE id = $1::uuid",
        oid,
    )
    assert (o["ai"], o["duyet"], o["nguon_lam_them"]) == (
        ca.dd.staff_id,
        ca.dd.staff_id,
        "sinh_hieu",
    )


async def test_lenh_them_cu_khong_song_lai_sau_mot_vong_them_bo(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Tombstone tăng đơn điệu chặn ABA khi trạng thái lại là “chưa có”."""
    ca, visit = await _san_sang(pool)
    cu = (await _nut(pool, ca, visit))["luot"][visit][ca.ma_dv]
    oid = (await _tick(pool, ca, visit))["order_id"]
    hien = (await _nut(pool, ca, visit))["luot"][visit][ca.ma_dv]
    await _tick(
        pool,
        ca,
        visit,
        chon=False,
        expected_order_id=oid,
        expected_version=hien["order_version"],
        expected_state_revision=hien["state_revision"],
    )
    with pytest.raises(ConflictError) as loi:
        await _tick(
            pool,
            ca,
            visit,
            expected_state_revision=cu["state_revision"],
            idempotency_key=_khoa(),
        )
    assert getattr(loi.value, "error_code", None) == "STALE_DESK_SERVICE"
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM service_order WHERE visit_id = $1::uuid"
            " AND service_code = $2 AND exec_status <> 'cancelled'",
            visit,
            ca.ma_dv,
        )
        == 0
    )


async def test_kham_xong_khong_bi_chi_dinh_quay_ep_mo_vong_doc(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Dịch vụ quầy đi độc lập, không biến thành quyết định của bác sĩ."""
    ca, visit = await _san_sang(pool)
    phien = str(
        await pool.fetchval(
            "SELECT id FROM consultation WHERE visit_id = $1::uuid"
            " AND kind = 'PRIMARY'",
            visit,
        )
    )
    await LuotKhamService(pool).start_consultation(
        consultation_id=phien, identity=ca.bac_si
    )
    oid = (await _tick(pool, ca, visit))["order_id"]
    await LuotKhamService(pool).kham_xong(
        consultation_id=phien, identity=ca.bac_si, idempotency_key=_khoa()
    )
    c = await pool.fetchrow(
        "SELECT outcome, status FROM consultation WHERE id = $1::uuid", phien
    )
    assert (c["outcome"], c["status"]) == ("NO_SERVICES", "completed")
    assert (
        await pool.fetchval(
            "SELECT exec_status FROM service_order WHERE id = $1::uuid", oid
        )
        != "cancelled"
    )
