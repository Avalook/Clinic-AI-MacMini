"""Quầy thuốc bán theo đơn cũ (09/10/2026) — chạy thật trên DB.

Khách cũ mở lượt bán lẻ → thấy đơn gần nhất (kê / đã mua / còn lại / hẹn tái
khám) · "Bán theo đơn này" nối lượt + thêm dòng QUAY số còn lại, bấm lại không
thêm trùng · đã mua cộng cả lần thu ở lượt gốc lẫn lượt bán lẻ đã nối · hai lời
nhắc chỉ nhắc · gỡ nối khi chưa thu, đã thu thì không · Postgres chặn nối sai.
"""

# ruff: noqa: F811 — fixture `q` được IMPORT từ CP1.

from __future__ import annotations

import json
import uuid
from datetime import timedelta
from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.core.clock import hom_nay_vn
from clinicai.services import ban_theo_don_service as btd
from clinicai.services.ban_le_service import BanLeService
from clinicai.services.bill_service import tinh_hoa_don
from clinicai.services.payment_service import PaymentService
from clinicai.services.pharmacy_service import PharmacyService
from clinicai.services.quay_thuoc_service import QuayThuocService
from tests.services.test_luot_kham_service_db import CLINIC
from tests.services.test_tien_thuoc_cp1_db import Quay, _don, _thuoc, q  # noqa: F401

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest.fixture(autouse=True)
def _tat_kho_thuoc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "0")


async def _pid(q: Quay) -> str:
    return str(
        await q.pool.fetchval(
            "SELECT clinic_patient_id::text FROM visit WHERE visit_id = $1::uuid",
            q.visit_id,
        )
    )


async def _thu(q: Quay, vid: str) -> None:
    async with q.pool.acquire() as conn:
        hd = await tinh_hoa_don(conn, clinic_id=CLINIC, visit_id=vid, kind="thuoc")
    await PaymentService(q.pool).record_payment(
        visit_id=vid,
        kind="thuoc",
        amount=None,
        clinic_patient_id=None,
        identity=q.thu_ngan,
        bill_revision=hd.revision,
        method="CASH",
    )


async def _don_kho(q: Quay, so: int = 10) -> tuple[str, str]:
    """Đơn bác sĩ ở lượt gốc: một thuốc đã xác định thuốc kho, kê ``so`` viên."""
    drug = await _thuoc(q, gia=5_000, ten=f"Thuốc kho {uuid.uuid4().hex[:6]}")
    rx = await _don(q, so=so, ten="thuoc bac si go")
    await PharmacyService(q.pool).xac_dinh_thuoc(
        identity=q.duoc_si, prescription_id=rx, drug_catalog_id=drug
    )
    return drug, rx


async def _doc(q: Quay, vid: str) -> Any:
    """Đơn đang nối của lượt (không nối → đơn mới nhất) trong lịch sử đơn."""
    pid = await q.pool.fetchval(
        "SELECT clinic_patient_id::text FROM visit WHERE visit_id = $1::uuid", vid
    )
    ls = await BanLeService(q.pool).lich_su_don(
        clinic_patient_id=pid, trang=0, identity=q.thu_ngan
    )
    return next(
        (d for d in ls["don"] if d["da_noi"]), ls["don"][0] if ls["don"] else None
    )


async def _so_dong(q: Quay, vid: str) -> int:
    return int(
        await q.pool.fetchval(
            "SELECT count(*) FROM prescription WHERE visit_id = $1::uuid"
            " AND removed_at IS NULL",
            vid,
        )
    )


