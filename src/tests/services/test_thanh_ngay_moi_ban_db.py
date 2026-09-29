"""Thanh chọn ngày ở mọi bàn làm việc (Tuyền 29/09/2026).

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55670/postgres \\
        poetry run pytest src/tests/services/test_thanh_ngay_moi_ban_db.py

"Để bác sĩ hay BẤT KỲ AI quay lại ngày đó XEM VÀ SỬA": Đo sinh hiệu, Bàn khám
tư vấn, Bàn khám và mọi phòng dịch vụ chọn được một NGÀY CŨ. Bộ này đo trên
Postgres thật rằng:

  1. hàng tư vấn / hàng khám của ngày cũ trả đúng khách check-in ngày ấy (kể
     cả đã xong), hôm nay không lẫn khách hôm qua, ngày rác → hôm nay;
  2. bảng Đo sinh hiệu theo ngày cũ có lượt ấy, sửa lần đo được — lần mới nhất
     thắng, lần cũ còn trong sổ; ngày cũ không bày ô "bỏ qua tư vấn";
  3. phòng dịch vụ ngày cũ: Bắt đầu / Xong một chỉ định chưa làm được (ghi giờ
     thật lúc bấm), phiếu kết quả lưu + Hoàn tất + Sửa lại được;
  4. lượt khách về giữa chừng (INCOMPLETE) vẫn sửa được hết, có sổ sự kiện;
     FINALIZED (đã ký) vẫn khoá;
  5. công tắc `quyen_theo_lich` chỉ đòi ca cho việc của HÔM NAY;
  6. "Khách của tôi" ở Bàn khám ngày cũ theo lịch trực CỦA NGÀY ĐÓ.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import asyncpg
import pytest

from clinicai.core.clock import hom_nay_vn
from clinicai.services.form_engine_service import FormEngineService
from clinicai.services.luot_kham_doc import BangLuotKham
from clinicai.services.luot_kham_service import LuotKhamService
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    _nguoi,
    pool,
)
from tests.services.test_hanh_trinh_tu_van_db import (
    _check_in,
    _do_sinh_hieu,
    _hanh_trinh,
    _phien_tu_van,
)
from tests.services.test_service_execution_db import KB, kb  # noqa: F401
from tests.services.test_service_execution_db import _nguoi as _nguoi_vai
from tests.services.test_sua_ket_qua_db import _don as _don_ket_qua
from tests.services.test_sua_ket_qua_db import _nguoi as _nguoi_kq
from tests.services.test_sua_ket_qua_db import _phieu_v1, _sua

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


def _hom_qua() -> str:
    return (hom_nay_vn() - timedelta(days=1)).isoformat()


async def _lui_mot_ngay(pool: asyncpg.Pool, visit_id: str) -> None:  # noqa: F811
    """Lượt này check-in HÔM QUA (dời mốc check-in lùi 24 giờ)."""
    await pool.execute(
        "UPDATE visit SET checked_in_at = checked_in_at - interval '1 day'"
        " WHERE visit_id = $1::uuid",
        visit_id,
    )


def _co(ds: list[dict[str, Any]], visit_id: str) -> list[dict[str, Any]]:
    return [d for d in ds if d["visit_id"] == visit_id]


# ── 1–2. Tư vấn · Bàn khám · Đo sinh hiệu theo ngày cũ ─────────────────────


async def test_tu_van_ban_kham_sinh_hieu_ngay_cu(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    lan = await _check_in(pool, qua_tu_van=True)
    await _hanh_trinh(pool)
    await _do_sinh_hieu(pool, lan)
    await _hanh_trinh(pool)
    async with pool.acquire() as conn:
        bs_tu_van = await _nguoi(conn, lan.loc, "DOCTOR")
        dd = await _nguoi(conn, lan.loc, "NURSE_ULTRASOUND")
    svc = LuotKhamService(pool)
    tv = await _phien_tu_van(pool, lan.visit)
    await svc.start_consultation(consultation_id=tv, identity=bs_tu_van)
    await svc.xong_tu_van(consultation_id=tv, identity=bs_tu_van)
    await _hanh_trinh(pool)
    await _lui_mot_ngay(pool, lan.visit)
    hom_qua = _hom_qua()
    bang = BangLuotKham(pool)

    # Hàng TƯ VẤN của hôm qua: có chị (đã chuyển bác sĩ chính = done).
    cu = await bang.hang_cho(
        identity=bs_tu_van, room_id=None, tu_van=True, ngay=hom_qua
    )
    assert cu["hom_nay"] is False and cu["ngay"] == hom_qua
    [dong] = _co(cu["hang_cho"], lan.visit)
    assert dong["loai"] == "TU_VAN" and dong["trang_thai"] == "done"
    # Hôm nay không lẫn khách hôm qua; ngày rác = hôm nay, không ném.
    hn = await bang.hang_cho(identity=bs_tu_van, room_id=None, tu_van=True)
    assert not _co(hn["hang_cho"], lan.visit)
    rac = await bang.hang_cho(
        identity=bs_tu_van, room_id=None, tu_van=True, ngay="2026-99-99'; --"
    )
    assert rac["hom_nay"] is True and not _co(rac["hang_cho"], lan.visit)

    # BÀN KHÁM (bác sĩ chính, "khách của tôi") hôm qua: có chị; không "sắp tới".
    bk = await bang.hang_cho(identity=lan.bac_si, room_id=None, ngay=hom_qua)
    assert [d["loai"] for d in _co(bk["hang_cho"], lan.visit)] == ["KHAM"]
    assert bk["sap_toi"] == []
    bk_hn = await bang.hang_cho(identity=lan.bac_si, room_id=None)
    assert not _co(bk_hn["hang_cho"], lan.visit)

    # ĐO SINH HIỆU hôm qua: có lượt + số đo; ngày cũ không bày "bỏ qua tư vấn",
    # không tính phút chờ, không có lịch chờ check-in.
    sh = await bang.bang(identity=dd, ngay=hom_qua)
    assert sh["hom_nay"] is False and sh["ngay"] == hom_qua
    [luot] = _co(sh["luot"], lan.visit)
    assert luot["sinh_hieu"]["tam_thu"] == 118
    assert luot["tu_van"] is None and luot["cho_phut"] is None
    assert sh["lich_cho_check_in"] == []
    assert not _co((await bang.bang(identity=dd))["luot"], lan.visit)
    assert (await bang.bang(identity=dd, ngay="rác"))["hom_nay"] is True

    # SỬA lần đo của lượt hôm qua: lần mới nhất thắng, lần cũ còn trong sổ.
    await svc.record_vitals(
        visit_id=lan.visit, raw={"systolic": 131, "diastolic": 82}, identity=dd
    )
    [luot] = _co((await bang.bang(identity=dd, ngay=hom_qua))["luot"], lan.visit)
    assert luot["sinh_hieu"]["tam_thu"] == 131
    so_lan = await pool.fetchval(
        "SELECT count(*) FROM vital_measurement WHERE visit_id = $1::uuid",
        lan.visit,
    )
    assert so_lan == 2


async def test_bang_ngay_cu_hien_ca_luot_da_dong(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Ngày cũ lấy MỌI lượt check-in hôm đó — kể cả khách về giữa chừng
    (INCOMPLETE), thứ bảng hôm nay cố ý giấu."""
    lan = await _check_in(pool, qua_tu_van=False)
    await pool.execute(
        "UPDATE visit SET status = 'INCOMPLETE', incomplete_reason = 'Khách về',"
        " checked_in_at = checked_in_at - interval '1 day'"
        " WHERE visit_id = $1::uuid",
        lan.visit,
    )
    async with pool.acquire() as conn:
        dd = await _nguoi(conn, lan.loc, "NURSE_ULTRASOUND")
    bang = BangLuotKham(pool)
    assert _co((await bang.bang(identity=dd, ngay=_hom_qua()))["luot"], lan.visit)


