"""HOÀN TÁC ở mọi thao tác (Tuyền 01/10/2026 — sau buổi thực nghiệm thật 30/09).

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55600/postgres \\
        .venv/bin/pytest src/tests/services/test_hoan_tac_moi_thao_tac_db.py

"Người dùng thao tác rối và hay làm sai, sai rồi thì không ấn lại được → cần nút
HOÀN TÁC ở tất cả các việc … Không được để bất kể cái gì khoá hẳn."

Mỗi bài: làm thao tác gốc → hoàn tác → trạng thái về đúng (phiên, hàng chờ,
vòng đọc, hoá đơn quầy, lịch hẹn, lượt) + sự kiện ghi (ai, lý do) → LÀM LẠI
thao tác gốc được.
"""

from __future__ import annotations

import json
import uuid

import asyncpg
import pytest

from clinicai.services.bill_service import hoa_don_con_no
from clinicai.services.cashier_board_service import CashierBoardService
from clinicai.services.checkout_service import CheckoutService
from clinicai.services.chi_dinh_service import ChiDinhService
from clinicai.services.hoan_tac_service import (
    CAN_XAC_NHAN,
    HoanTacService,
    tien_thua_cua_luot,
)
from clinicai.services.lenh_kham_core import LuotKhamConflictError
from clinicai.services.luot_kham_service import LuotKhamService
from clinicai.services.service_execution_service import ServiceExecutionService
from tests.chay_nguoi_dua_tin import chay_hanh_trinh
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
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
    _khoa,
    _su_kien,
    _thu,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _phien(
    pool: asyncpg.Pool,  # noqa: F811
    visit: str,
    loai: str = "PRIMARY",
) -> asyncpg.Record:
    return await pool.fetchrow(
        "SELECT id::text AS id, status, outcome, completed_at FROM consultation"
        " WHERE visit_id = $1::uuid AND kind = $2",
        visit,
        loai,
    )


async def _luot(pool: asyncpg.Pool, visit: str) -> asyncpg.Record:  # noqa: F811
    return await pool.fetchrow(
        "SELECT v.status, v.closed_at, v.exam_completed_at, a.status AS lich"
        "  FROM visit v LEFT JOIN appointment a ON a.id = v.appointment_id"
        " WHERE v.visit_id = $1::uuid",
        visit,
    )


async def _cho(pool: asyncpg.Pool, ref: str) -> list[str]:  # noqa: F811
    return [
        r["status"]
        for r in await pool.fetch(
            "SELECT status FROM queue_entry WHERE ref_id = $1::uuid"
            " ORDER BY created_at",
            ref,
        )
    ]


async def _kham_xong(pool: asyncpg.Pool, ca: Ca, con: str) -> dict:  # type: ignore[type-arg]  # noqa: F811
    return await LuotKhamService(pool).kham_xong(
        consultation_id=con, identity=ca.bac_si, idempotency_key=_khoa()
    )


async def _vao_kham(pool: asyncpg.Pool, ca: Ca, visit: str) -> str:  # noqa: F811
    con = (await _phien(pool, visit))["id"]
    await LuotKhamService(pool).start_consultation(
        consultation_id=con, identity=ca.bac_si
    )
    return str(con)


async def _xep_va_lam(pool: asyncpg.Pool, ca: Ca, visit: str, order: str) -> str:  # noqa: F811
    """Khách chốt + trả tiền → H4 xếp phòng → bắt đầu làm. Trả mã lần làm."""
    await _chon(pool, ca, visit, [order])
    await _thu(pool, visit, ca.thu_ngan)
    await chay_hanh_trinh(pool)
    d = await _don(pool, order)
    assert d["routing_status"] == "ASSIGNED"
    bd = await ServiceExecutionService(pool).bat_dau(
        order_id=order,
        expected_execution_revision=int(d["execution_revision"]),
        expected_routing_revision=int(d["routing_revision"]),
        identity=ca.dd,
        idempotency_key=_khoa(),
    )
    return str(bd["attempt_id"])


