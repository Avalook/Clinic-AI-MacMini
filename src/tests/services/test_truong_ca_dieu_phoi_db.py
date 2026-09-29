"""Trưởng ca điều phối được (Tuyền chốt 29/09/2026).

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55680/postgres \\
        poetry run pytest src/tests/services/test_truong_ca_dieu_phoi_db.py

1. TRƯỚC KHI KHÁCH TRẢ TIỀN: trưởng ca đặt phòng dự kiến (nguồn trưởng ca); thu
   xong dây H4 xếp đúng phòng ấy. Quầy thu VẪN đổi được — và mọi lần xếp / đổi
   có dòng lịch sử (giờ · nguồn · A → B · lý do).
2. DỊCH VỤ ĐÃ BẮT ĐẦU: chỉ trưởng ca chuyển được — một lệnh: dừng lần làm (có
   lý do) + chuyển phòng + chuyển hàng + sự kiện. Dịch vụ xong vẫn chặn.
3. NHÃN TRẠNG THÁI của từng dịch vụ trên màn trưởng ca (máy chủ quyết).
"""

from __future__ import annotations

import json
from typing import Any

import asyncpg
import pytest

from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.services.dispatch_service import DispatchService
from clinicai.services.hanh_trinh_khach_service import HanhTrinhKhachService
from clinicai.services.lenh_kham_core import (
    LuotKhamConflictError,
    LuotKhamValidationError,
)
from clinicai.services.service_execution_service import ServiceExecutionService
from clinicai.services.service_routing_service import ServiceRoutingService
from tests.chay_nguoi_dua_tin import chay_hanh_trinh
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    _nguoi,
    pool,
)
from tests.services.test_nguon_xep_phong_db import _phong_thu_hai
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    _benh_nhan,
    _check_in,
    _chon,
    _don,
    _dung,
    _kham_va_chi_dinh,
    _khoa,
    _su_kien,
    _thu,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _mot_dv(pool: asyncpg.Pool, visit: str, order: str) -> dict[str, Any]:  # noqa: F811
    [d] = [
        x
        for x in await DispatchService(pool).chi_dinh(clinic_id=CLINIC, visit_id=visit)
        if x["id"] == order
    ]
    return d


async def _lich_su(
    pool: asyncpg.Pool,  # noqa: F811
    visit: str,
    order: str,
    ai: StaffIdentity,
) -> list[dict[str, Any]]:
    ht = await HanhTrinhKhachService(pool).mot_luot(visit_id=visit, identity=ai)
    return list(ht["lich_su_phong"].get(order, []))


