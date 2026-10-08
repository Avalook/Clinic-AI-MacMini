"""Hành trình khách (Tuyền chốt 29/09/2026) trên DB thật.

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55620/postgres \\
        poetry run pytest src/tests/services/test_hanh_trinh_khach_db.py

Một buổi đủ qua service thật: check-in → đo sinh hiệu → khám + chỉ định 3 dịch
vụ (2 ở phòng siêu âm, 1 gửi đối tác) → thu tiền (tự xếp phòng) → phòng làm
xong một dịch vụ, đang làm dịch vụ thứ hai, đối tác đã lấy mẫu chờ kết quả →
check-out.
"""

from __future__ import annotations

import uuid

import asyncpg
import pytest

import clinicai.events.consumers.dong_thoi_gian  # noqa: F401 — đăng ký bên nhận
from clinicai.api.exceptions import NotFoundError
from clinicai.events.catalogue import DONG_THOI_GIAN_LUOT
from clinicai.services.chi_dinh_service import ChiDinhService
from clinicai.services.hanh_trinh_khach_service import (
    HanhTrinhKhachService,
    doc_hanh_trinh_khach,
)
from clinicai.services.lan_bac_si import noi_lam
from clinicai.services.luot_kham_service import LuotKhamService
from clinicai.services.service_execution_service import ServiceExecutionService
from tests.chay_nguoi_dua_tin import chay_ben_nhan, chay_hanh_trinh
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    NODE,
    _benh_nhan,
    _check_in,
    _chon,
    _don,
    _dung,
    _khoa,
    _thu,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _gia(pool: asyncpg.Pool, ten: str, node: str) -> str:  # noqa: F811
    ma = f"HTK-{uuid.uuid4().hex[:8]}"
    await pool.execute(
        'INSERT INTO service_price (clinic_id, service_code, name, "group",'
        " unit_price, node_code) VALUES ($1::uuid, $2, $3, 'dich_vu', 200000, $4)",
        CLINIC,
        ma,
        ten,
        node,
    )
    return ma


async def _bat_dau(pool: asyncpg.Pool, ca: object, order: str) -> str:  # noqa: F811
    d = await _don(pool, order)
    kq = await ServiceExecutionService(pool).bat_dau(
        order_id=order,
        expected_execution_revision=int(d["execution_revision"]),
        expected_routing_revision=int(d["routing_revision"]),
        identity=ca.dd,  # type: ignore[attr-defined]
        idempotency_key=_khoa(),
    )
    return str(kq["attempt_id"])


