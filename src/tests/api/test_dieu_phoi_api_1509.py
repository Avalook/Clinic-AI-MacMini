"""Bảng điều phối qua HTTP (15/09/2026): chuyển phòng, xếp tuyến theo chỉ định
bác sĩ đã duyệt, ngưỡng cảnh báo RIÊNG TỪNG PHÒNG do quản lý chỉnh, TV có tên,
trưởng ca chuyển bác sĩ, nhật ký tài khoản nhân sự.

Pool giả trả lời theo nội dung câu SQL; hàm SQL thật (`move_visit_to_station`,
RLS, chỉ mục ngưỡng) đã có test SQL + smoke Postgres.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Any

import asyncpg
import pytest
from fastapi.testclient import TestClient

from clinicai.api.identity import ClinicRole, get_current_identity
from clinicai.core.database import get_db_pool
from clinicai.main import app
from tests.services.fake_sql import SqlConn, pool
from tests.services.test_luat_1509_thu_ky_va_dieu_phoi import BS1, ME, VISIT, who

PHONG = "f0000000-0000-4000-8000-000000000001"
NOW = datetime.now(timezone.utc)


def _khach(**kw: Any) -> dict[str, Any]:
    base = {
        "visit_id": VISIT,
        "patient_name": "Nguyễn Thị A",
        "patient_code": "BN1",
        "clinic_patient_id": None,
        "queue_number": 7,
        "specialty": "Sản",
        "doctor_name": "BS",
        "current_node_code": "SIEUAM",
        "current_node_name": "Siêu âm",
        "room_id": PHONG,
        "room_code": "SA1",
        "room_name": "Siêu âm 1",
        "room_floor": 2,
        "wait_minutes": 45,
        "total_minutes": 60,
        "threshold_minutes": None,
        "done_steps": ["TIEPDON"],
        "route_steps": ["TIEPDON", "SIEUAM", "KHAM"],
        "checked_in_at": NOW,
    }
    base.update(kw)
    return base


def _phong(**kw: Any) -> dict[str, Any]:
    base = {
        "id": PHONG,
        "code": "SA1",
        "name": "Siêu âm 1",
        "floor": 2,
        "node_code": "SIEUAM",
        "serves_nodes": None,
        "node_name": "Siêu âm",
        "capacity": 1,
        "accepting": True,
        "show_on_tv": True,
        "serving": 1,
        "waiting": 9,
        "max_wait": 45,
        "avg_wait": 30,
        "threshold_minutes": 20,
        "threshold_waiting": 5,
    }
    base.update(kw)
    return base


# Câu toàn cảnh cũng JOIN clinic_room — khoá theo cột riêng của nó trước.
DOC = [
    ("AS visit_status", [_khach(), _khach(queue_number=None, room_code="SA1")]),
    (
        "FROM public.clinic_room r",
        [_phong(), _phong(id="x", code="TV0", show_on_tv=False)],
    ),
]


@pytest.fixture(autouse=True)
def _quyen_theo_nhom_mau(monkeypatch: pytest.MonkeyPatch) -> None:
    """21 lego (25/09/2026): cửa router + đổi bác sĩ hỏi QUYỀN — pool giả trả lời
    theo nhóm mẫu của vai (tests/quyen_gia.py)."""
    from tests.quyen_gia import cua_router_theo_nhom_mau, dich_vu_theo_nhom_mau

    cua_router_theo_nhom_mau(monkeypatch)
    dich_vu_theo_nhom_mau(monkeypatch)


@pytest.fixture
def db() -> Iterator[list[SqlConn]]:
    holder: list[SqlConn] = [pool(*DOC)]
    app.dependency_overrides[get_db_pool] = lambda: holder[0]
    yield holder
    app.dependency_overrides.clear()


def _as(role: ClinicRole, staff: str = ME) -> None:
    app.dependency_overrides[get_current_identity] = lambda: who(role, staff)


def test_doc_toan_canh_canh_bao_tv(db: list[SqlConn]) -> None:
    _as(ClinicRole.RECEPTION)
    c = TestClient(app)
    ov = c.get("/api/v1/dispatch/overview").json()
    assert ov["patients"][0]["next_step"] == "KHAM"
    assert ov["patients"][0]["threshold_minutes"] == 20  # chưa đặt → mặc định
    assert ov["rooms"][0]["state"] != "ok" or ov["rooms"][0]["waiting"] == 9
    assert c.get("/api/v1/dispatch/alerts").json()["items"]
    tv = c.get("/api/v1/dispatch/tv").json()["rooms"]
    # Phòng tắt TV không lên; khách chưa có số không hiện tên.
    assert [r["code"] for r in tv] == ["SA1"]
    assert tv[0]["names"] == ["Nguyễn Thị A"] and tv[0]["queue"] == [7]


def test_lich_su_va_tuyen(db: list[SqlConn]) -> None:
    db[0] = pool(
        (
            "FROM public.v_dispatch_history",
            [
                {
                    "created_at": NOW,
                    "event_type": "dispatch.moved",
                    "visit_id": VISIT,
                    "from_node": "A",
                    "to_node": "B",
                    "from_room": None,
                    "to_room": "SA1",
                    "reason": None,
                    "actor_name": "TC",
                    "patient_name": "K",
                    "patient_code": "BN",
                },
            ],
        ),
        (
            "SELECT code, name, steps FROM public.route_template",
            [{"code": "R1", "name": "Tuyến 1", "steps": ["A", "B"]}],
        ),
    )
    _as(ClinicRole.TRUONG_CA)
    c = TestClient(app)
    assert (
        c.get("/api/v1/dispatch/history?limit=5").json()["items"][0]["to_room"] == "SA1"
    )
    assert c.get("/api/v1/dispatch/routes").json()["items"][0]["steps"] == ["A", "B"]


def test_nguong_rieng_tung_phong_chi_truong_ca_quan_ly(db: list[SqlConn]) -> None:
    c = TestClient(app)
    _as(ClinicRole.RECEPTION)
    body = {"room_id": PHONG, "wait_minutes": 15, "max_waiting": 4}
    assert c.put("/api/v1/dispatch/threshold", json=body).status_code == 403

    _as(ClinicRole.MANAGEMENT)
    assert c.put("/api/v1/dispatch/threshold", json=body).json() == {"ok": True}
    rieng = db[0].da_goi("ON CONFLICT (clinic_id, room_id)")
    assert rieng and rieng[0][1:4] == (PHONG, 15, 4)
    c.put("/api/v1/dispatch/threshold", json={"wait_minutes": 25, "max_waiting": 8})
    assert db[0].da_goi("ON CONFLICT (clinic_id) WHERE room_id IS NULL")
    assert (
        c.put(
            "/api/v1/dispatch/threshold", json={"wait_minutes": 0, "max_waiting": 8}
        ).status_code
        == 422
    )


@pytest.mark.asyncio
async def test_nguong_ngoai_khoang_bi_chan_o_service() -> None:
    from clinicai.api.exceptions import ValidationError
    from clinicai.services.dispatch_service import DispatchService

    svc = DispatchService(pool())
    with pytest.raises(ValidationError):
        await svc.set_threshold(
            identity=who(ClinicRole.MANAGEMENT),
            room_id=None,
            wait_minutes=500,
            max_waiting=3,
        )
    with pytest.raises(ValidationError):
        await svc.set_threshold(
            identity=who(ClinicRole.MANAGEMENT),
            room_id=None,
            wait_minutes=5,
            max_waiting=0,
        )


def test_chuyen_phong_va_doi_phong(db: list[SqlConn]) -> None:
    db[0] = pool(("move_visit_to_station(", "w-1"))
    c = TestClient(app)
    _as(ClinicRole.DOCTOR)
    move = {"visit_id": VISIT, "node_code": "SIEUAM"}
    assert c.post("/api/v1/dispatch/move", json=move).status_code == 403
    _as(ClinicRole.TRUONG_CA)
    r = c.post("/api/v1/dispatch/move", json=move).json()
    assert r == {"ok": True, "work_item_id": "w-1", "gate_overridden": None}
    r2 = c.post(
        "/api/v1/dispatch/transfer-room",
        json={**move, "room_id": PHONG, "reason": "Cân tải"},
    )
    assert r2.status_code == 201
    assert db[0].da_goi("move_visit_to_station(")[-1][-1] == "dispatch.transfer_room"

    # Hàm SQL từ chối (vd bước dịch vụ chưa được bác sĩ chỉ định) → 4xx nguyên câu.
    db[0] = pool(
        ("move_visit_to_station(", asyncpg.RaiseError("Chưa có chỉ định\nchi tiết"))
    )
    bad = c.post("/api/v1/dispatch/move", json=move)
    assert bad.status_code in (400, 422) and "Chưa có chỉ định" in bad.text


def test_xep_tuyen_chi_giu_buoc_da_chi_dinh(db: list[SqlConn]) -> None:
    c = TestClient(app)
    _as(ClinicRole.TRUONG_CA)
    body = {"visit_id": VISIT, "template_code": "R1"}

    db[0] = pool()
    assert c.post("/api/v1/dispatch/route", json=body).status_code in (400, 422)
    assert c.post(
        "/api/v1/dispatch/route", json={**body, "is_exception": True}
    ).status_code in (400, 422)

    tpl = (
        "SELECT id, steps FROM public.route_template",
        {"id": "t", "steps": ["SIEUAM", "XN", "KHAM"]},
    )
    db[0] = pool(
        tpl,
        (
            "FROM public.node_definition n",
            [{"code": "SIEUAM", "co_viec": True}, {"code": "XN", "co_viec": False}],
        ),
        ("array_agg(node_code)", ["TIEPDON"]),
        ("INSERT INTO public.visit_route", "route-1"),
    )
    r = c.post("/api/v1/dispatch/route", json=body).json()
    assert r["steps"] == ["SIEUAM", "KHAM"] and r["bo_qua_chua_chi_dinh"] == ["XN"]
    assert db[0].da_goi("superseded_at = now()")
    assert db[0].da_goi("dispatch.route_applied")

    db[0] = pool(
        tpl,
        (
            "FROM public.node_definition n",
            [{"code": c_, "co_viec": False} for c_ in ("SIEUAM", "XN", "KHAM")],
        ),
    )
    assert "chưa chỉ định" in c.post("/api/v1/dispatch/route", json=body).text


def test_truong_ca_chuyen_bac_si(db: list[SqlConn]) -> None:
    c = TestClient(app)
    _as(ClinicRole.TRUONG_CA)
    db[0] = pool(
        (
            # 24/09/2026: danh sách theo QUYỀN (khám + hoàn tất khám), không vai.
            "'clinical.consult.finalize')) = 2",
            [{"id": BS1, "full_name": "BS B", "role": "DOCTOR"}],
        )
    )
    assert c.get("/api/v1/dispatch/bac-si").json()["items"][0]["id"] == BS1

    db[0] = pool(
        (
            "FOR UPDATE",
            {
                "visit_id": VISIT,
                "status": "IN_PROGRESS",
                "appointment_id": "ap",
                "bac_si_cu": ME,
            },
        ),
        ("SELECT EXISTS", True),
    )
    r = c.post(
        "/api/v1/dispatch/doi-bac-si",
        json={"visit_id": VISIT, "bac_si_moi_id": BS1, "ly_do": "BS nghỉ"},
    )
    assert r.json()["bac_si_moi_id"] == BS1
    assert db[0].da_goi("UPDATE appointment SET doctor_id") and db[0].events()
    assert (
        c.post(
            "/api/v1/dispatch/doi-bac-si",
            json={"visit_id": VISIT, "bac_si_moi_id": BS1, "ly_do": ""},
        ).status_code
        == 422
    )


def test_nhat_ky_tai_khoan_nhan_su(db: list[SqlConn]) -> None:
    c = TestClient(app)
    url = f"/api/v1/staff/{BS1}/nhat-ky-tai-khoan"
    _as(ClinicRole.RECEPTION)
    assert c.post(url, json={"hanh_dong": "doi_mat_khau"}).status_code == 403
    _as(ClinicRole.MANAGEMENT)
    db[0] = pool()
    assert c.post(url, json={"hanh_dong": "doi_mat_khau"}).status_code == 404
    # Tạo / thu hồi ghi trong giao dịch của TaiKhoanService (06/10/2026) — nhận
    # ở đây nữa là ghi hai lần.
    for da_chuyen in ("tao", "thu_hoi"):
        assert c.post(url, json={"hanh_dong": da_chuyen}).status_code == 422
    db[0] = pool(("SELECT s.full_name FROM staff s", "BS B"))
    ok = c.post(url, json={"hanh_dong": "doi_mat_khau"})
    assert ok.status_code in (200, 201) and db[0].events()