async def test_ban_theo_don_tu_dau_den_cuoi(q: Quay) -> None:
    drug, rx = await _don_kho(q, so=10)
    # Ở lượt gốc khách mua 4/10 rồi thu.
    await PharmacyService(q.pool).khai_so_luong_mua(
        identity=q.duoc_si, prescription_id=rx, so_luong=4
    )
    await _thu(q, q.visit_id)
    # Ngày hẹn tái khám trên phiếu của lượt gốc.
    await q.pool.execute(
        "INSERT INTO phieu_kham_luot (clinic_id, visit_id, form_id, version, du_lieu)"
        " VALUES ($1::uuid, $2::uuid, 'PK', 1, $3::jsonb)",
        CLINIC,
        q.visit_id,
        json.dumps({"pk_follow_date": {"nguon": "USER", "gia_tri": "2026-12-01"}}),
    )
    pid = await _pid(q)
    vid = (
        await BanLeService(q.pool).mo_luot(identity=q.thu_ngan, clinic_patient_id=pid)
    )["visit_id"]

    don = await _doc(q, vid)
    assert (don["visit_id"], don["da_noi"], don["ngay_hen"]) == (
        q.visit_id,
        False,
        "2026-12-01",
    )
    assert don["bac_si"] == q.bac_si.full_name
    assert don["ngay_kham"] == hom_nay_vn().isoformat()
    [d] = don["dong"]
    assert (d["drug_catalog_id"], d["ten_bac_si"]) == (drug, "thuoc bac si go")
    assert (d["so_ke"], d["da_mua"], d["con_lai"], d["vuot"]) == ("10", "4", "6", False)
    assert don["nhac"] == []

    # "Bán theo đơn này": nối + thêm dòng QUAY 6 viên.
    kq = await btd.noi_don(
        q.pool, q.thu_ngan, visit_id=vid, don_goc_visit_id=q.visit_id
    )
    assert (kq["so_dong_them"], kq["bo_qua"]) == (1, [])
    dong = await QuayThuocService(q.pool).doc(visit_id=vid, identity=q.thu_ngan)
    [quay] = dong["dong"]
    assert (quay["nguon"], quay["drug_catalog_id"], quay["so_ke"]) == (
        "QUAY",
        drug,
        "6",
    )
    # Bấm lại → không thêm trùng.
    kq = await btd.noi_don(
        q.pool, q.thu_ngan, visit_id=vid, don_goc_visit_id=q.visit_id
    )
    assert kq["so_dong_them"] == 0 and await _so_dong(q, vid) == 1
    don = await _doc(q, vid)
    assert don["da_noi"] is True
    assert (don["dong"][0]["dang_ban"], don["dong"][0]["vuot"]) == ("6", False)

    # Nhân viên sửa lên 8 → nhắc vượt (4 + 8 > 10), không chặn.
    await QuayThuocService(q.pool).doi_so_luong(
        prescription_id=quay["id"], so_luong="8", identity=q.thu_ngan
    )
    don = await _doc(q, vid)
    assert don["dong"][0]["vuot"] is True
    assert any("vượt số bác sĩ kê 10" in c for c in don["nhac"])

    # Hoàn tác: gỡ nối (dòng giữ nguyên), rồi nối lại.
    assert (await btd.go_noi_don(q.pool, q.thu_ngan, visit_id=vid))["da_go"] is True
    assert (await _doc(q, vid))["da_noi"] is False
    assert await _so_dong(q, vid) == 1
    assert (
        await q.pool.fetchval(
            "SELECT count(*) FROM event_log WHERE aggregate_id = $1"
            " AND event_type IN ('visit.ban_le_noi_don', 'visit.ban_le_go_don')",
            vid,
        )
        == 2
    )
    await btd.noi_don(q.pool, q.thu_ngan, visit_id=vid, don_goc_visit_id=q.visit_id)

    # Thu lượt bán lẻ → đã thu thì không gỡ nối / nối nữa.
    await _thu(q, vid)
    with pytest.raises(ConflictError):
        await btd.go_noi_don(q.pool, q.thu_ngan, visit_id=vid)
    # Lần mua sau: đã mua = 4 (lượt gốc) + 8 (lượt bán lẻ đã nối) = 12 → hết còn lại.
    vid2 = (
        await BanLeService(q.pool).mo_luot(identity=q.thu_ngan, clinic_patient_id=pid)
    )["visit_id"]
    assert vid2 != vid
    d = (await _doc(q, vid2))["dong"][0]
    assert (d["da_mua"], d["con_lai"], d["dang_ban"], d["vuot"]) == (
        "12",
        "0",
        "0",
        True,
    )
    kq = await btd.noi_don(
        q.pool, q.thu_ngan, visit_id=vid2, don_goc_visit_id=q.visit_id
    )
    assert kq["so_dong_them"] == 0 and "đã mua đủ" in kq["bo_qua"][0]