# ── 3. Phòng dịch vụ ngày cũ: Bắt đầu / Xong + sửa kết quả ─────────────────


async def test_phong_dich_vu_ngay_cu_bat_dau_xong_duoc(kb: KB) -> None:  # noqa: F811
    await _lui_mot_ngay(kb.pool, kb.visit_id)
    hom_qua = _hom_qua()
    async with kb.pool.acquire() as conn:
        ql = await _nguoi_vai(conn, "MANAGEMENT")
    bang = BangLuotKham(kb.pool)
    cu = await bang.hang_cho(identity=ql, room_id=kb.room_id, ngay=hom_qua)
    assert cu["hom_nay"] is False
    assert [d["ref_id"] for d in _co(cu["hang_cho"], kb.visit_id)] == [kb.order_id]
    hn = await bang.hang_cho(identity=ql, room_id=kb.room_id)
    assert not _co(hn["hang_cho"], kb.visit_id)

    truoc = datetime.now(UTC)
    mo = await kb.svc.bat_dau(
        order_id=kb.order_id,
        expected_execution_revision=0,
        expected_routing_revision=1,
        identity=kb.bs,
        idempotency_key=str(uuid.uuid4()),
    )
    kq = await kb.svc.xong(
        order_id=kb.order_id,
        attempt_id=mo["attempt_id"],
        expected_execution_revision=mo["execution_revision"],
        identity=kb.bs,
        idempotency_key=str(uuid.uuid4()),
    )
    assert kq["execution_status"] == "COMPLETED"
    # GIỜ THẬT lúc bấm, không phải giờ của ngày cũ.
    bat_dau = await kb.pool.fetchval(
        "SELECT started_at FROM service_execution_attempt WHERE id = $1::uuid",
        mo["attempt_id"],
    )
    assert bat_dau >= truoc - timedelta(seconds=5)
    # Xong rồi vẫn nằm trong hàng chờ của ngày ấy (đã xong) để mở lại sửa.
    cu = await bang.hang_cho(identity=ql, room_id=kb.room_id, ngay=hom_qua)
    [dong] = _co(cu["hang_cho"], kb.visit_id)
    assert dong["trang_thai"] == "done"


