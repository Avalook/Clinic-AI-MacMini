"""Đổi cơ sở thì mọi màn danh sách vận hành chỉ hiện khách của cơ sở đó (nhóm C).

    scripts/test-nhanh.sh src/tests/services/test_loc_co_so_nhom_c_db.py

Tuyền 08/10/2026: *"sang cơ sở khác là của cơ sở đó hết, đừng sót"*. Cơ sở của
người xem = ``identity.location_id`` (header X-Location-ID); cơ sở của lượt =
``coalesce(visit.location_id, appointment.location_id)``.

Một bác sĩ, hai danh tính chỉ khác cơ sở (như bấm đổi cơ sở trên thanh trên):
không lọc thì cả hai danh tính thấy cả hai lượt, nên mỗi khẳng định "không thấy"
dưới đây đo đúng bộ lọc cơ sở, không đo bộ lọc bác sĩ / quyền. Cơ sở thứ hai
tạo riêng cho bài (is_active = false — cơ sở đang mở thứ hai đổi hành vi tự gán
cơ sở của bài khác chạy song song); đọc danh sách không xét is_active.
"""

from __future__ import annotations

import dataclasses
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import asyncpg
import pytest

from clinicai.api.identity import StaffIdentity
from clinicai.services.luot_kham_doc import BangLuotKham
from clinicai.services.luot_kham_service import LuotKhamService
from clinicai.services.service_routing_service import co_so_cua_luot
from clinicai.services.ultrasound_board_service import UltrasoundBoardService
from clinicai.services.work_item_service import WorkItemService
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    Ca,
    _benh_nhan,
    _check_in,
    _dung,
    _kham_va_chi_dinh,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


def _o(ai: StaffIdentity, loc: str) -> StaffIdentity:
    return dataclasses.replace(ai, location_id=loc, location_name="Cơ sở C thử")


@dataclasses.dataclass
class HaiCoSo:
    a: Ca
    b: Ca
    luot_a: str
    luot_b: str
    don_a: str
    don_b: str


async def _hai_co_so(pool: asyncpg.Pool) -> HaiCoSo:  # noqa: F811
    a = await _dung(pool)
    loc_b = str(
        await pool.fetchval(
            "INSERT INTO clinic_location (clinic_id, code, name, is_active)"
            " VALUES ($1::uuid, $2, 'Cơ sở C thử', false) RETURNING id::text",
            CLINIC,
            f"C{uuid.uuid4().hex[:6]}",
        )
    )
    b = dataclasses.replace(
        a,
        loc=loc_b,
        le_tan=_o(a.le_tan, loc_b),
        thu_ngan=_o(a.thu_ngan, loc_b),
        bac_si=_o(a.bac_si, loc_b),
        dd=_o(a.dd, loc_b),
    )
    # Check-in THẬT ở mỗi cơ sở (A trước B): có work_item, queue_entry, phiên.
    luot_a = await _check_in(pool, a, await _benh_nhan(pool, a), a.loai_kham)
    luot_b = await _check_in(pool, b, await _benh_nhan(pool, b), b.loai_kham)
    async with pool.acquire() as conn:
        assert await co_so_cua_luot(conn, CLINIC, visit_id=luot_a) == a.loc
        assert await co_so_cua_luot(conn, CLINIC, visit_id=luot_b) == loc_b
    _, don_a = await _kham_va_chi_dinh(pool, a, luot_a)
    _, don_b = await _kham_va_chi_dinh(pool, b, luot_b)
    return HaiCoSo(a, b, luot_a, luot_b, don_a, don_b)


async def _viec_moi(pool: asyncpg.Pool, node: str, luot: str | None) -> str:  # noqa: F811
    """Một việc PENDING ở `node` (bản node hiện hành); `luot` None = việc khu
    vận hành không gắn lượt / lịch (OPS-*)."""
    return str(
        await pool.fetchval(
            "INSERT INTO work_item (clinic_id, node_code, node_version_id,"
            " clinic_patient_id, visit_id, appointment_id, status)"
            " SELECT n.clinic_id, n.code, nv.id, v.clinic_patient_id, v.visit_id,"
            "        v.appointment_id, 'PENDING'"
            "   FROM node_definition n"
            "   JOIN node_definition_version nv"
            "     ON nv.node_definition_id = n.id AND nv.version = n.current_version"
            "    AND nv.clinic_id = n.clinic_id"
            "   LEFT JOIN visit v ON v.visit_id = $3::uuid"
            "  WHERE n.clinic_id = $1::uuid AND n.code = $2"
            " RETURNING id::text",
            CLINIC,
            node,
            luot,
        )
    )


def _ids(ds: list[dict[str, Any]], khoa: str = "visit_id") -> set[str]:
    return {str(d[khoa]) for d in ds}