async def _xong_dv(pool: asyncpg.Pool, ca: Ca, order: str, attempt: str) -> None:  # noqa: F811
    d = await _don(pool, order)
    await ServiceExecutionService(pool).xong(
        order_id=order,
        attempt_id=attempt,
        expected_execution_revision=int(d["execution_revision"]),
        identity=ca.dd,
        idempotency_key=_khoa(),
    )


# ── (a) Khám xong → mở lại khám ─────────────────────────────────────────────


async def test_kham_xong_hoan_tac_mo_lai_roi_kham_xong_lai(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Kê đơn thiếu số lượng rồi bấm khám xong → Hoàn tác → sửa → khám xong lại."""
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    con = await _vao_kham(pool, ca, visit)
    await _kham_xong(pool, ca, con)
    p = await _phien(pool, visit)
    assert (p["status"], p["outcome"]) == ("completed", "NO_SERVICES")
    l0 = await _luot(pool, visit)
    assert l0["exam_completed_at"] is not None and l0["lich"] == "COMPLETED"

    kq = await HoanTacService(pool).mo_lai_kham(consultation_id=con, identity=ca.bac_si)
    assert kq["ok"] is True and kq["mo_lai_kham_xong"] is True

    p = await _phien(pool, visit)
    assert (p["status"], p["outcome"], p["completed_at"]) == ("in_progress", None, None)
    # Khách về lại bàn bác sĩ, ĐANG KHÁM (nút Hoàn tất hiện lại).
    assert (await _cho(pool, con))[-1] == "serving"
    l1 = await _luot(pool, visit)
    assert l1["exam_completed_at"] is None and l1["lich"] == "CHECKED_IN"
    # Sự kiện: ai hoàn tác, hoàn tác cái gì → dòng thời gian Hành trình khách.
    [ev] = await _su_kien(pool, "consultation.reopened", con)
    assert ev["ai"] == ca.bac_si.staff_id
    pl = json.loads(ev["payload"])
    assert (pl["loai"], pl["ket_qua_cu"], pl["mo_lai_kham_xong"]) == (
        "PRIMARY",
        "NO_SERVICES",
        True,
    )
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM event_log WHERE event_type = 'consult.reopened'"
            " AND aggregate_id = $1",
            visit,
        )
        == 1
    )

    # Bấm hai lần: không làm gì thêm.
    lai = await HoanTacService(pool).mo_lai_kham(
        consultation_id=con, identity=ca.bac_si
    )
    assert lai.get("already") is True
    assert len(await _su_kien(pool, "consultation.reopened", con)) == 1

    # Khám xong LẠI được như thường.
    await _kham_xong(pool, ca, con)
    assert (await _phien(pool, visit))["status"] == "completed"
    assert (await _luot(pool, visit))["exam_completed_at"] is not None


async def test_kham_xong_co_chi_dinh_hoan_tac_bo_vong_doc_vua_mo(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    con, _order = await _kham_va_chi_dinh(pool, ca, visit)
    await _kham_xong(pool, ca, con)
    assert (await _phien(pool, visit))["outcome"] == "SERVICES"
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM review_round WHERE visit_id = $1::uuid", visit
        )
        == 1
    )

    await HoanTacService(pool).mo_lai_kham(consultation_id=con, identity=ca.bac_si)
    assert (await _phien(pool, visit))["status"] == "in_progress"
    # Vòng đọc kết quả lần bấm ấy mở ra (chưa ai đọc) bị bỏ.
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM review_round WHERE visit_id = $1::uuid", visit
        )
        == 0
    )
    # Khám xong lại → mở vòng mới (không vấp chỉ mục duy nhất).
    await _kham_xong(pool, ca, con)
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM review_round WHERE visit_id = $1::uuid", visit
        )
        == 1
    )


async def test_kham_xong_roi_check_out_hoan_tac_phai_xac_nhan_va_mo_lai_luot(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    con = await _vao_kham(pool, ca, visit)
    await _kham_xong(pool, ca, con)
    await CheckoutService(pool).close(
        identity=ca.le_tan, visit_id=visit, ly_do_tu_dong="Lễ tân cho khách về."
    )
    assert (await _luot(pool, visit))["closed_at"] is not None

    # Ràng buộc thật (khách đã về): KHÔNG khoá — hỏi xác nhận + lý do.
    with pytest.raises(LuotKhamConflictError) as e:
        await HoanTacService(pool).mo_lai_kham(consultation_id=con, identity=ca.bac_si)
    assert e.value.error_code == CAN_XAC_NHAN
    assert e.value.chi_tiet and e.value.chi_tiet["can_xac_nhan"] is True
    with pytest.raises(LuotKhamConflictError):  # lý do quá ngắn
        await HoanTacService(pool).mo_lai_kham(
            consultation_id=con, identity=ca.bac_si, xac_nhan=True, ly_do="ab"
        )
    assert (await _phien(pool, visit))["status"] == "completed"

    await HoanTacService(pool).mo_lai_kham(
        consultation_id=con,
        identity=ca.bac_si,
        xac_nhan=True,
        ly_do="Kê đơn thiếu số lượng thuốc",
    )
    lt = await _luot(pool, visit)
    assert lt["closed_at"] is None and lt["exam_completed_at"] is None
    assert lt["lich"] == "CHECKED_IN"
    assert await pool.fetchval(
        "SELECT status FROM work_item WHERE visit_id = $1::uuid"
        " AND node_code = 'LUOTKHAM-15'",
        visit,
    ) in (None, "PENDING")
    [mo] = await _su_kien(pool, "visit.reopened", visit)
    assert json.loads(mo["payload"])["ly_do"] == "Kê đơn thiếu số lượng thuốc"
    [ev] = await _su_kien(pool, "consultation.reopened", con)
    assert json.loads(ev["payload"])["ly_do"] == "Kê đơn thiếu số lượng thuốc"
    # Khám xong lại rồi check-out lại được.
    await _kham_xong(pool, ca, con)
    kq = await CheckoutService(pool).close(
        identity=ca.le_tan, visit_id=visit, ly_do_tu_dong="Lễ tân cho khách về."
    )
    assert kq["ok"] is True and not kq.get("already_closed")


async def test_xong_tu_van_hoan_tac_ve_lai_ban_tu_van(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    loai_tv = await pool.fetchval(
        "INSERT INTO service_type (clinic_id, code, name, is_active, qua_tu_van)"
        " VALUES ($1::uuid, $2, $3, true, true) RETURNING id::text",
        CLINIC,
        f"TV-HT-{uuid.uuid4().hex[:8]}",
        "Khám qua tư vấn (hoàn tác)",
    )
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), str(loai_tv))
    tv = await _phien(pool, visit, "TU_VAN")
    assert tv is not None
    luot = LuotKhamService(pool)
    await luot.start_consultation(consultation_id=tv["id"], identity=ca.bac_si)
    await luot.xong_tu_van(consultation_id=tv["id"], identity=ca.bac_si)
    await chay_hanh_trinh(pool)
    assert (await _phien(pool, visit))["status"] == "queued"

    await HoanTacService(pool).mo_lai_kham(consultation_id=tv["id"], identity=ca.bac_si)
    assert (await _phien(pool, visit, "TU_VAN"))["status"] == "in_progress"
    # Bác sĩ chính chưa nhận → thôi chờ; khách về lại bàn tư vấn.
    chinh = await _phien(pool, visit)
    assert chinh["status"] == "cancelled"
    assert "waiting" not in await _cho(pool, chinh["id"])
    assert (await _cho(pool, tv["id"]))[-1] == "serving"

    # Xong tư vấn LẠI → khách vào lại hàng bác sĩ chính.
    await luot.xong_tu_van(consultation_id=tv["id"], identity=ca.bac_si)
    await chay_hanh_trinh(pool)
    assert (await _phien(pool, visit))["status"] == "queued"
    assert (await _cho(pool, chinh["id"]))[-1] in ("waiting", "blocked")


async def test_tin_xong_tu_van_toi_sau_hoan_tac_khong_dua_sang_bac_si(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Người đưa tin chạy SAU khi đã bấm Hoàn tác: khách vẫn ở bàn tư vấn."""
    ca = await _dung(pool)
    loai_tv = await pool.fetchval(
        "INSERT INTO service_type (clinic_id, code, name, is_active, qua_tu_van)"
        " VALUES ($1::uuid, $2, $3, true, true) RETURNING id::text",
        CLINIC,
        f"TV-HT-{uuid.uuid4().hex[:8]}",
        "Khám qua tư vấn (tin tới muộn)",
    )
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), str(loai_tv))
    tv = await _phien(pool, visit, "TU_VAN")
    luot = LuotKhamService(pool)
    await luot.start_consultation(consultation_id=tv["id"], identity=ca.bac_si)
    await luot.xong_tu_van(consultation_id=tv["id"], identity=ca.bac_si)
    await HoanTacService(pool).mo_lai_kham(consultation_id=tv["id"], identity=ca.bac_si)
    await chay_hanh_trinh(pool)
    chinh = await _phien(pool, visit)
    assert chinh is None or chinh["status"] == "cancelled"