async def test_sua_ket_qua_dich_vu_ngay_cu_luu_duoc(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    async with pool.acquire() as conn:
        bs = await _nguoi_kq(conn, "DOCTOR")
        oid, vid = await _don_ket_qua(conn, bs)
    await _lui_mot_ngay(pool, vid)
    svc = FormEngineService(pool)
    phieu_id = await _phieu_v1(svc, bs, oid)
    kq = await _sua(svc, pool, bs, phieu_id, "bản sửa ngày cũ")
    assert kq["la_lan_sua"] is True
    du_lieu = await pool.fetchval(
        "SELECT du_lieu->'ket_luan'->>'gia_tri' FROM form_instance WHERE id = $1::uuid",
        phieu_id,
    )
    assert du_lieu == "bản sửa ngày cũ"


# ── 4. Khách về giữa chừng (INCOMPLETE) vẫn sửa được; đã ký vẫn khoá ────────
#
# Tuyền chốt 29/09/2026: "ngày cũ sửa được hết, vì ai sửa gì cũng đã có lịch
# sử". FINALIZED (hồ sơ đã ký, TT13) giữ khoá.


async def _ve_giua_chung(pool: asyncpg.Pool, visit_id: str) -> None:  # noqa: F811
    """Khách về giữa chừng HÔM QUA: lượt INCOMPLETE, chỗ chờ còn mở → `left`
    (đúng như `checkout_service` làm)."""
    await pool.execute(
        "UPDATE queue_entry SET status = 'left', version = version + 1"
        " WHERE visit_id = $1::uuid"
        "   AND status IN ('blocked', 'waiting', 'called', 'serving')",
        visit_id,
    )
    await pool.execute(
        "UPDATE visit SET status = 'INCOMPLETE', incomplete_reason = 'Khách về',"
        " incomplete_at = now(), checked_in_at = checked_in_at - interval '1 day'"
        " WHERE visit_id = $1::uuid",
        visit_id,
    )


async def _bat_dau_kb(kb: KB) -> dict[str, Any]:  # noqa: F811
    return await kb.svc.bat_dau(
        order_id=kb.order_id,
        expected_execution_revision=0,
        expected_routing_revision=1,
        identity=kb.bs,
        idempotency_key=str(uuid.uuid4()),
    )


async def test_incomplete_phong_dich_vu_lam_duoc_va_co_so_su_kien(
    kb: KB,  # noqa: F811
) -> None:
    await _ve_giua_chung(kb.pool, kb.visit_id)
    async with kb.pool.acquire() as conn:
        ql = await _nguoi_vai(conn, "MANAGEMENT")
    bang = BangLuotKham(kb.pool)
    # Hàng chờ ngày cũ có dòng "khách đã về" để mở ra làm.
    cu = await bang.hang_cho(identity=ql, room_id=kb.room_id, ngay=_hom_qua())
    [dong] = _co(cu["hang_cho"], kb.visit_id)
    assert dong["trang_thai"] == "left" and dong["ref_id"] == kb.order_id

    mo = await _bat_dau_kb(kb)
    kq = await kb.svc.xong(
        order_id=kb.order_id,
        attempt_id=mo["attempt_id"],
        expected_execution_revision=mo["execution_revision"],
        identity=kb.bs,
        idempotency_key=str(uuid.uuid4()),
    )
    assert kq["execution_status"] == "COMPLETED"
    for ten in ("service.started", "service.completed"):
        assert await kb.pool.fetchval(
            "SELECT count(*) FROM domain_event WHERE aggregate_id = $1::uuid"
            " AND event_type = $2",
            kb.order_id,
            ten,
        ), ten
    trang_thai = await kb.pool.fetchval(
        "SELECT status FROM visit WHERE visit_id = $1::uuid", kb.visit_id
    )
    assert trang_thai == "INCOMPLETE"


async def test_incomplete_sinh_hieu_va_phieu_kham_sua_duoc(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    from clinicai.phieu_kham.khung import cac_o, dinh_nghia
    from clinicai.services.phieu_kham_service import PhieuKhamService, kiem_quyen_core

    lan = await _check_in(pool, qua_tu_van=False)
    await _hanh_trinh(pool)
    await _do_sinh_hieu(pool, lan)
    await _ve_giua_chung(pool, lan.visit)
    async with pool.acquire() as conn:
        dd = await _nguoi(conn, lan.loc, "NURSE_ULTRASOUND")

    # Sinh hiệu: lưu lại được, sổ sự kiện có hai lần.
    await LuotKhamService(pool).record_vitals(
        visit_id=lan.visit, raw={"systolic": 125, "diastolic": 80}, identity=dd
    )
    so_lan = await pool.fetchval(
        "SELECT count(*) FROM event_log WHERE aggregate_id = $1::uuid"
        " AND event_type = 'vitals.recorded'",
        lan.visit,
    )
    assert so_lan == 2
    # Bàn khám ngày cũ: dòng khám của khách đã về vẫn hiện để mở phiếu.
    bk = await BangLuotKham(pool).hang_cho(
        identity=lan.bac_si, room_id=None, ngay=_hom_qua()
    )
    assert [d["trang_thai"] for d in _co(bk["hang_cho"], lan.visit)] == ["left"]

    # Phiếu khám v5: tự lưu được (lịch sử sửa phiếu có sẵn).
    o = next(
        ma
        for ma, x in cac_o(dinh_nghia("PK")["khung"]).items()
        if x["kieu"] == "doan_van"
    )
    r = await PhieuKhamService(pool, kiem_quyen=kiem_quyen_core).luu_luot(
        visit_id=lan.visit,
        form_id="PK",
        du_lieu={o: {"gia_tri": "Ghi bù sau khi khách về", "nguon": "USER"}},
        expected_revision=0,
        identity=lan.bac_si,
    )
    assert r["revision"] == 1


async def test_incomplete_phieu_ket_qua_sua_duoc(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    async with pool.acquire() as conn:
        bs = await _nguoi_kq(conn, "DOCTOR")
        oid, vid = await _don_ket_qua(conn, bs)
    await _ve_giua_chung(pool, vid)
    svc = FormEngineService(pool)
    phieu_id = await _phieu_v1(svc, bs, oid)
    kq = await _sua(svc, pool, bs, phieu_id, "bản sửa khi khách đã về")
    assert kq["la_lan_sua"] is True


async def test_finalized_van_khoa(kb: KB) -> None:  # noqa: F811
    from clinicai.services.luot_kham_service import LuotKhamConflictError

    await kb.pool.execute(
        "UPDATE visit SET status = 'FINALIZED', finalized_at = now(),"
        " finalized_by = $2::uuid WHERE visit_id = $1::uuid",
        kb.visit_id,
        kb.bs.staff_id,
    )
    with pytest.raises(LuotKhamConflictError, match="đã đóng"):
        await _bat_dau_kb(kb)


# ── 5. Quyền theo lịch chỉ áp cho HÔM NAY ──────────────────────────────────


async def test_quyen_theo_lich_ngay_cu_khong_doi_ca(kb: KB) -> None:  # noqa: F811
    from clinicai.core.exceptions import SafetyGateError
    from tests.services.test_service_execution_db import _dat_day_lich

    await _dat_day_lich(kb, True)
    try:
        # Hôm nay, không có ca ở phòng → chặn (luật cũ giữ nguyên).
        with pytest.raises(SafetyGateError):
            await _bat_dau_kb(kb)
        # Cùng chỉ định nhưng lượt check-in HÔM QUA → có lego là làm được.
        await _lui_mot_ngay(kb.pool, kb.visit_id)
        mo = await _bat_dau_kb(kb)
        assert mo["attempt_no"] == 1
    finally:
        await _dat_day_lich(kb, False)


# ── 6. "Khách của tôi" ngày cũ theo lịch CỦA NGÀY ĐÓ ───────────────────────


async def _xep_hom_qua(
    pool: asyncpg.Pool,  # noqa: F811
    ma_vi_tri: str,
    staff_id: str,
) -> None:
    await pool.execute(
        "INSERT INTO work_roster (clinic_id, week_start, work_date, shift, station,"
        " staff_id, staff_name, status)"
        " SELECT $1::uuid, d - (extract(isodow FROM d)::int - 1), d, 'FULL', $2,"
        " $3::uuid, 'Test', 'APPROVED'"
        " FROM (SELECT (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date - 1 AS d) x",
        CLINIC,
        ma_vi_tri,
        staff_id,
    )


async def test_khach_cua_toi_ngay_cu_theo_lich_ngay_do(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    from clinicai.permissions.lich import bac_si_cung_phong_hom_nay

    # Chị Lan là khách của bác sĩ B, check-in hôm qua.
    lan = await _check_in(pool, qua_tu_van=False)
    await _hanh_trinh(pool)
    await _lui_mot_ngay(pool, lan.visit)
    async with pool.acquire() as conn:
        bs_a = await _nguoi(conn, lan.loc, "DOCTOR")
    bang = BangLuotKham(pool)
    hom_qua = _hom_qua()
    # Chưa có lịch hôm qua: bác sĩ A chỉ thấy khách của chính mình.
    truoc = await bang.hang_cho(identity=bs_a, room_id=None, ngay=hom_qua)
    assert not _co(truoc["hang_cho"], lan.visit)

    # Lịch HÔM QUA: A và B đứng cùng một phòng → A thấy khách của B hôm ấy.
    room = await pool.fetchval(
        "SELECT id::text FROM clinic_room WHERE clinic_id = $1::uuid"
        " ORDER BY created_at, id LIMIT 1",
        CLINIC,
    )
    ma = f"T-NGAY-{uuid.uuid4().hex[:8]}"
    await pool.execute(
        "INSERT INTO vi_tri_lam_viec (clinic_id, code, ten, nhom_nghe, room_id)"
        " VALUES ($1::uuid, $2, 'Vị trí test', 'BAC_SI', $3::uuid)",
        CLINIC,
        ma,
        room,
    )
    await _xep_hom_qua(pool, ma, bs_a.staff_id)
    await _xep_hom_qua(pool, ma, lan.bac_si.staff_id)
    sau = await bang.hang_cho(identity=bs_a, room_id=None, ngay=hom_qua)
    assert [d["loai"] for d in _co(sau["hang_cho"], lan.visit)] == ["KHAM"]
    # Lịch hôm qua không lan sang hôm nay.
    async with pool.acquire() as conn:
        assert await bac_si_cung_phong_hom_nay(conn, CLINIC, bs_a.staff_id) == []