async def test_truong_ca_dat_phong_truoc_thu_roi_quay_doi_duoc_va_co_lich_su(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    phong_hai = await _phong_thu_hai(pool, ca.loc)
    async with pool.acquire() as conn:
        truong_ca = await _nguoi(conn, ca.loc, "TRUONG_CA")
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    _con, order = await _kham_va_chi_dinh(pool, ca, visit)
    await _chon(pool, ca, visit, [order])
    svc = ServiceRoutingService(pool)

    # Chưa thu: máy chủ nói trưởng ca đặt PHÒNG DỰ KIẾN; lễ tân không có lối này.
    goi_y = await svc.recommend(order_id=order, identity=truong_ca)
    assert goi_y["che_do"] == "DU_KIEN"
    assert goi_y["cau_che_do"] == "Phòng dự kiến — xếp khi thu tiền xong."
    assert (await svc.recommend(order_id=order, identity=ca.le_tan))["che_do"] == (
        "KHONG"
    )
    assert (await _mot_dv(pool, visit, order))["trang_thai"]["ma"] == "CHUA_THU"

    # Lệnh xếp thường vẫn chặn vì chưa trả tiền — trưởng ca đi đường dự kiến.
    kq = await svc.dat_phong_du_kien(
        order_id=order, room_id=phong_hai, identity=truong_ca, nguon="truong_ca"
    )
    assert kq["phong_du_kien_id"] == phong_hai and kq["nguon"] == "truong_ca"
    assert (await svc.recommend(order_id=order, identity=truong_ca))[
        "phong_du_kien_id"
    ] == phong_hai
    # Người không có lego Điều phối khách không xưng nguồn trưởng ca được.
    with pytest.raises(SafetyGateError):
        await svc.dat_phong_du_kien(
            order_id=order, room_id=ca.phong, identity=ca.le_tan, nguon="truong_ca"
        )

    # Thu xong → H4 xếp ĐÚNG phòng trưởng ca đặt, sự kiện ghi ai đặt trước.
    await _thu(pool, visit, ca.le_tan)
    await chay_hanh_trinh(pool)
    d = await _don(pool, order)
    assert d["room_id"] == phong_hai and d["routing_status"] == "ASSIGNED"
    [ev] = await _su_kien(pool, "service.routed", order)
    assert json.loads(ev["payload"])["du_kien_nguon"] == "truong_ca"
    dv = await _mot_dv(pool, visit, order)
    # Bác sĩ chính còn đang khám → chỗ ở phòng giữ, chờ khách xong bước kia.
    assert dv["trang_thai"]["ma"] == "DANG_CHO"
    assert dv["trang_thai"]["nhan"] == "Đang chờ (khách đang ở bước khác)"
    assert dv["trang_thai"]["chuyen_duoc"] is True

    # Quầy thu đổi phòng trưởng ca đã xếp → ĐƯỢC (bỏ khoá 29/09), có lịch sử.
    await svc.assign(
        order_id=order,
        room_id=ca.phong,
        expected_routing_revision=int(d["routing_revision"]),
        reason_code="MANUAL_CORRECTION",
        identity=ca.le_tan,
        idempotency_key=_khoa(),
        nguon="quay_thu",
    )
    assert (await _don(pool, order))["room_id"] == ca.phong
    ls = await _lich_su(pool, visit, order, ca.le_tan)
    assert [x["nguon"] for x in ls] == ["tu_dong", "quay_thu"]
    assert "theo phòng trưởng ca chọn trước khi thu" in ls[0]["cau"]
    assert ls[1]["cau"].startswith("Quầy thu đổi phòng Phòng hai → Phòng thử")
    assert ls[1]["luc"] and ls[1]["ai"] == ca.le_tan.full_name


async def test_truong_ca_chuyen_dich_vu_dang_lam(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    phong_hai = await _phong_thu_hai(pool, ca.loc)
    async with pool.acquire() as conn:
        truong_ca = await _nguoi(conn, ca.loc, "TRUONG_CA")
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    _con, order = await _kham_va_chi_dinh(pool, ca, visit)
    await _chon(pool, ca, visit, [order])
    svc = ServiceRoutingService(pool)
    # Quầy chọn phòng trước thu (không để H4 chọn phòng của bài kiểm khác).
    await svc.dat_phong_du_kien(order_id=order, room_id=ca.phong, identity=ca.le_tan)
    await _thu(pool, visit, ca.le_tan)
    await chay_hanh_trinh(pool)
    d = await _don(pool, order)
    assert d["room_id"] == ca.phong

    # Đã gọi vào → nhãn "Đã gọi", không bày [Chuyển phòng].
    await pool.execute(
        "UPDATE queue_entry SET status = 'called', called_at = now(),"
        " eligible_at = coalesce(eligible_at, now())"
        " WHERE ref_id = $1::uuid AND reason = 'SERVICE'"
        "   AND status IN ('waiting', 'blocked')",
        order,
    )
    dv = await _mot_dv(pool, visit, order)
    assert dv["trang_thai"]["ma"] == "DA_GOI" and not dv["trang_thai"]["chuyen_duoc"]
    assert (await svc.recommend(order_id=order, identity=truong_ca))["che_do"] == (
        "KHONG"
    )

    mo = await ServiceExecutionService(pool).bat_dau(
        order_id=order,
        expected_execution_revision=int(d["execution_revision"]),
        expected_routing_revision=int(d["routing_revision"]),
        identity=ca.dd,
        idempotency_key=_khoa(),
    )
    # Dữ liệu phiếu đã nhập gắn với chỉ định — phải còn nguyên sau khi chuyển.
    mau = await pool.fetchrow(
        "SELECT form_id, version FROM form_definition WHERE clinic_id = $1::uuid"
        " ORDER BY form_id, version LIMIT 1",
        CLINIC,
    )
    assert mau is not None
    phieu = await pool.fetchval(
        "INSERT INTO form_instance (clinic_id, service_order_id, form_id, version,"
        ' du_lieu) VALUES ($1::uuid, $2::uuid, $3, $4, \'{"o": "da nhap"}\'::jsonb)'
        " RETURNING id::text",
        CLINIC,
        order,
        mau["form_id"],
        mau["version"],
    )
    dv = await _mot_dv(pool, visit, order)
    assert dv["trang_thai"]["ma"] == "DANG_LAM" and dv["trang_thai"]["tu_luc"]
    assert dv["trang_thai"]["chuyen_duoc"] is True
    goi_y = await svc.recommend(order_id=order, identity=truong_ca)
    assert goi_y["che_do"] == "CHUYEN_DANG_LAM" and goi_y["dang_lam_tu"]
    assert goi_y["phong_hien_tai"]
    # Người làm ở phòng (không phải trưởng ca) không có lối này.
    assert (await svc.recommend(order_id=order, identity=ca.dd))["che_do"] == "KHONG"

    rev = int((await _don(pool, order))["routing_revision"])

    async def chuyen(
        ai: StaffIdentity, khoa: str, ly_do: object = "Máy siêu âm hỏng đầu dò"
    ) -> dict[str, Any]:
        return await svc.chuyen_phong_dang_lam(
            order_id=order,
            room_id=phong_hai,
            expected_routing_revision=rev,
            ly_do=ly_do,
            identity=ai,
            idempotency_key=khoa,
        )

    # Không phải trưởng ca → vẫn bị chặn.
    for ai in (ca.le_tan, ca.dd):
        with pytest.raises(SafetyGateError):
            await chuyen(ai, _khoa())
    # Thiếu lý do → chặn.
    for rac in ("", "  ", None, 12):
        with pytest.raises(LuotKhamValidationError) as loi_ly_do:
            await chuyen(truong_ca, _khoa(), rac)
        assert loi_ly_do.value.error_code == "TRANSFER_REASON_REQUIRED"

    khoa = _khoa()
    kq = await chuyen(truong_ca, khoa)
    assert kq["room_id"] == phong_hai and kq["execution_status"] == "PENDING"
    # Gửi lại cùng khoá → cùng kết quả, không làm lần hai.
    assert await chuyen(truong_ca, khoa) == kq

    sau = await pool.fetchrow(
        "SELECT room_id::text AS room_id, execution_status, exec_status,"
        " routing_nguon FROM service_order WHERE id = $1::uuid",
        order,
    )
    assert dict(sau) == {
        "room_id": phong_hai,
        "execution_status": "PENDING",
        "exec_status": "assigned",
        "routing_nguon": "truong_ca",
    }
    # Hàng phòng mới có khách (đang chờ), không còn chỗ nào ở phòng cũ.
    hang = await pool.fetch(
        "SELECT room_id::text AS room_id, status FROM queue_entry"
        " WHERE ref_id = $1::uuid AND reason = 'SERVICE'"
        "   AND status NOT IN ('done', 'left', 'cancelled')",
        order,
    )
    assert [(h["room_id"], h["status"]) for h in hang] == [(phong_hai, "waiting")]
    assert (
        await pool.fetchval(
            "SELECT current_room_id::text FROM visit WHERE visit_id = $1::uuid", visit
        )
        == phong_hai
    )
    # Lần làm cũ đóng CÓ LÝ DO.
    lan = await pool.fetchrow(
        "SELECT status, interruption_reason_code, interruption_reason_note"
        " FROM service_execution_attempt WHERE id = $1::uuid",
        mo["attempt_id"],
    )
    assert lan["status"] == "INTERRUPTED"
    assert lan["interruption_reason_code"] == "OTHER"
    assert "Máy siêu âm hỏng đầu dò" in lan["interruption_reason_note"]
    # Phiếu đã nhập còn nguyên.
    assert (
        await pool.fetchval(
            "SELECT du_lieu ->> 'o' FROM form_instance WHERE id = $1::uuid", phieu
        )
        == "da nhap"
    )
    # Sự kiện ghi một lần, kèm lý do.
    [ev] = await _su_kien(pool, "service.room_transferred", order)
    p = json.loads(ev["payload"])
    assert p["ly_do"] == "Máy siêu âm hỏng đầu dò"
    assert p["from_room_id"] == ca.phong and p["room_id"] == phong_hai
    assert ev["ai"] == truong_ca.staff_id
    # Lịch sử lượt.
    ls = await _lich_su(pool, visit, order, truong_ca)
    assert ls[-1]["cau"] == (
        "Trưởng ca chuyển phòng khi đang làm "
        f"{ls[-1]['tu_phong']} → Phòng hai: Máy siêu âm hỏng đầu dò"
    )
    dv = await _mot_dv(pool, visit, order)
    assert dv["trang_thai"]["ma"] == "DANG_CHO" and dv["room_id"] == phong_hai
    assert dv["trang_thai"]["stt"] == 1 and dv["trang_thai"]["so_truoc"] == 0
    assert dv["trang_thai"]["tu_luc"]

    # Phòng mới bắt đầu lại được; làm xong thì KHÔNG chuyển được nữa.
    d2 = await _don(pool, order)
    mo2 = await ServiceExecutionService(pool).bat_dau(
        order_id=order,
        expected_execution_revision=int(d2["execution_revision"]),
        expected_routing_revision=int(d2["routing_revision"]),
        identity=ca.dd,
        idempotency_key=_khoa(),
    )
    assert mo2["attempt_no"] == 2
    await ServiceExecutionService(pool).xong(
        order_id=order,
        attempt_id=mo2["attempt_id"],
        expected_execution_revision=mo2["execution_revision"],
        identity=ca.dd,
        idempotency_key=_khoa(),
    )
    assert (await _mot_dv(pool, visit, order))["trang_thai"]["ma"] == "XONG"
    rev = int((await _don(pool, order))["routing_revision"])
    with pytest.raises(LuotKhamConflictError) as loi:
        await svc.chuyen_phong_dang_lam(
            order_id=order,
            room_id=ca.phong,
            expected_routing_revision=rev,
            ly_do="đổi lại",
            identity=truong_ca,
            idempotency_key=_khoa(),
        )
    assert loi.value.error_code == "SERVICE_EXECUTION_TERMINAL"


async def test_chua_bat_dau_thi_lenh_chuyen_dang_lam_tu_choi(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    phong_hai = await _phong_thu_hai(pool, ca.loc)
    async with pool.acquire() as conn:
        truong_ca = await _nguoi(conn, ca.loc, "TRUONG_CA")
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    _con, order = await _kham_va_chi_dinh(pool, ca, visit)
    await _chon(pool, ca, visit, [order])
    await _thu(pool, visit, ca.le_tan)
    await chay_hanh_trinh(pool)
    with pytest.raises(LuotKhamConflictError) as loi:
        await ServiceRoutingService(pool).chuyen_phong_dang_lam(
            order_id=order,
            room_id=phong_hai,
            expected_routing_revision=int(
                (await _don(pool, order))["routing_revision"]
            ),
            ly_do="phòng đông",
            identity=truong_ca,
            idempotency_key=_khoa(),
        )
    assert loi.value.error_code == "SERVICE_NOT_IN_PROGRESS"