# ── (b) Chỉ định → bỏ chỉ định ──────────────────────────────────────────────


async def test_bo_chi_dinh_chua_thu_hoa_don_quay_bot_ngay_roi_chi_dinh_khac(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    con, order = await _kham_va_chi_dinh(pool, ca, visit)
    await _chon(pool, ca, visit, [order])
    async with pool.acquire() as conn:
        hd = await hoa_don_con_no(conn, clinic_id=CLINIC, visit_id=visit)
    assert order in {d.source_id for d in hd.dong}

    kq = await HoanTacService(pool).huy_chi_dinh(order_id=order, identity=ca.bac_si)
    assert (kq["ok"], kq["da_thu_tien"], kq["tien_thua"]) == (True, False, 0)
    d = await _don(pool, order)
    assert d["exec_status"] == "cancelled"
    # Quầy thu: hoá đơn máy chủ dựng lại — dòng ấy biến mất ngay.
    async with pool.acquire() as conn:
        hd = await hoa_don_con_no(conn, clinic_id=CLINIC, visit_id=visit)
    assert order not in {x.source_id for x in hd.dong}
    [ev] = await _su_kien(pool, "service_order.cancelled", order)
    assert ev["ai"] == ca.bac_si.staff_id
    assert json.loads(ev["payload"])["da_thu_tien"] is False
    # Bấm lại: không làm gì thêm.
    assert (
        await HoanTacService(pool).huy_chi_dinh(order_id=order, identity=ca.bac_si)
    )["already"] is True

    # Chỉ định cái khác được ngay (cùng mã cũng được — chỉ định mới).
    moi = await ChiDinhService(pool).dat_chi_dinh(
        consultation_id=con,
        service_codes=[ca.ma_dv],
        identity=ca.bac_si,
        idempotency_key=_khoa(),
    )
    assert moi["order_ids"] and moi["order_ids"][0] != order


async def test_bo_chi_dinh_da_thu_hoi_xac_nhan_roi_thanh_tien_thua_o_quay(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    _con, order = await _kham_va_chi_dinh(pool, ca, visit)
    await _chon(pool, ca, visit, [order])
    await _thu(pool, visit, ca.thu_ngan)
    await chay_hanh_trinh(pool)
    assert (await _don(pool, order))["routing_status"] == "ASSIGNED"

    # Đã thu: KHÔNG khoá — hỏi xác nhận, nói rõ thành tiền thừa.
    with pytest.raises(LuotKhamConflictError) as e:
        await HoanTacService(pool).huy_chi_dinh(order_id=order, identity=ca.bac_si)
    assert e.value.error_code == CAN_XAC_NHAN
    assert "TIỀN THỪA" in str(e.value)
    assert (await _don(pool, order))["exec_status"] != "cancelled"

    kq = await HoanTacService(pool).huy_chi_dinh(
        order_id=order,
        identity=ca.bac_si,
        xac_nhan=True,
        ly_do="Chỉ định nhầm siêu âm",
    )
    assert kq["da_thu_tien"] is True and kq["tien_thua"] == 300000
    # Khách rời hàng phòng đã xếp.
    assert "waiting" not in await _cho(pool, order)
    async with pool.acquire() as conn:
        thua = await tien_thua_cua_luot(conn, CLINIC, [visit])
    assert thua[visit]["tong"] == 300000
    assert thua[visit]["dong"][0]["loai"] == "BO_CHI_DINH"
    assert thua[visit]["dong"][0]["ly_do"] == "Chỉ định nhầm siêu âm"
    # Quầy thu thấy khoản tiền thừa, khách nằm trong danh sách chờ xử lý.
    bang = await CashierBoardService(pool).board(
        identity=ca.thu_ngan, modes=["dich_vu"]
    )
    [item] = [i for i in bang["items"] if i["visit_id"] == visit]
    assert item["tien_thua"]["tong"] == 300000
    assert visit in bang["ds_cho_thu"]
    pl = json.loads(
        (await _su_kien(pool, "service_order.cancelled", order))[0]["payload"]
    )
    assert (pl["da_thu_tien"], pl["tien_thua"], pl["ly_do"]) == (
        True,
        300000,
        "Chỉ định nhầm siêu âm",
    )


async def test_bo_chi_dinh_dang_lam_thi_noi_huy_bat_dau_truoc(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    _con, order = await _kham_va_chi_dinh(pool, ca, visit)
    await _xep_va_lam(pool, ca, visit, order)
    with pytest.raises(LuotKhamConflictError) as e:
        await HoanTacService(pool).huy_chi_dinh(
            order_id=order, identity=ca.bac_si, xac_nhan=True, ly_do="Nhầm dịch vụ"
        )
    assert e.value.error_code == "ORDER_IN_PROGRESS"
    assert "Huỷ bắt đầu" in str(e.value)


# ── (c) Xong làm dịch vụ → về đang làm ──────────────────────────────────────


async def test_hoan_tac_xong_dich_vu_ve_dang_lam_roi_xong_lai(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    _con, order = await _kham_va_chi_dinh(pool, ca, visit)
    lan = await _xep_va_lam(pool, ca, visit, order)
    await _xong_dv(pool, ca, order, lan)
    assert (
        await pool.fetchval(
            "SELECT execution_status FROM service_order WHERE id = $1::uuid", order
        )
        == "COMPLETED"
    )

    kq = await HoanTacService(pool).hoan_tac_xong_dich_vu(
        order_id=order, identity=ca.dd
    )
    assert kq["execution_status"] == "IN_PROGRESS"
    o = await pool.fetchrow(
        "SELECT execution_status, exec_status, finished_at FROM service_order"
        " WHERE id = $1::uuid",
        order,
    )
    assert (o["execution_status"], o["exec_status"], o["finished_at"]) == (
        "IN_PROGRESS",
        "in_progress",
        None,
    )
    at = await pool.fetchrow(
        "SELECT status, completed_at FROM service_execution_attempt"
        " WHERE id = $1::uuid",
        lan,
    )
    assert (at["status"], at["completed_at"]) == ("IN_PROGRESS", None)
    assert (await _cho(pool, order))[-1] == "serving"
    [ev] = await _su_kien(pool, "service.completion_undone", order)
    assert ev["ai"] == ca.dd.staff_id
    # Bấm lại: không làm gì thêm.
    lai = await HoanTacService(pool).hoan_tac_xong_dich_vu(
        order_id=order, identity=ca.dd
    )
    assert lai.get("already") is True

    # Xong LẠI — đúng lần làm cũ.
    await _xong_dv(pool, ca, order, lan)
    assert (
        await pool.fetchval(
            "SELECT execution_status FROM service_order WHERE id = $1::uuid", order
        )
        == "COMPLETED"
    )


# ── (d) Check-out → mở lại lượt ─────────────────────────────────────────────


async def test_check_out_nham_hoan_tac_mo_lai_luot_roi_check_out_lai(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    con = (await _phien(pool, visit))["id"]
    truoc = await _cho(pool, con)
    assert truoc and truoc[-1] in ("waiting", "blocked")
    await CheckoutService(pool).close(
        identity=ca.le_tan, visit_id=visit, ly_do_tu_dong="Lễ tân cho khách về."
    )
    lt = await _luot(pool, visit)
    assert lt["closed_at"] is not None and lt["lich"] == "COMPLETED"
    assert (await _cho(pool, con))[-1] == "left"

    kq = await HoanTacService(pool).mo_lai_luot(visit_id=visit, identity=ca.le_tan)
    assert kq["ok"] is True and kq["tu_ve_giua_chung"] is False
    lt = await _luot(pool, visit)
    assert lt["closed_at"] is None and lt["lich"] == "CHECKED_IN"
    # Khách về lại hàng chờ bác sĩ.
    assert (await _cho(pool, con))[-1] == "waiting"
    [ev] = await _su_kien(pool, "visit.reopened", visit)
    assert ev["ai"] == ca.le_tan.staff_id
    assert (await HoanTacService(pool).mo_lai_luot(visit_id=visit, identity=ca.le_tan))[
        "already"
    ] is True

    # Bác sĩ khám tiếp được, check-out lại được.
    await LuotKhamService(pool).start_consultation(
        consultation_id=con, identity=ca.bac_si
    )
    kq2 = await CheckoutService(pool).close(
        identity=ca.le_tan, visit_id=visit, ly_do_tu_dong="Lễ tân cho khách về."
    )
    assert kq2["ok"] is True and not kq2.get("already_closed")


async def test_ve_giua_chung_hoan_tac_ve_lai_dang_kham(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    await CheckoutService(pool).close(
        identity=ca.le_tan,
        visit_id=visit,
        incomplete=True,
        incomplete_reason="Khách bận việc về trước",
    )
    assert (await _luot(pool, visit))["status"] == "INCOMPLETE"
    kq = await HoanTacService(pool).mo_lai_luot(visit_id=visit, identity=ca.le_tan)
    assert kq["tu_ve_giua_chung"] is True
    v = await pool.fetchrow(
        "SELECT status, incomplete_reason, closed_at FROM visit"
        " WHERE visit_id = $1::uuid",
        visit,
    )
    assert (v["status"], v["incomplete_reason"], v["closed_at"]) == (
        "IN_PROGRESS",
        None,
        None,
    )


# ── (h) Duyệt kết quả → thu hồi về chờ duyệt ────────────────────────────────


async def test_duyet_ket_qua_nham_thu_hoi_ve_cho_duyet_mo_lai_theo_doi(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    _con, order = await _kham_va_chi_dinh(pool, ca, visit)
    lan = await _xep_va_lam(pool, ca, visit, order)
    await _xong_dv(pool, ca, order, lan)
    await pool.execute(
        "UPDATE service_order SET ket_qua_luc = now() WHERE id = $1::uuid", order
    )
    benh_nhan = await pool.fetchval(
        "SELECT clinic_patient_id FROM visit WHERE visit_id = $1::uuid", visit
    )
    theo_doi = await pool.fetchval(
        "INSERT INTO follow_up_case (clinic_id, clinic_patient_id, visit_id,"
        " service_order_id, reason) VALUES ($1::uuid, $2, $3::uuid, $4::uuid,"
        " 'chờ kết quả') RETURNING id::text",
        CLINIC,
        benh_nhan,
        visit,
        order,
    )
    await LuotKhamService(pool).duyet_ket_qua(
        order_id=order, danh_gia="Bình thường", identity=ca.bac_si
    )
    assert (
        await pool.fetchval(
            "SELECT status FROM follow_up_case WHERE id = $1::uuid", theo_doi
        )
        == "DONE"
    )

    kq = await HoanTacService(pool).thu_hoi_duyet_ket_qua(
        order_id=order, identity=ca.bac_si
    )
    assert kq["ok"] is True and kq["tep_da_gui"] == 0
    o = await pool.fetchrow(
        "SELECT duyet_luc, duyet_boi, bac_si_danh_gia FROM service_order"
        " WHERE id = $1::uuid",
        order,
    )
    # Về chờ duyệt; đánh giá đã ghi giữ làm bản nháp.
    assert (o["duyet_luc"], o["duyet_boi"], o["bac_si_danh_gia"]) == (
        None,
        None,
        "Bình thường",
    )
    f = await pool.fetchrow(
        "SELECT status, closed_at FROM follow_up_case WHERE id = $1::uuid", theo_doi
    )
    assert (f["status"], f["closed_at"]) == ("OPEN", None)
    [ev] = await _su_kien(pool, "result.approval_revoked", order)
    assert ev["ai"] == ca.bac_si.staff_id
    lai = await HoanTacService(pool).thu_hoi_duyet_ket_qua(
        order_id=order, identity=ca.bac_si
    )
    assert lai.get("already") is True

    # Duyệt LẠI được như lần đầu.
    await LuotKhamService(pool).duyet_ket_qua(
        order_id=order, danh_gia=None, identity=ca.bac_si
    )
    assert await pool.fetchval(
        "SELECT duyet_luc IS NOT NULL FROM service_order WHERE id = $1::uuid", order
    )


async def test_thu_hoi_duyet_khi_tep_da_gui_khach_phai_xac_nhan(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    _con, order = await _kham_va_chi_dinh(pool, ca, visit)
    # Giả lập "đã duyệt + có tệp đã gửi khách" bằng cột (đường tải tệp thật
    # có test riêng ở tep_ket_qua).
    await pool.execute(
        "UPDATE service_order SET ket_qua_luc = now(), duyet_luc = now(),"
        " duyet_boi = $2::uuid WHERE id = $1::uuid",
        order,
        ca.bac_si.staff_id,
    )
    benh_nhan = await pool.fetchval(
        "SELECT clinic_patient_id FROM visit WHERE visit_id = $1::uuid", visit
    )
    await pool.execute(
        "INSERT INTO tep_ket_qua (clinic_id, clinic_patient_id, service_order_id,"
        " khoa, loai_tep, mime, so_byte, sha256, tai_len_boi_staff_id,"
        " gui_luc, gui_boi_staff_id, gui_kenh)"
        " VALUES ($1::uuid, $2, $3::uuid, $4, 'PDF', 'application/pdf', 10,"
        " repeat('a', 64), $5::uuid, now(), $5::uuid, 'ZALO')",
        CLINIC,
        benh_nhan,
        order,
        f"thu/{uuid.uuid4()}.pdf",
        ca.bac_si.staff_id,
    )
    with pytest.raises(LuotKhamConflictError) as e:
        await HoanTacService(pool).thu_hoi_duyet_ket_qua(
            order_id=order, identity=ca.bac_si
        )
    assert e.value.error_code == CAN_XAC_NHAN
    assert "Đã gửi 1 tệp" in str(e.value)
    assert await pool.fetchval(
        "SELECT duyet_luc IS NOT NULL FROM service_order WHERE id = $1::uuid", order
    )
    kq = await HoanTacService(pool).thu_hoi_duyet_ket_qua(
        order_id=order, identity=ca.bac_si, xac_nhan=True, ly_do="Duyệt nhầm khách"
    )
    assert kq["tep_da_gui"] == 1
    assert (
        await pool.fetchval(
            "SELECT duyet_luc FROM service_order WHERE id = $1::uuid", order
        )
        is None
    )


# ── (e) Xếp phòng → huỷ xếp phòng (nút ở khối DoiPhong) ─────────────────────


async def test_xep_nham_phong_huy_xep_phong_ve_chua_xep(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    from clinicai.services.service_routing_service import ServiceRoutingService

    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    _con, order = await _kham_va_chi_dinh(pool, ca, visit)
    await _chon(pool, ca, visit, [order])
    await _thu(pool, visit, ca.thu_ngan)
    await chay_hanh_trinh(pool)
    d = await _don(pool, order)
    assert d["routing_status"] == "ASSIGNED"

    await ServiceRoutingService(pool).invalidate(
        order_id=order,
        expected_routing_revision=int(d["routing_revision"]),
        reason_code="ASSIGNED_BY_MISTAKE",
        identity=ca.thu_ngan,
        idempotency_key=_khoa(),
    )
    o = await pool.fetchrow(
        "SELECT routing_status, room_id FROM service_order WHERE id = $1::uuid", order
    )
    assert (o["routing_status"], o["room_id"]) == ("REASSIGNMENT_REQUIRED", None)
    assert "waiting" not in await _cho(pool, order)
