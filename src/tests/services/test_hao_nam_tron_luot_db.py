"""CỔNG NGHIỆM THU Hào Nam (08/10/2026): một lượt khám TRỌN VẸN ở cơ sở mới.

    scripts/test-nhanh.sh src/tests/services/test_hao_nam_tron_luot_db.py

Dựng Kim Ngưu giống prod (phòng tiếp đón LUOTKHAM-01/14, đo sinh hiệu
LUOTKHAM-03, tư vấn LUOTKHAM-02, bác sĩ KHAM-*, siêu âm DICHVU-SIEUAM, quầy
thuốc THUOC-04, một lô thuốc ở kho KN), chạy lõi `scripts/nhan-ban-co-so.py`
`--that --chep-kho` (bộ A), rồi đi hết một lượt bằng danh tính đứng ở Hào Nam:
đặt lịch → check-in → trạm đầu → khám + chỉ định → thu tiền → tự xếp phòng →
kê thuốc → chọn lô (lô KN bị từ chối) → thu tiền thuốc → giao thuốc. Cuối cùng:
KHÔNG một dòng nào của lượt trỏ phòng hay lô thuốc của Kim Ngưu.

Chạy trên phòng khám seed (như các bài lượt khám khác — cấu hình luồng của seed
là thứ một lượt cần). Xong thì `--go` tắt Hào Nam, trả giờ mở cửa về như cũ.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import importlib.util
import json
import sys
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from types import ModuleType

import asyncpg
import pytest
import pytest_asyncio

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.core.clock import CLINIC_TZ
from clinicai.services.bill_service import tinh_hoa_don
from clinicai.services.booking_service import BookingService
from clinicai.services.chi_dinh_service import ChiDinhService
from clinicai.services.luot_kham_service import LuotKhamService
from clinicai.services.payment_service import PaymentService
from clinicai.services.pharmacy_service import LO_KHAC_CO_SO, PharmacyService
from clinicai.services.service_selection_service import (
    ServiceSelectionService,
    cho_khach_quyet,
)
from tests.chay_nguoi_dua_tin import chay_hanh_trinh
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    _nguoi,
    pool,
)

pytestmark = [pytest.mark.db]

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "nhan-ban-co-so.py"


def _nap() -> ModuleType:
    spec = importlib.util.spec_from_file_location("nhan_ban_co_so", _SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["nhan_ban_co_so"] = mod
    spec.loader.exec_module(mod)
    return mod


NB = _nap()

KHAM = ["KHAM-NOITIET", "KHAM-PHUKHOA", "KHAM-SANKHOA", "KHAM-NAMKHOA"]
# Phòng KN theo bảng phòng prod: (tên mã sau 'KN-', các việc — việc đầu là chính)
PHONG_KN: list[tuple[str, list[str]]] = [
    ("TIEPDON", ["LUOTKHAM-01", "LUOTKHAM-14"]),
    ("DOCHISO", ["LUOTKHAM-03"]),
    ("TUVAN", ["LUOTKHAM-02"]),
    ("NOITIET", KHAM),
    ("SA1", ["DICHVU-SIEUAM"]),
    ("QUAYTHUOC", ["THUOC-04", "DICHVU-THUOC"]),
]


@dataclasses.dataclass
class HaoNam:
    kn: str
    hn: str
    duoi: str
    loai_kham: str
    ma_dv: str
    thuoc: str
    lo_kn: str
    lo_hn: str
    le_tan: StaffIdentity
    thu_ngan: StaffIdentity
    bac_si: StaffIdentity
    duoc_si: StaffIdentity


def _khoa() -> str:
    return f"hao-nam-{uuid.uuid4().hex}"


@pytest.fixture(autouse=True)
def _kho_bat_buoc(monkeypatch: pytest.MonkeyPatch) -> None:
    # Thu tiền thuốc đòi đủ lô — đúng chế độ prod (CP3).
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "1")


@pytest_asyncio.fixture
async def mo_ca_ngay(pool: asyncpg.Pool) -> AsyncIterator[None]:  # noqa: F811
    """Giờ mở cửa + ca phủ cả ngày: bài kiểm không phụ thuộc giờ chạy."""
    cu = await pool.fetchval("SELECT settings FROM clinic WHERE id = $1::uuid", CLINIC)
    await pool.execute(
        "UPDATE clinic SET settings = settings"
        " || jsonb_build_object('ca_lam_viec', $2::jsonb)"
        " || jsonb_build_object('hours', (SELECT jsonb_object_agg(k, $3::jsonb)"
        "    FROM jsonb_object_keys(settings -> 'hours') k))"
        " WHERE id = $1::uuid",
        CLINIC,
        json.dumps(
            {
                "SANG": {"bat_dau": "00:00", "ket_thuc": "08:00"},
                "CHIEU": {"bat_dau": "08:00", "ket_thuc": "16:00"},
                "TOI": {"bat_dau": "16:00", "ket_thuc": "23:59"},
            }
        ),
        json.dumps({"open": "00:00", "close": "23:59"}),
    )
    try:
        yield
    finally:
        await pool.execute(
            "UPDATE clinic SET settings = $2::jsonb WHERE id = $1::uuid", CLINIC, cu
        )


async def _dung_kim_nguu(conn: asyncpg.Connection, kn: str, duoi: str) -> str:
    """Phòng KN cho từng bước của một lượt + giá khám / siêu âm. Trả mã dịch vụ."""
    ma_dv = f"SA-HN-{duoi}"
    await conn.execute(
        'INSERT INTO service_price (clinic_id, service_code, name, "group",'
        " unit_price, node_code) VALUES ($1::uuid, $2, $3, 'dich_vu', 300000,"
        " 'DICHVU-SIEUAM')",
        CLINIC,
        ma_dv,
        f"Siêu âm Hào Nam {duoi}",
    )
    for i, (ten, viec) in enumerate(PHONG_KN):
        rid = await conn.fetchval(
            "INSERT INTO clinic_room (clinic_id, location_id, code, name, node_code,"
            " floor, sort, is_active, accepting, show_on_tv)"
            " VALUES ($1::uuid, $2::uuid, $3, $4, $5, 'Tầng 1', $6, true, true, true)"
            " RETURNING id::text",
            CLINIC,
            kn,
            f"KN-{ten}-{duoi}",
            f"{ten} thử {duoi}",
            viec[0],
            -1000 + i,  # đứng trước phòng thử của bài khác trong cùng DB
        )
        for v in viec:
            await conn.execute(
                "INSERT INTO clinic_room_node (clinic_id, room_id, node_code)"
                " VALUES ($1::uuid, $2::uuid, $3)",
                CLINIC,
                rid,
                v,
            )
        if ten == "SA1":
            await conn.execute(
                "INSERT INTO clinic_room_service (clinic_id, room_id, service_code)"
                " VALUES ($1::uuid, $2::uuid, $3)",
                CLINIC,
                rid,
                ma_dv,
            )
    return ma_dv


@pytest_asyncio.fixture
async def hao_nam(
    pool: asyncpg.Pool,  # noqa: F811
    mo_ca_ngay: None,
) -> AsyncIterator[HaoNam]:
    duoi = uuid.uuid4().hex[:8]
    async with pool.acquire() as conn:
        kn = str(
            await conn.fetchval(
                "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid"
                " AND code = 'KN'",
                CLINIC,
            )
        )
        ma_dv = await _dung_kim_nguu(conn, kn, duoi)
        ten_kham = f"Khám Hào Nam {duoi}"
        loai_kham = str(
            await conn.fetchval(
                "INSERT INTO service_type (clinic_id, code, name, is_active)"
                " VALUES ($1::uuid, $2, $3, true) RETURNING id::text",
                CLINIC,
                f"KHN-{duoi}",
                ten_kham,
            )
        )
        await conn.execute(
            'INSERT INTO service_price (clinic_id, service_code, name, "group",'
            " unit_price) VALUES ($1::uuid, $2, $3, 'dich_vu', 150000)",
            CLINIC,
            f"GKHN-{duoi}",
            ten_kham,
        )
        thuoc = str(
            await conn.fetchval(
                "INSERT INTO drug_catalog (clinic_id, name_base, name_raw, unit_price)"
                " VALUES ($1::uuid, $2, $2, 5000) RETURNING id::text",
                CLINIC,
                f"Thuốc Hào Nam {duoi}",
            )
        )
        duoc_si_kn = await _nguoi(conn, kn, "PHARMACIST")
        # Script ghi người thao tác (sổ kho, thu hồi quyền) = một quản lý đang bật.
        await _nguoi(conn, kn, "MANAGEMENT")
    ma_lo = f"LO-HN-{duoi}"
    lo_kn = str(
        (
            await PharmacyService(pool).nhap_lo(
                identity=duoc_si_kn,
                drug_catalog_id=thuoc,
                so_luong=40,
                batch_code=ma_lo,
                expiry_date=dt.date(2099, 12, 31),
                unit="viên",
            )
        )["drug_batch_id"]
    )

    # Nhân bản: bộ A + chép kho, ghi thật.
    async with pool.acquire() as conn:
        bc = await NB.chay(conn, clinic_id=CLINIC, that=True, chep_kho=True)
    assert bc.bo == "A"
    hn = str(
        await pool.fetchval(
            "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid"
            " AND code = 'HN' AND is_active",
            CLINIC,
        )
    )
    lo_hn = str(
        await pool.fetchval(
            "SELECT id::text FROM drug_batch WHERE location_id = $1::uuid"
            " AND batch_code = $2",
            hn,
            ma_lo,
        )
    )
    async with pool.acquire() as conn:
        o_hn = HaoNam(
            kn=kn,
            hn=hn,
            duoi=duoi,
            loai_kham=loai_kham,
            ma_dv=ma_dv,
            thuoc=thuoc,
            lo_kn=lo_kn,
            lo_hn=lo_hn,
            le_tan=await _nguoi(conn, hn, "RECEPTION"),
            thu_ngan=await _nguoi(conn, hn, "CASHIER"),
            bac_si=await _nguoi(conn, hn, "DOCTOR"),
            duoc_si=await _nguoi(conn, hn, "PHARMACIST"),
        )
    try:
        yield o_hn
    finally:
        # Tắt Hào Nam (không xoá) — bài khác trong cùng DB thấy lại một cơ sở.
        async with pool.acquire() as conn:
            await NB.chay(conn, clinic_id=CLINIC, viec="go", that=True)


async def _phong_cua(pool: asyncpg.Pool, room_id: str | None) -> str | None:  # noqa: F811
    if room_id is None:
        return None
    loc = await pool.fetchval(
        "SELECT location_id::text FROM clinic_room WHERE id = $1::uuid", room_id
    )
    return None if loc is None else str(loc)


async def _dat_lich_va_check_in(pool: asyncpg.Pool, h: HaoNam) -> tuple[str, str]:  # noqa: F811
    pid = str(
        await pool.fetchval(
            "INSERT INTO patient (clinic_id, patient_code, full_name, location_id)"
            " VALUES ($1::uuid, $2, 'Chị Hà Hào Nam', $3::uuid)"
            " RETURNING clinic_patient_id::text",
            CLINIC,
            f"HN-{h.duoi}",
            h.hn,
        )
    )
    bd = dt.datetime.now(CLINIC_TZ).replace(second=0, microsecond=0)
    bd = bd - dt.timedelta(minutes=bd.minute % 15)
    svc = BookingService(pool)
    for lan in range(16):
        try:
            kq = await svc.create(
                clinic_patient_id=pid,
                service_type_id=h.loai_kham,
                location_id=None,  # = cơ sở của người đặt (Hào Nam)
                slot_start=bd + dt.timedelta(minutes=15 * lan),
                slot_end=bd + dt.timedelta(minutes=15 * lan + 15),
                identity=h.le_tan,
                doctor_id=h.bac_si.staff_id,
            )
            break
        except ConflictError:
            continue
    else:
        pytest.fail("không còn khung nào trong 4 giờ tới")
    appt = str(kq.get("id") or kq.get("appointment_id") or kq["appointment"]["id"])
    assert (
        await pool.fetchval(
            "SELECT location_id::text FROM appointment WHERE id = $1::uuid", appt
        )
        == h.hn
    )
    await svc.apply_action(appointment_id=appt, action="checkin", identity=h.le_tan)
    await chay_hanh_trinh(pool)
    vid = await pool.fetchval(
        "SELECT visit_id::text FROM visit WHERE appointment_id = $1::uuid", appt
    )
    assert vid is not None
    return str(vid), appt


async def test_mot_luot_tron_ven_o_hao_nam(
    pool: asyncpg.Pool,  # noqa: F811
    hao_nam: HaoNam,
) -> None:
    h = hao_nam
    vid, _appt = await _dat_lich_va_check_in(pool, h)

    # Check-in: lượt mang cơ sở Hào Nam, trạm đầu là phòng Hào Nam.
    visit = await pool.fetchrow(
        "SELECT location_id::text AS loc, current_room_id::text AS phong"
        " FROM visit WHERE visit_id = $1::uuid",
        vid,
    )
    assert visit["loc"] == h.hn
    assert visit["phong"] is not None, "check-in không đặt khách vào trạm nào"
    assert await _phong_cua(pool, visit["phong"]) == h.hn

    # Khám + chỉ định siêu âm.
    con = str(
        await pool.fetchval(
            "SELECT id::text FROM consultation WHERE visit_id = $1::uuid"
            " AND kind = 'PRIMARY'",
            vid,
        )
    )
    await LuotKhamService(pool).start_consultation(
        consultation_id=con, identity=h.bac_si
    )
    order = str(
        (
            await ChiDinhService(pool).dat_chi_dinh(
                consultation_id=con,
                service_codes=[h.ma_dv],
                identity=h.bac_si,
                idempotency_key=_khoa(),
            )
        )["order_ids"][0]
    )
    async with pool.acquire() as conn:
        cho = (await cho_khach_quyet(conn, CLINIC, [vid]))[vid]
    await ServiceSelectionService(pool).confirm(
        visit_id=vid,
        order_ids_seen=[c["id"] for c in cho["chi_dinh"]],
        selected_order_ids=[order],
        expected_selection_revision=int(cho["revision"]),
        identity=h.le_tan,
        idempotency_key=_khoa(),
    )

    # Thu tiền dịch vụ ở quầy Hào Nam → hành trình tự xếp phòng siêu âm HN.
    await PaymentService(pool).record_payment(
        visit_id=vid,
        kind="dich_vu",
        amount=None,
        clinic_patient_id=None,
        identity=h.thu_ngan,
        idempotency_key=_khoa(),
    )
    await chay_hanh_trinh(pool)
    don = await pool.fetchrow(
        "SELECT routing_status, room_id::text AS room_id FROM service_order"
        " WHERE id = $1::uuid",
        order,
    )
    assert don["routing_status"] == "ASSIGNED", dict(don)
    assert await _phong_cua(pool, don["room_id"]) == h.hn
    await LuotKhamService(pool).kham_xong(consultation_id=con, identity=h.bac_si)

    # Thuốc: kê → xác định thuốc → chọn lô. Lô KN bị từ chối, lô HN đi qua.
    rx = str(
        await pool.fetchval(
            "INSERT INTO prescription (clinic_id, source_ref, visit_id,"
            " clinic_patient_id, drug_name_raw, quantity, quantity_num, unit)"
            " SELECT $1::uuid, $2, v.visit_id, v.clinic_patient_id, 'thuốc HN',"
            " '5 viên', 5, 'viên' FROM visit v WHERE v.visit_id = $3::uuid"
            " RETURNING id::text",
            CLINIC,
            f"test-rx-{uuid.uuid4().hex}",
            vid,
        )
    )
    nha_thuoc = PharmacyService(pool)
    await nha_thuoc.xac_dinh_thuoc(
        identity=h.duoc_si, prescription_id=rx, drug_catalog_id=h.thuoc
    )
    with pytest.raises(ValidationError) as loi:
        await nha_thuoc.phan_lo(
            identity=h.duoc_si, prescription_id=rx, drug_batch_id=h.lo_kn, so_luong=5
        )
    assert loi.value.message == LO_KHAC_CO_SO
    await nha_thuoc.phan_lo(
        identity=h.duoc_si, prescription_id=rx, drug_batch_id=h.lo_hn, so_luong=5
    )
    async with pool.acquire() as conn:
        hd = await tinh_hoa_don(conn, clinic_id=CLINIC, visit_id=vid, kind="thuoc")
    await PaymentService(pool).record_payment(
        visit_id=vid,
        kind="thuoc",
        idempotency_key=_khoa(),
        amount=None,
        clinic_patient_id=None,
        identity=h.thu_ngan,
        bill_revision=hd.revision,
        method="CASH",
    )
    await nha_thuoc.cap_phat(
        identity=h.duoc_si, prescription_id=rx, drug_batch_id=h.lo_hn, so_luong=5
    )
    ton = await pool.fetch(
        "SELECT id::text, quantity_on_hand FROM drug_batch WHERE id = ANY($1::uuid[])",
        [h.lo_kn, h.lo_hn],
    )
    assert {r["id"]: int(r["quantity_on_hand"]) for r in ton} == {
        h.lo_kn: 40,
        h.lo_hn: 35,
    }

    # CUỐI: không một dòng nào của lượt trỏ phòng / lô Kim Ngưu.
    phong_cua_luot = await pool.fetch(
        """
        SELECT 'visit' AS bang, current_room_id AS room_id FROM visit
         WHERE visit_id = $1::uuid
        UNION ALL SELECT 'work_item', room_id FROM work_item WHERE visit_id = $1::uuid
        UNION ALL SELECT 'service_order', room_id FROM service_order
         WHERE visit_id = $1::uuid
        UNION ALL SELECT 'service_order.du_kien', phong_du_kien_id FROM service_order
         WHERE visit_id = $1::uuid
        UNION ALL SELECT 'queue_entry', room_id FROM queue_entry
         WHERE visit_id = $1::uuid
        """,
        vid,
    )
    co_phong = [r for r in phong_cua_luot if r["room_id"] is not None]
    assert co_phong, "lượt không có dòng nào gắn phòng — bài kiểm không đo gì"
    sai = [
        (r["bang"], str(r["room_id"]))
        for r in co_phong
        if await _phong_cua(pool, str(r["room_id"])) != h.hn
    ]
    assert sai == [], f"dòng của lượt trỏ phòng ngoài Hào Nam: {sai}"

    lo_cua_luot = await pool.fetch(
        """
        SELECT 'allocation' AS bang, a.drug_batch_id FROM prescription_allocation a
         WHERE a.visit_id = $1::uuid
        UNION ALL
        SELECT 'inventory_txn', t.drug_batch_id FROM inventory_txn t
         WHERE t.ref_id = ANY(SELECT id FROM prescription WHERE visit_id = $1::uuid)
            OR t.payment_cycle_id IN (SELECT payment_cycle_id FROM payment_cycle
                                       WHERE visit_id = $1::uuid)
        """,
        vid,
    )
    assert {r["bang"] for r in lo_cua_luot} >= {"allocation", "inventory_txn"}
    assert {str(r["drug_batch_id"]) for r in lo_cua_luot} == {h.lo_hn}
