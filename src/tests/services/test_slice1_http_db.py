"""Slice 1 — smoke trọn luồng qua HTTP thật của FastAPI trên Postgres dùng một lần.

Router + service + SQL chạy thật; chỉ thay danh tính (không có Supabase) và kho
tệp (thư mục tạm). Hai lượt khám:

  1. lấy máu (VALID_RESULT) + siêu âm (PERFORMED): lấy mẫu xong chưa đủ → quầy,
     CSKH, bác sĩ đều thấy "chờ kết quả" từ rail mới → đối tác tải TỆP thật →
     hook chạy lại vòng đọc → khách về bác sĩ → duyệt → đóng → lịch COMPLETED;
  2. siêu âm KHÔNG làm được → không đóng vòng khi chưa quyết → thư ký không
     quyết được → thiếu lý do bị từ chối → bác sĩ miễn có lý do → nhật ký đủ vai.

Cộng hai lối rail cũ phải từ chối: POST /lab/orders (410) và chuyển cả lượt bằng
move_visit_to_station với lượt luồng mới.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

import asyncpg
import httpx
import pytest

from clinicai.api.identity import ClinicRole, StaffIdentity, _resolve_identity
from clinicai.core.database import get_db_pool
from clinicai.main import app
from clinicai.services.permission_service import cap_preset_mac_dinh

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

CLINIC = "a0000000-0000-4000-8000-000000000001"
KET: list[tuple[str, bool, str]] = []
HIEN_TAI: dict[str, StaffIdentity] = {}


# Lifecycle v1 Slice 4 §D: /dispatch cũ chỉ còn cho dòng legacy — smoke này
# kiểm rail Slice 1 qua HTTP, không kiểm Routing, nên đưa chỉ định về dạng
# legacy trước khi gọi. Routing chính thức: test_service_routing_db.py.
_VE_LEGACY = (
    "UPDATE service_order SET selection_status = NULL, routing_status = NULL"
    " WHERE id = $1::uuid"
)


def kiem(ten: str, dung: bool, chi_tiet: Any = "") -> None:
    KET.append((ten, dung, str(chi_tiet)[:300]))


async def nguoi(conn: asyncpg.Connection, loc: str, role: str) -> StaffIdentity:
    ten = f"Smoke {role} {uuid.uuid4().hex[:5]}"
    sid = await conn.fetchval(
        "INSERT INTO staff (full_name, primary_department, primary_location_id,"
        " is_active) VALUES ($1, $2, $3::uuid, true) RETURNING id::text",
        ten,
        role,
        loc,
    )
    await conn.execute(
        "INSERT INTO clinic_membership (clinic_id, staff_id, role, is_active)"
        " VALUES ($1::uuid, $2::uuid, $3, true) ON CONFLICT DO NOTHING",
        CLINIC,
        sid,
        role,
    )
    await cap_preset_mac_dinh(conn, clinic_id=CLINIC, staff_id=sid, vai=role)

    return StaffIdentity(
        staff_id=sid,
        auth_user_id=str(uuid.uuid4()),
        full_name=ten,
        department=role,
        role=ClinicRole(role),
        clinic_id=CLINIC,
        location_id=loc,
        location_name="Cơ sở smoke",
    )


async def _chay(pool: asyncpg.Pool) -> None:
    app.dependency_overrides[get_db_pool] = lambda: pool
    app.dependency_overrides[_resolve_identity] = lambda: HIEN_TAI["ai"]
    async with pool.acquire() as conn:
        loc = await conn.fetchval(
            "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid"
            " AND is_active ORDER BY created_at, id LIMIT 1",
            CLINIC,
        )
        le_tan = await nguoi(conn, loc, "RECEPTION")
        dd = await nguoi(conn, loc, "NURSE_ULTRASOUND")
        bs = await nguoi(conn, loc, "DOCTOR")
        tk = await nguoi(conn, loc, "TKYK")
        bs_sa = await nguoi(conn, loc, "ULTRASOUND_DOCTOR")
        tc = await nguoi(conn, loc, "TRUONG_CA")
        dt = await nguoi(conn, loc, "PARTNER")
        await conn.execute(
            "INSERT INTO thu_ky_bac_si (clinic_id, thu_ky_staff_id, bac_si_staff_id)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid)",
            CLINIC,
            tk.staff_id,
            bs.staff_id,
        )
        st = await conn.fetchval(
            "SELECT id::text FROM service_type WHERE clinic_id = $1::uuid"
            " ORDER BY name LIMIT 1",
            CLINIC,
        )
        ma_sa = await conn.fetchval(
            "SELECT service_code FROM service_price WHERE clinic_id = $1::uuid AND"
            " active AND node_code = 'DICHVU-SIEUAM' ORDER BY service_code LIMIT 1",
            CLINIC,
        )
        ma_mau = await conn.fetchval(
            "SELECT service_code FROM service_price WHERE clinic_id = $1::uuid AND"
            " active AND node_code = 'DICHVU-LAYMAU-MAU' AND NOT doi_tac_lay_mau"
            " ORDER BY service_code LIMIT 1",
            CLINIC,
        )

        async def lich(phut: int) -> str:
            pid = await conn.fetchval(
                "INSERT INTO patient (clinic_id, patient_code, full_name, location_id)"
                " VALUES ($1::uuid, $2, 'Khách Smoke Slice1', $3::uuid)"
                " RETURNING clinic_patient_id::text",
                CLINIC,
                f"SMK-{uuid.uuid4().hex[:8]}",
                loc,
            )
            return str(
                await conn.fetchval(
                    "INSERT INTO appointment (clinic_id, clinic_patient_id,"
                    " location_id, service_type_id, doctor_id, slot_start, slot_end,"
                    " status, booking_channel, is_walkin)"
                    " VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5::uuid,"
                    " now() + make_interval(mins => $6),"
                    " now() + make_interval(mins => $6 + 15), 'CONFIRMED',"
                    " 'WALK_IN', true)"
                    " RETURNING id::text",
                    CLINIC,
                    pid,
                    loc,
                    st,
                    bs.staff_id,
                    phut,
                )
            )

        hen1 = await lich(0)
        hen2 = await lich(30)

    tx = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://smoke"
    )

    async def goi(
        ai: StaffIdentity, method: str, path: str, **kw: Any
    ) -> httpx.Response:
        HIEN_TAI["ai"] = ai
        headers = kw.pop("headers", {})
        headers.setdefault("Idempotency-Key", "smk-" + uuid.uuid4().hex)
        return await tx.request(method, "/api/v1" + path, headers=headers, **kw)

    async def luot_cua(hen: str) -> str:
        return str(
            await pool.fetchval(
                "SELECT visit_id::text FROM visit WHERE appointment_id = $1::uuid", hen
            )
        )

    async def bang(ai: StaffIdentity, vid: str) -> dict[str, Any]:
        r = await goi(ai, "GET", "/luot-kham/bang")
        return next(v for v in r.json()["luot"] if v["visit_id"] == vid)

    async def vao_kham(hen: str) -> tuple[str, str]:
        r = await goi(
            le_tan, "POST", "/luot-kham/check-in", json={"appointment_id": hen}
        )
        kiem("check-in 200", r.status_code == 200, r.text)
        vid = await luot_cua(hen)
        sinh_hieu = {
            "systolic": 118,
            "diastolic": 76,
            "weight_kg": 55,
            "height_cm": 160,
        }
        # Chưa bấm [Bắt đầu] thì không lưu lần đầu được (chốt 23/09/2026).
        r = await goi(dd, "POST", f"/luot-kham/visits/{vid}/vitals", json=sinh_hieu)
        kiem(
            "lưu khi chưa Bắt đầu → 409 VITALS_NOT_STARTED",
            r.status_code == 409 and r.json().get("error") == "VITALS_NOT_STARTED",
            r.text,
        )
        r = await goi(dd, "POST", f"/luot-kham/visits/{vid}/vitals/start")
        kiem("bắt đầu đo 200", r.status_code == 200, r.text)
        r = await goi(
            dd,
            "POST",
            f"/luot-kham/visits/{vid}/vitals",
            json=sinh_hieu,
        )
        kiem("đo sinh hiệu 200", r.status_code == 200, r.text)
        phien = (await bang(bs, vid))["phien"][0]["id"]
        r = await goi(bs, "POST", f"/luot-kham/consultations/{phien}/start")
        kiem("bác sĩ bắt đầu khám", r.status_code == 200, r.text)
        return vid, phien

    # ── Lượt 1: VALID_RESULT (lấy máu) + PERFORMED (siêu âm) ────────────────
    vid, phien = await vao_kham(hen1)
    r = await goi(
        tk,
        "POST",
        f"/luot-kham/consultations/{phien}/draft-orders",
        json={"service_codes": [ma_mau, ma_sa]},
    )
    kiem("thư ký ghi nháp chỉ định", r.status_code == 200, r.text)
    nhap = r.json()
    r = await goi(
        tk,
        "POST",
        f"/luot-kham/consultations/{phien}/authorize-orders",
        json={
            "draft_order_ids": nhap["order_ids"],
            "expected_versions": nhap["versions"],
        },
    )
    kiem("thư ký KHÔNG duyệt được chỉ định (403)", r.status_code == 403, r.status_code)
    r = await goi(
        bs,
        "POST",
        f"/luot-kham/consultations/{phien}/authorize-orders",
        json={
            "draft_order_ids": nhap["order_ids"],
            "expected_versions": nhap["versions"],
        },
    )
    kiem("bác sĩ duyệt nháp", r.status_code == 200, r.text)
    mau, sa = nhap["order_ids"]
    r = await goi(bs, "POST", f"/luot-kham/consultations/{phien}/kham-xong")
    kiem("khám xong (mặc định theo dịch vụ)", r.status_code == 200, r.text)
    vong = (await bang(bs, vid))["vong"][0]
    can = {y["chi_dinh_id"]: y["can"] for y in vong["yeu_cau"]}
    kiem(
        "lấy máu cần KẾT QUẢ, siêu âm cần ĐÃ LÀM",
        can == {mau: "VALID_RESULT", sa: "PERFORMED"},
        can,
    )

    for oid, ai in ((sa, bs_sa), (mau, dd)):
        st_ = await pool.fetchval(
            "SELECT exec_status FROM service_order WHERE id = $1::uuid", oid
        )
        if st_ == "authorized":
            room_node = "DICHVU-SIEUAM" if oid == sa else "DICHVU-LAYMAU-MAU"
            room = await pool.fetchval(
                "SELECT r.id::text FROM clinic_room r JOIN clinic_room_node rn ON"
                " rn.room_id = r.id WHERE r.clinic_id = $1::uuid AND rn.node_code ="
                " $2 AND r.is_active AND r.accepting ORDER BY r.sort LIMIT 1",
                CLINIC,
                room_node,
            )
            await pool.execute(_VE_LEGACY, oid)
            await goi(
                tc, "POST", f"/luot-kham/orders/{oid}/dispatch", json={"room_id": room}
            )
        r1 = await goi(ai, "POST", f"/luot-kham/orders/{oid}/start")
        r2 = await goi(
            ai, "POST", f"/luot-kham/orders/{oid}/complete", json={"performed": True}
        )
        kiem(
            f"làm dịch vụ {'SA' if oid == sa else 'lấy máu'}",
            r1.status_code == 200 and r2.status_code == 200,
            r1.text + r2.text,
        )

    vong = (await bang(bs, vid))["vong"][0]
    kiem(
        "lấy máu xong CHƯA đủ — vòng vẫn đang thu",
        vong["trang_thai"] == "collecting",
        vong,
    )
    r = await goi(bs, "GET", "/luot-kham/cho-quyet")
    viec = [v for v in r.json()["viec"] if v["visit_id"] == vid]
    kiem(
        "bác sĩ thấy 'chờ kết quả'",
        [v["trang_thai"] for v in viec] == ["cho_ket_qua"],
        viec,
    )
    r = await goi(le_tan, "GET", f"/reception/checkout/{vid}")
    if r.status_code == 404:
        r = await goi(le_tan, "GET", f"/checkout/{vid}")
    kiem("checkout đọc được", r.status_code == 200, f"{r.status_code} {r.text[:200]}")
    loai = (
        {b["type"] for b in r.json().get("blockers", [])}
        if r.status_code == 200
        else set()
    )
    kiem("checkout chặn 'kết quả bác sĩ đang chờ'", "lab_pending" in loai, loai)
    cskh = await pool.fetch(
        "SELECT trang_thai FROM v_viec_cskh v JOIN visit vi ON vi.clinic_patient_id ="
        " v.clinic_patient_id WHERE vi.visit_id = $1::uuid",
        vid,
    )
    kiem(
        "CSKH có việc CHO_KQ_XN (rail mới)",
        "CHO_KQ_XN" in {c["trang_thai"] for c in cskh},
        [c["trang_thai"] for c in cskh],
    )

    # Đối tác gửi TỆP kết quả thật → hook chạy lại vòng đọc.
    await pool.execute(
        "UPDATE node_definition SET lam_ben_ngoai = true WHERE clinic_id = $1::uuid"
        " AND code = 'DICHVU-LAYMAU-MAU'",
        CLINIC,
    )
    pdf = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
    r = await goi(
        dt,
        "POST",
        "/doi-tac/ket-qua",
        data={"chi_dinh_id": mau},
        files={"file": ("ket-qua.pdf", pdf, "application/pdf")},
    )
    kiem(
        "đối tác tải tệp kết quả",
        r.status_code == 201,
        f"{r.status_code} {r.text[:300]}",
    )
    tep_id = r.json()["id"]

    # Tệp mới tải lên ở trạng thái CHO_XAC_NHAN -> vòng CHƯA sẵn sàng (Blocker 1)
    vong = (await bang(bs, vid))["vong"][0]
    kiem(
        "tệp mới tải lên chưa xác nhận → vòng CHƯA sẵn sàng",
        vong["trang_thai"] == "collecting",
        vong,
    )

    # Cấp capability ket_qua.xac_nhan và xác nhận HOP_LE qua HTTP
    await pool.execute(
        "INSERT INTO staff_capability (staff_id, capability) "
        "VALUES ($1::uuid, 'ket_qua.xac_nhan') ON CONFLICT DO NOTHING",
        tc.staff_id,
    )
    r = await goi(
        tc,
        "POST",
        f"/cskh/ket-qua/tep/{tep_id}/xac-nhan",
        json={"trang_thai": "HOP_LE"},
    )
    kiem("xác nhận tệp kết quả hợp lệ", r.status_code == 200, r.text)

    vong = (await bang(bs, vid))["vong"][0]
    kiem(
        "tệp về → vòng SẴN SÀNG, khách quay lại bác sĩ",
        vong["trang_thai"] == "ready",
        vong,
    )
    phien2 = next(
        p["id"] for p in (await bang(bs, vid))["phien"] if p["loai"] == "REVIEW"
    )
    r = await goi(bs, "POST", f"/luot-kham/consultations/{phien2}/start")
    kiem("bác sĩ bắt đầu đọc kết quả", r.status_code == 200, r.text)
    r = await goi(bs, "POST", f"/luot-kham/orders/{mau}/duyet-ket-qua", json={})
    kiem("bác sĩ duyệt kết quả", r.status_code == 200, r.text)
    r = await goi(bs, "POST", f"/luot-kham/consultations/{phien2}/kham-xong")
    kiem("đọc xong", r.status_code == 200, r.text)
    hen_st = await pool.fetchval(
        "SELECT status FROM appointment WHERE id = $1::uuid", hen1
    )
    kiem("lịch hẹn COMPLETED (quầy thu tiền được)", hen_st == "COMPLETED", hen_st)
    r = await goi(le_tan, "GET", f"/reception/checkout/{vid}")
    if r.status_code == 404:
        r = await goi(le_tan, "GET", f"/checkout/{vid}")
    loai = {b["type"] for b in r.json().get("blockers", [])}
    kiem(
        "checkout hết vướng lâm sàng",
        not loai & {"service_open", "lab_pending", "exam_open"},
        loai,
    )

    # ── Lượt 2: NOT_PERFORMED → bác sĩ phải quyết ───────────────────────────
    vid2, phien = await vao_kham(hen2)
    r = await goi(
        bs,
        "POST",
        f"/luot-kham/consultations/{phien}/authorize-orders",
        json={"service_codes": [ma_sa]},
    )
    [sa2] = r.json()["order_ids"]
    await goi(bs, "POST", f"/luot-kham/consultations/{phien}/kham-xong")
    sa2_st = await pool.fetchval(
        "SELECT exec_status FROM service_order WHERE id = $1::uuid", sa2
    )
    if sa2_st == "authorized":
        room = await pool.fetchval(
            "SELECT r.id::text FROM clinic_room r JOIN clinic_room_node rn ON"
            " rn.room_id = r.id WHERE r.clinic_id = $1::uuid AND rn.node_code ="
            " 'DICHVU-SIEUAM' AND r.is_active AND r.accepting ORDER BY r.sort LIMIT 1",
            CLINIC,
        )
        await pool.execute(_VE_LEGACY, sa2)
        await goi(
            tc, "POST", f"/luot-kham/orders/{sa2}/dispatch", json={"room_id": room}
        )
    await goi(bs_sa, "POST", f"/luot-kham/orders/{sa2}/start")
    r = await goi(
        bs_sa,
        "POST",
        f"/luot-kham/orders/{sa2}/complete",
        json={"performed": False, "reason": "Khách không nhịn tiểu được"},
    )
    kiem("siêu âm KHÔNG làm được", r.status_code == 200, r.text)
    phien2 = next(
        p["id"] for p in (await bang(bs, vid2))["phien"] if p["loai"] == "REVIEW"
    )
    await goi(bs, "POST", f"/luot-kham/consultations/{phien2}/start")
    r = await goi(bs, "POST", f"/luot-kham/consultations/{phien2}/kham-xong")
    kiem(
        "không đóng vòng khi chưa quyết (409)",
        r.status_code == 409 and "REQUIREMENT_DECISION_REQUIRED" in r.text,
        f"{r.status_code} {r.text[:200]}",
    )
    r = await goi(bs, "GET", "/luot-kham/cho-quyet")
    viec = [v for v in r.json()["viec"] if v["visit_id"] == vid2]
    kiem(
        "bác sĩ thấy 'không làm được'",
        [v["trang_thai"] for v in viec] == ["can_quyet"],
        viec,
    )
    rid = viec[0]["id"] if viec else str(uuid.uuid4())
    r = await goi(
        tk,
        "POST",
        f"/luot-kham/yeu-cau/{rid}/quyet",
        json={"hanh_dong": "WAIVE", "ly_do": "Thư ký thử"},
    )
    kiem("thư ký KHÔNG quyết được (403)", r.status_code == 403, r.status_code)
    r = await goi(
        bs,
        "POST",
        f"/luot-kham/yeu-cau/{rid}/quyet",
        json={"hanh_dong": "WAIVE", "ly_do": ""},
    )
    kiem("thiếu lý do bị từ chối (422)", r.status_code == 422, r.status_code)
    r = await goi(
        bs,
        "POST",
        f"/luot-kham/yeu-cau/{rid}/quyet",
        json={"hanh_dong": "WAIVE", "ly_do": "Hẹn siêu âm lần tái khám"},
    )
    kiem("bác sĩ miễn có lý do", r.status_code == 200, r.text)
    r = await goi(bs, "POST", f"/luot-kham/consultations/{phien2}/kham-xong")
    kiem("đọc xong sau khi quyết", r.status_code == 200, r.text)
    ev = await pool.fetchrow(
        "SELECT metadata FROM event_log WHERE event_type = 'requirement.waived'"
        " AND aggregate_id = $1::uuid",
        vid2,
    )
    kiem(
        "nhật ký requirement.waived có vai + người",
        ev is not None
        and bs.staff_id in str(ev["metadata"])
        and "DOCTOR" in str(ev["metadata"]),
        ev,
    )

    # ── Lối cũ đã nghỉ ─────────────────────────────────────────────────────
    r = await goi(
        bs,
        "POST",
        "/lab/orders",
        json={"clinic_patient_id": str(uuid.uuid4()), "test_name": "X"},
    )
    kiem("POST /lab/orders → 410", r.status_code == 410, r.status_code)
    r = await goi(
        tc,
        "POST",
        "/dispatch/transfer-room",
        json={
            "visit_id": vid2,
            "node_code": "DICHVU-SIEUAM",
            "room_id": str(uuid.uuid4()),
            "reason": "thử",
        },
    )
    kiem(
        "chuyển cả lượt (move_visit_to_station) bị từ chối với luồng mới",
        r.status_code in (400, 422) and "từng chỉ định" in r.text,
        f"{r.status_code} {r.text[:200]}",
    )

    await tx.aclose()


async def test_slice1_tron_luong_qua_http(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = os.environ.get("DATABASE_URL") or ""
    if not url:
        pytest.skip("cần DATABASE_URL_TEST trỏ tới database dùng một lần")
    from clinicai.services import media_service, nhan_tep_luong, tep_ket_qua_service

    for mod in (media_service, nhan_tep_luong, tep_ket_qua_service):
        monkeypatch.setattr(mod, "MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(tep_ket_qua_service, "MEDIA_MIN_FREE_BYTES", 0)
    KET.clear()
    pool = await asyncpg.create_pool(
        url.replace("postgresql+asyncpg://", "postgresql://", 1),
        min_size=1,
        max_size=6,
    )
    try:
        await _chay(pool)
    finally:
        app.dependency_overrides.pop(get_db_pool, None)
        app.dependency_overrides.pop(_resolve_identity, None)
        await pool.close()
    hong = [f"{ten} :: {ct}" for ten, dung, ct in KET if not dung]
    assert not hong, "\n".join(hong)
    assert len(KET) >= 35