async def test_bang_luot_va_lich_cho_check_in_theo_co_so(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    h = await _hai_co_so(pool)
    # Lịch hẹn hôm nay chưa check-in, mỗi cơ sở một cái.
    lich: dict[str, str] = {}
    bd = datetime.now(UTC) + timedelta(minutes=1)
    for ca in (h.a, h.b):
        lich[ca.loc] = str(
            await pool.fetchval(
                "INSERT INTO appointment (clinic_id, clinic_patient_id, location_id,"
                " service_type_id, slot_start, slot_end, status)"
                " VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5, $6,"
                " 'CONFIRMED') RETURNING id::text",
                CLINIC,
                await _benh_nhan(pool, ca),
                ca.loc,
                ca.loai_kham,
                bd,
                bd + timedelta(minutes=15),
            )
        )
    for ca, cua_minh, cua_nguoi in (
        (h.a, h.luot_a, h.luot_b),
        (h.b, h.luot_b, h.luot_a),
    ):
        kq = await BangLuotKham(pool).bang(identity=ca.le_tan)
        luot = _ids(kq["luot"])
        assert cua_minh in luot and cua_nguoi not in luot
        hen = _ids(kq["lich_cho_check_in"], "id")
        khac = h.b.loc if ca is h.a else h.a.loc
        assert lich[ca.loc] in hen and lich[khac] not in hen
    # Danh tính không mang cơ sở (rỗng) = không lọc: thấy cả hai.
    kq = await BangLuotKham(pool).bang(identity=_o(h.a.le_tan, ""))
    assert {h.luot_a, h.luot_b} <= _ids(kq["luot"])
    assert set(lich.values()) <= _ids(kq["lich_cho_check_in"], "id")


async def test_hang_cho_va_so_thu_tu_dem_rieng_tung_co_so(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    h = await _hai_co_so(pool)
    so: dict[str, int] = {}
    for ca, cua_minh, cua_nguoi in (
        (h.a, h.luot_a, h.luot_b),
        (h.b, h.luot_b, h.luot_a),
    ):
        kq = await BangLuotKham(pool).hang_cho(identity=ca.bac_si, room_id=None)
        hang = _ids(kq["hang_cho"])
        assert cua_minh in hang and cua_nguoi not in hang
        so[cua_minh] = next(
            d["so_thu_tu"] for d in kq["hang_cho"] if d["visit_id"] == cua_minh
        )
    # Cơ sở B mới dựng, lượt B là khách đầu tiên của B hôm nay — dù lượt A
    # check-in trước (không đếm riêng thì số ≥ 2).
    assert so[h.luot_b] == 1


async def test_sap_toi_theo_co_so(pool: asyncpg.Pool) -> None:  # noqa: F811
    h = await _hai_co_so(pool)
    # Khách đang ở bước TƯ VẤN (chưa vào hàng bác sĩ): một phiên tư vấn chờ.
    for luot in (h.luot_a, h.luot_b):
        await pool.execute(
            "INSERT INTO consultation (clinic_id, visit_id, round_no, kind, status)"
            " SELECT clinic_id, visit_id, 0, 'TU_VAN', 'queued' FROM visit"
            " WHERE visit_id = $1::uuid",
            luot,
        )
    for ca, cua_minh, cua_nguoi in (
        (h.a, h.luot_a, h.luot_b),
        (h.b, h.luot_b, h.luot_a),
    ):
        kq = await BangLuotKham(pool).hang_cho(identity=ca.bac_si, room_id=None)
        sap = _ids(kq["sap_toi"])
        assert cua_minh in sap and cua_nguoi not in sap


async def test_chi_dinh_hom_nay_va_tong_theo_co_so(
    pool: asyncpg.Pool,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import clinicai.services.luot_kham_doc as lkd

    async def _cho_qua(*_a: object, **_k: object) -> None:
        return None

    # Bài đo bộ lọc CƠ SỞ, không đo lego Điều phối.
    monkeypatch.setattr(lkd, "doi_quyen", _cho_qua)
    h = await _hai_co_so(pool)
    for ca, cua_minh, cua_nguoi in (
        (h.a, h.don_a, h.don_b),
        (h.b, h.don_b, h.don_a),
    ):
        kq = await BangLuotKham(pool).chi_dinh_hom_nay(identity=ca.bac_si)
        don = _ids(kq["chi_dinh"], "id")
        assert cua_minh in don and cua_nguoi not in don
        # Câu đếm cùng điều kiện với danh sách — lệch là báo nhầm "bị cắt".
        assert kq["tong"] == len(kq["chi_dinh"]) and kq["bi_cat"] is False
    # Cơ sở B chỉ có đúng chỉ định của lượt B.
    kq_b = await BangLuotKham(pool).chi_dinh_hom_nay(identity=h.b.bac_si)
    assert kq_b["tong"] == 1


async def test_ket_qua_cho_duyet_theo_co_so(pool: asyncpg.Pool) -> None:  # noqa: F811
    h = await _hai_co_so(pool)
    await pool.execute(
        "UPDATE service_order SET ket_qua_luc = now(), result_note = 'Bình thường'"
        " WHERE id = ANY($1::uuid[])",
        [h.don_a, h.don_b],
    )
    for ca, cua_minh, cua_nguoi in (
        (h.a, h.don_a, h.don_b),
        (h.b, h.don_b, h.don_a),
    ):
        kq = await BangLuotKham(pool).ket_qua_cho_duyet(identity=ca.bac_si)
        don = _ids(kq["ket_qua"], "id")
        assert cua_minh in don and cua_nguoi not in don


async def test_cho_quyet_theo_co_so(pool: asyncpg.Pool) -> None:  # noqa: F811
    h = await _hai_co_so(pool)
    yeu_cau: dict[str, str] = {}
    for luot, don in ((h.luot_a, h.don_a), (h.luot_b, h.don_b)):
        vong = await pool.fetchval(
            "INSERT INTO review_round (clinic_id, visit_id, round_no, locked_by)"
            " VALUES ($1::uuid, $2::uuid, 2, $3::uuid) RETURNING id::text",
            CLINIC,
            luot,
            h.a.bac_si.staff_id,
        )
        yeu_cau[luot] = str(
            await pool.fetchval(
                "INSERT INTO round_requirement (clinic_id, round_id, service_order_id,"
                " need) VALUES ($1::uuid, $2::uuid, $3::uuid, 'PERFORMED')"
                " RETURNING id::text",
                CLINIC,
                vong,
                don,
            )
        )
        await pool.execute(
            "UPDATE service_order SET exec_status = 'not_performed',"
            " not_performed_reason = 'Máy hỏng' WHERE id = $1::uuid",
            don,
        )
    for ca, cua_minh, cua_nguoi in (
        (h.a, h.luot_a, h.luot_b),
        (h.b, h.luot_b, h.luot_a),
    ):
        kq = await LuotKhamService(pool).cho_quyet(identity=ca.bac_si)
        viec = _ids(kq["viec"], "id")
        assert yeu_cau[cua_minh] in viec and yeu_cau[cua_nguoi] not in viec


async def test_hang_cho_sieu_am_theo_co_so(pool: asyncpg.Pool) -> None:  # noqa: F811
    h = await _hai_co_so(pool)
    wi: dict[str, str] = {}
    for luot in (h.luot_a, h.luot_b):
        wi[luot] = await _viec_moi(pool, "DICHVU-SIEUAM", luot)
    for ca, cua_minh, cua_nguoi in (
        (h.a, h.luot_a, h.luot_b),
        (h.b, h.luot_b, h.luot_a),
    ):
        kq = await UltrasoundBoardService(pool).queue(identity=ca.bac_si)
        hang = _ids(kq["items"], "work_item_id")
        assert wi[cua_minh] in hang and wi[cua_nguoi] not in hang
    # Mọi dòng bảng siêu âm của B là lượt của B (hoặc lượt chưa rõ cơ sở).
    kq_b = await UltrasoundBoardService(pool).queue(identity=h.b.bac_si)
    async with pool.acquire() as conn:
        co_so = {
            await co_so_cua_luot(conn, CLINIC, visit_id=d["visit_id"])
            for d in kq_b["items"]
        }
    assert co_so <= {h.b.loc, None}


async def test_viec_can_xu_ly_theo_co_so_viec_khong_luot_hien_ca_hai(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    h = await _hai_co_so(pool)
    # Khu có việc mở của CẢ HAI lượt (cùng loại khám → cùng chuỗi node).
    ws = await pool.fetchval(
        "SELECT n.workspace FROM work_item w JOIN node_definition n"
        "  ON n.clinic_id = w.clinic_id AND n.code = w.node_code"
        " WHERE w.visit_id = ANY($1::uuid[]) AND w.status IN ('PENDING', 'IN_PROGRESS')"
        "   AND n.workspace IS NOT NULL"
        " GROUP BY n.workspace HAVING count(DISTINCT w.visit_id) = 2"
        " ORDER BY n.workspace LIMIT 1",
        [h.luot_a, h.luot_b],
    )
    assert ws is not None, "hai lượt không có khu nào chung — bài không đo gì"
    # Việc khu vận hành không lượt, không lịch (OPS-*): hiện ở cả hai cơ sở.
    node_ws = await pool.fetchval(
        "SELECT code FROM node_definition WHERE clinic_id = $1::uuid"
        " AND workspace = $2 ORDER BY code LIMIT 1",
        CLINIC,
        ws,
    )
    khong_luot = await _viec_moi(pool, str(node_ws), None)
    svc = WorkItemService(pool)
    for ca, cua_minh, cua_nguoi in (
        (h.a, h.luot_a, h.luot_b),
        (h.b, h.luot_b, h.luot_a),
    ):
        ds = await svc.list_worklist(workspace=ws, identity=ca.bac_si, ca_khu=True)
        luot = {str(d["visit_id"]) for d in ds if d["visit_id"]}
        assert cua_minh in luot and cua_nguoi not in luot
        assert khong_luot in {str(d["id"]) for d in ds}