async def test_buoi_du_dang_o_tiep_theo_gio_tung_buoc_va_check_out(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    ngoai = await pool.fetchval(
        "SELECT code FROM node_definition WHERE clinic_id = $1::uuid"
        " AND lam_ben_ngoai LIMIT 1",
        CLINIC,
    )
    assert ngoai, "seed cần một node làm bên ngoài"
    ma_2 = await _gia(pool, "Siêu âm thứ hai", NODE)
    ma_dt = await _gia(pool, "HPV PCR đối tác", ngoai)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)

    # Đo sinh hiệu.
    await LuotKhamService(pool).bat_dau_do_sinh_hieu(visit_id=visit, identity=ca.dd)
    await LuotKhamService(pool).record_vitals(
        visit_id=visit,
        raw={"systolic": 120, "diastolic": 80},
        identity=ca.dd,
        idempotency_key=_khoa(),
    )
    await chay_hanh_trinh(pool)

    # Khám + chỉ định 3 dịch vụ, thu tiền → tự xếp phòng.
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
    kq = await ChiDinhService(pool).dat_chi_dinh(
        consultation_id=con,
        service_codes=[ca.ma_dv, ma_2, ma_dt],
        identity=ca.bac_si,
        idempotency_key=_khoa(),
    )
    o1, o2, o_dt = (str(x) for x in kq["order_ids"])
    await _chon(pool, ca, visit, [o1, o2, o_dt])
    await _thu(pool, visit, ca.le_tan)
    await chay_hanh_trinh(pool)
    await LuotKhamService(pool).kham_xong(consultation_id=con, identity=ca.bac_si)
    await chay_hanh_trinh(pool)

    # Phòng: làm xong o2, rồi đang làm o1.
    lan = await _bat_dau(pool, ca, o2)
    d2 = await _don(pool, o2)
    await ServiceExecutionService(pool).xong(
        order_id=o2,
        attempt_id=lan,
        expected_execution_revision=int(d2["execution_revision"]),
        identity=ca.dd,
        idempotency_key=_khoa(),
    )
    await chay_hanh_trinh(pool)
    await _bat_dau(pool, ca, o1)
    await chay_hanh_trinh(pool)
    # Đối tác: phòng khám đã lấy mẫu, chờ kết quả (không có phiếu kết quả).
    await pool.execute(
        "UPDATE service_order SET execution_status = 'COMPLETED',"
        " finished_at = now() WHERE id = $1::uuid",
        o_dt,
    )
    await chay_ben_nhan(pool, DONG_THOI_GIAN_LUOT)

    # Phòng dây H4 tự xếp cho o1 (DB thử dùng chung có thể có phòng cũ).
    # Phòng nhiều bác sĩ (DB chung, bài khác chạy song song có thể đặt lịch bác
    # sĩ vào phòng ấy): "đang ở" kèm bác sĩ quầy đã chọn — cùng hàm `noi_lam`.
    dong_phong = await pool.fetchrow(
        "SELECT r.name, s.full_name AS bac_si FROM service_order o"
        " JOIN clinic_room r ON r.id = o.room_id"
        " LEFT JOIN staff s ON s.id = o.bac_si_lam_id"
        " WHERE o.id = $1::uuid",
        o1,
    )
    ten_phong = noi_lam(dong_phong["name"], dong_phong["bac_si"])
    async with pool.acquire() as conn:
        ht = (
            await doc_hanh_trinh_khach(
                conn, clinic_id=CLINIC, visit_ids=[visit.upper()], kem_ai=True
            )
        )[visit]

    # ĐANG Ở: tên phòng thật, đang làm từ lúc phòng bắt đầu.
    o = ht["dang_o"]
    assert o["trang_thai"] == "DANG_O", o
    assert o["noi"] == ten_phong
    assert isinstance(o["tu_luc"], str)

    b = {x["ma"]: x for x in ht["buoc"]}
    assert b["CHECK_IN"]["trang_thai"] == "xong" and b["CHECK_IN"]["xong"]
    assert b["SINH_HIEU"]["trang_thai"] == "xong" and b["SINH_HIEU"]["xong"]
    kham = b["KHAM"]
    assert kham["trang_thai"] == "xong"
    assert kham["bat_dau"] and kham["xong"] and kham["so_chi_dinh"] == 3
    assert kham["thu_luc"], "giờ thu tiền"
    assert kham["nguoi_thu"], "người thu (sổ sự kiện)"
    the = {t["id"]: t for t in b["LAM_DV"]["dich_vu"]}
    assert the[o2]["trang_thai"] == "XONG"
    assert the[o2]["vao"] and the[o2]["bat_dau"] and the[o2]["xong"]
    assert the[o1]["trang_thai"] == "DANG_LAM"
    assert the[o1]["bat_dau"] and the[o1]["xong"] is None
    assert the[o_dt]["trang_thai"] == "DOI_TAC" and the[o_dt]["lay_mau"]
    assert b["LAM_DV"]["trang_thai"] == "dang"

    g = ht["gon"]
    assert (g["dv_xong"], g["dv_tong"]) == (1, 3)
    assert "KQ đối tác" in g["con_cho"]
    assert "dang" in g["doan"] and "doi_tac" in g["doan"]
    assert not g["xong_buoi"]
    # TIẾP THEO có chỗ để đi (quay lại bác sĩ / bước kế) — không rỗng khi
    # khách còn ở phòng khám.
    assert ht["tiep_theo"], ht["tiep_theo"]

    # Dạng gọn nhiều lượt: mã rác bỏ qua, không lỗi.
    svc = HanhTrinhKhachService(pool)
    gon = await svc.gon_nhieu_luot(luot=f"rác,{visit}, ,", identity=ca.le_tan)
    assert list(gon["luot"]) == [visit]
    assert (await svc.gon_nhieu_luot(luot="rác", identity=ca.le_tan)) == {"luot": {}}
    with pytest.raises(NotFoundError):
        await svc.mot_luot(visit_id="không-phải-mã", identity=ca.le_tan)
    with pytest.raises(NotFoundError):
        await svc.mot_luot(
            visit_id="00000000-0000-4000-8000-000000000000", identity=ca.le_tan
        )

    # CHECK-OUT = xong buổi: không còn "tiếp theo"; thanh đoạn đọc thẳng các
    # bước (02/10 — không ép xanh hết, cùng màu bên trong).
    await pool.execute(
        "UPDATE queue_entry SET status = 'done', done_at = now()"
        " WHERE visit_id = $1::uuid"
        " AND status IN ('blocked', 'waiting', 'called', 'serving')",
        visit,
    )
    await pool.execute(
        "UPDATE visit SET closed_at = now() WHERE visit_id = $1::uuid", visit
    )
    ve = await svc.mot_luot(visit_id=visit, identity=ca.le_tan)
    assert ve["gon"]["trang_thai"] == "DA_VE" and ve["gon"]["xong_buoi"]
    assert ve["gon"]["doan"][-1] == "xong", "đoạn Check-out xanh"
    assert len(ve["gon"]["doan"]) == len(ve["buoc"]) - 1 + len(
        {x["ma"]: x for x in ve["buoc"]}["LAM_DV"]["dich_vu"]
    ), "mỗi bước một đoạn, Làm dịch vụ mỗi thẻ một đoạn"
    assert ve["tiep_theo"] == []
    assert {x["ma"]: x for x in ve["buoc"]}["CHECK_OUT"]["trang_thai"] == "xong"