async def test_lich_su_don_moi_den_cu_theo_trang_va_nhac(
    q: Quay, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _don_kho(q, so=3)
    pid = await _pid(q)
    # Lượt khám CŨ hơn cũng có đơn → lịch sử có cả hai, mới → cũ.
    cu = await q.pool.fetchval(
        "INSERT INTO visit (clinic_id, clinic_patient_id, status, checked_in_at,"
        " created_at) VALUES ($1::uuid, $2::uuid, 'OPEN', now() - interval '40 days',"
        " now() - interval '40 days') RETURNING visit_id::text",
        CLINIC,
        pid,
    )
    await q.pool.execute(
        "INSERT INTO prescription (clinic_id, source_ref, visit_id, clinic_patient_id,"
        " drug_name_raw, quantity, quantity_num, unit)"
        " VALUES ($1::uuid, $2, $3::uuid, $4::uuid, 'thuoc cu', '2 viên', 2, 'viên')",
        CLINIC,
        f"test-rx-{uuid.uuid4().hex}",
        cu,
        pid,
    )
    vid = (
        await BanLeService(q.pool).mo_luot(identity=q.thu_ngan, clinic_patient_id=pid)
    )["visit_id"]
    svc = BanLeService(q.pool)
    ls = await svc.lich_su_don(clinic_patient_id=pid, trang=0, identity=q.duoc_si)
    assert [d["visit_id"] for d in ls["don"]] == [q.visit_id, cu]
    assert (ls["co_them"], ls["luot_mo"], ls["nhac_chung"]) == (False, vid, [])
    assert [d["ban_duoc"] for d in ls["don"]] == [True, True]
    # Theo trang (1 đơn/trang); trang rác → trang đầu.
    monkeypatch.setattr(btd, "DON_MOI_TRANG", 1)
    t0 = await svc.lich_su_don(clinic_patient_id=pid, trang="rác", identity=q.duoc_si)
    t1 = await svc.lich_su_don(clinic_patient_id=pid, trang="1", identity=q.duoc_si)
    assert ([d["visit_id"] for d in t0["don"]], t0["co_them"]) == ([q.visit_id], True)
    assert ([d["visit_id"] for d in t1["don"]], t1["co_them"]) == ([cu], False)
    monkeypatch.undo()
    # Nhắc 2 tháng là của KHÁCH — tính theo lần khám gần nhất (hôm nay).
    sau = btd.cong_thang(hom_nay_vn(), 2) + timedelta(days=1)
    async with q.pool.acquire() as conn:
        ls = await btd.lich_su_don(conn, q.thu_ngan, clinic_patient_id=pid, hom_nay=sau)
    assert any("quá 2 tháng" in c for c in ls["nhac_chung"])
    # Đơn không xác định thuốc kho → không thêm được, báo thêm tay.
    kq = await btd.noi_don(q.pool, q.thu_ngan, visit_id=vid, don_goc_visit_id=cu)
    assert kq["so_dong_them"] == 0 and "chưa xác định thuốc kho" in kq["bo_qua"][0]
    assert (await _doc(q, vid))["visit_id"] == cu  # đã nối → hiện đúng đơn đã nối
    ls = await svc.lich_su_don(clinic_patient_id=pid, trang=0, identity=q.duoc_si)
    assert [(d["da_noi"], d["ban_duoc"]) for d in ls["don"]] == [
        (False, False),
        (True, True),
    ]
    # Đang nối đơn khác → phải gỡ trước.
    with pytest.raises(ConflictError):
        await btd.noi_don(q.pool, q.thu_ngan, visit_id=vid, don_goc_visit_id=q.visit_id)


async def test_postgres_chan_noi_sai(q: Quay) -> None:
    await _don_kho(q)
    khac = await q.pool.fetchval(
        "INSERT INTO patient (clinic_id, patient_code, full_name, location_id)"
        " SELECT $1::uuid, $2, 'Khách khác', primary_location_id FROM staff"
        " WHERE id = $3::uuid RETURNING clinic_patient_id::text",
        CLINIC,
        f"BTD-{uuid.uuid4().hex[:8]}",
        q.thu_ngan.staff_id,
    )
    vid = (
        await BanLeService(q.pool).mo_luot(identity=q.thu_ngan, clinic_patient_id=khac)
    )["visit_id"]
    # Đơn của khách khác: service từ chối, Postgres cũng chặn.
    with pytest.raises(ValidationError):
        await btd.noi_don(q.pool, q.thu_ngan, visit_id=vid, don_goc_visit_id=q.visit_id)
    with pytest.raises(asyncpg.CheckViolationError):
        await q.pool.execute(
            "UPDATE visit SET don_goc_visit_id = $2::uuid WHERE visit_id = $1::uuid",
            vid,
            q.visit_id,
        )
    # Lượt khám thường không mang đơn gốc.
    with pytest.raises(asyncpg.CheckViolationError):
        await q.pool.execute(
            "UPDATE visit SET don_goc_visit_id = $2::uuid WHERE visit_id = $1::uuid",
            q.visit_id,
            vid,
        )
    # Khách chưa từng được kê đơn → không có đơn gần nhất.
    assert await _doc(q, vid) is None


async def test_chon_khach_thay_don_ngay_va_mo_theo_don_mot_giao_dich(q: Quay) -> None:
    drug, _rx = await _don_kho(q, so=10)
    pid = await _pid(q)
    svc = BanLeService(q.pool)

    async def so_luot_mo() -> int:
        return int(
            await q.pool.fetchval(
                "SELECT count(*) FROM visit WHERE clinic_patient_id = $1::uuid"
                " AND ban_le AND closed_at IS NULL",
                pid,
            )
        )

    # Chọn khách → đơn gần nhất hiện ngay, CHƯA mở lượt nào.
    don = (await svc.lich_su_don(clinic_patient_id=pid, trang=0, identity=q.duoc_si))[
        "don"
    ][0]
    assert (don["visit_id"], don["da_noi"]) == (q.visit_id, False)
    assert (don["dong"][0]["con_lai"], don["dong"][0]["dang_ban"]) == ("10", "0")
    assert await so_luot_mo() == 0

    # Đơn sai → lỗi ở bước nối, lượt vừa mở cũng huỷ theo: KHÔNG còn lượt mở nào.
    sai = str(uuid.uuid4())
    with pytest.raises(ValidationError):
        await svc.mo_theo_don(
            clinic_patient_id=pid, don_goc_visit_id=sai, identity=q.thu_ngan
        )
    assert await so_luot_mo() == 0

    # "Bán theo đơn này" từ khung chọn khách: mở lượt + nối + thêm dòng một lần.
    kq = await svc.mo_theo_don(
        clinic_patient_id=pid, don_goc_visit_id=q.visit_id, identity=q.thu_ngan
    )
    vid = kq["visit_id"]
    assert kq["so_dong_them"] == 1 and await so_luot_mo() == 1
    assert (
        await q.pool.fetchval(
            "SELECT don_goc_visit_id::text FROM visit WHERE visit_id = $1::uuid", vid
        )
        == q.visit_id
    )
    # Bấm lại → cùng lượt, không thêm dòng trùng.
    lai = await svc.mo_theo_don(
        clinic_patient_id=pid, don_goc_visit_id=q.visit_id, identity=q.thu_ngan
    )
    assert (lai["visit_id"], lai["so_dong_them"]) == (vid, 0)
    assert await _so_dong(q, vid) == 1
    # Chọn lại khách khi đang có lượt mở → đọc theo lượt ấy (đã nối, đang bán).
    don = (await svc.lich_su_don(clinic_patient_id=pid, trang=0, identity=q.duoc_si))[
        "don"
    ][0]
    assert don["da_noi"] is True
    assert (don["dong"][0]["drug_catalog_id"], don["dong"][0]["dang_ban"]) == (
        drug,
        "10",
    )
