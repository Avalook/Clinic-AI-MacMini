"""Test đơn vị: nháp chỉ định (thư ký nhập, bác sĩ duyệt), ký bệnh án đúng phiên
bản, cho phép gửi, đính chính, ký siêu âm theo bác sĩ nhận ca (15/09/2026).

Đường database thật: smoke Postgres + test SQL. Đây khoá nhánh Python.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.api.identity import ClinicRole
from clinicai.core.exceptions import SafetyGateError
from tests.quyen_gia import can_theo_nhom_mau
from tests.services.fake_sql import pool
from tests.services.test_luat_1509_thu_ky_va_dieu_phoi import BS1, ME, VISIT, who

LUOT = {"visit_id": VISIT, "attending_doctor_id": ME, "closed_at": None}
NHAP = {"id": "n1", "service_codes": ["SA"], "recorded_by": BS1, "version": 3}
GIA = [{"service_code": "SA", "node_code": "DICHVU-SIEUAM"}]


@pytest.fixture(autouse=True)
def _cua_quyen_co_bai_kiem_rieng(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cho phép gửi / đính chính hỏi quyền `clinical.consult.finalize` (CORE-A);
    bài kiểm quyền chạy trên Postgres thật. Ở đây pool là giả lập SQL."""

    async def _qua(*_a: Any, **_k: Any) -> None:
        return None

    monkeypatch.setattr("clinicai.services.clinical_sign_service.doi_quyen", _qua)
    # 28/09: duyệt nháp / bỏ dịch vụ / cho phép gửi hỏi QUYỀN — theo nhóm mẫu.
    for duong in (
        "clinicai.services.service_order_service.can",
        "clinicai.services.tep_ket_qua_service.can",
        # 29/09: đính chính đơn hỏi QUYỀN Khám (trợ lý trọn quyền).
        "clinicai.services.dinh_chinh_don.can",
    ):
        monkeypatch.setattr(duong, can_theo_nhom_mau)


def _co_ban(nhap: Any = NHAP) -> list[tuple[str, Any]]:
    return [
        ("SELECT visit_id, attending_doctor_id, closed_at", LUOT),
        ("FROM public.thu_ky_bac_si", [ME]),
        ("SELECT service_code, node_code FROM service_price", GIA),
        ("FROM service_order_draft WHERE clinic_id", nhap),
        (
            "FROM service_order_draft d",
            {
                "id": "n1",
                "version": 4,
                "service_codes": ["SA", "XN"],
                "updated_at": datetime.now(timezone.utc),
                "recorded_by": BS1,
                "recorded_by_name": "TK",
            },
        ),
        (
            "SELECT service_code, name, unit_price, node_code",
            [
                {
                    "service_code": "SA",
                    "name": "Siêu âm",
                    "unit_price": 200000,
                    "node_code": "N",
                }
            ],
        ),
        ("SELECT attending_doctor_id::text FROM visit", ME),
    ]


@pytest.mark.asyncio
async def test_thu_ky_nhap_gop_va_tao_moi() -> None:
    from clinicai.services.service_order_service import ServiceOrderService

    p = pool(*_co_ban())
    out = await ServiceOrderService(p).save_draft(
        visit_id=VISIT, codes=["SA", " SA "], identity=who(ClinicRole.TKYK)
    )
    assert out is not None
    services: Any = out["services"]
    assert services[0]["unit_price"] == 200000.0
    assert services[1]["name"] == "XN"  # mã chưa có trong bảng giá
    assert p.da_goi("UPDATE service_order_draft SET service_codes")

    moi = pool(*_co_ban(nhap=None))
    await ServiceOrderService(moi).save_draft(
        visit_id=VISIT, codes=["SA"], identity=who(ClinicRole.TKYK)
    )
    assert moi.da_goi("INSERT INTO service_order_draft")

    with pytest.raises(ValidationError, match="Chưa chọn"):
        await ServiceOrderService(pool(*_co_ban())).save_draft(
            visit_id=VISIT, codes=[" "], identity=who(ClinicRole.TKYK)
        )
    with pytest.raises(ValidationError, match="chưa cấu hình phòng"):
        await ServiceOrderService(pool(*_co_ban())).save_draft(
            visit_id=VISIT, codes=["KHONG_CO"], identity=who(ClinicRole.TKYK)
        )
    with pytest.raises(SafetyGateError):
        await ServiceOrderService(pool()).save_draft(
            visit_id=VISIT, codes=["SA"], identity=who(ClinicRole.CSKH)
        )


@pytest.mark.asyncio
async def test_thu_ky_sua_ca_danh_sach_theo_phien_ban() -> None:
    from clinicai.services.service_order_service import ServiceOrderService

    svc = ServiceOrderService
    with pytest.raises(ConflictError):
        await svc(pool(*_co_ban())).save_draft(
            visit_id=VISIT,
            codes=["SA"],
            identity=who(ClinicRole.TKYK),
            replace=True,
            expected_version=2,
        )
    p = pool(*_co_ban())
    await svc(p).save_draft(
        visit_id=VISIT,
        codes=[],
        identity=who(ClinicRole.TKYK),
        replace=True,
        expected_version=3,
    )
    assert p.da_goi("discard_reason = 'THU_KY_XOA_HET'")
    p2 = pool(*_co_ban())
    await svc(p2).save_draft(
        visit_id=VISIT,
        codes=["SA"],
        identity=who(ClinicRole.TKYK),
        replace=True,
        expected_version=3,
    )
    assert p2.da_goi("UPDATE service_order_draft SET service_codes")
    with pytest.raises(ConflictError, match="đã đóng"):
        await svc(
            pool(
                (
                    "SELECT visit_id, attending_doctor_id, closed_at",
                    {**LUOT, "closed_at": 1},
                )
            )
        ).save_draft(visit_id=VISIT, codes=["SA"], identity=who(ClinicRole.DOCTOR))
    with pytest.raises(Exception, match="Không tìm thấy"):
        await svc(pool()).save_draft(
            visit_id=VISIT, codes=["SA"], identity=who(ClinicRole.DOCTOR)
        )


@pytest.mark.asyncio
async def test_bac_si_duyet_va_bo_nhap() -> None:
    from clinicai.services.service_order_service import ServiceOrderService

    svc = ServiceOrderService
    ket_qua_phong = [
        {
            "out_node_code": "DICHVU-SIEUAM",
            "out_work_item_id": "w",
            "out_service_count": 1,
            "out_created": True,
        }
    ]
    p = pool(*_co_ban(), ("FROM order_services(", ket_qua_phong))
    rows = await svc(p).approve_draft(
        visit_id=VISIT, expected_version=3, identity=who(ClinicRole.DOCTOR)
    )
    assert rows[0]["created"] is True
    assert p.da_goi("approved_at = now()") and p.events()

    with pytest.raises(ConflictError, match="vừa sửa"):
        await svc(pool(*_co_ban())).approve_draft(
            visit_id=VISIT, expected_version=2, identity=who(ClinicRole.DOCTOR)
        )
    with pytest.raises(ConflictError, match="Không có"):
        await svc(pool(*_co_ban(nhap=None))).approve_draft(
            visit_id=VISIT, expected_version=3, identity=who(ClinicRole.DOCTOR)
        )
    with pytest.raises(SafetyGateError, match="bác sĩ khác"):
        await svc(pool(*_co_ban())).approve_draft(
            visit_id=VISIT, expected_version=3, identity=who(ClinicRole.DOCTOR, BS1)
        )
    with pytest.raises(ConflictError, match="không bán"):
        await svc(
            pool(*_co_ban(), ("FROM order_services(", asyncpg.RaiseError("không bán")))
        ).approve_draft(
            visit_id=VISIT, expected_version=3, identity=who(ClinicRole.DOCTOR)
        )
    # 28/09: thư ký / điều dưỡng duyệt được như bác sĩ; người KHÔNG có quyền
    # chỉ định (CSKH) thì không.
    with pytest.raises(SafetyGateError):
        await svc(pool()).approve_draft(
            visit_id=VISIT, expected_version=3, identity=who(ClinicRole.CSKH)
        )

    with pytest.raises(ValidationError, match="lý do"):
        await svc(pool()).discard_draft(
            visit_id=VISIT,
            expected_version=3,
            reason=" ",
            identity=who(ClinicRole.DOCTOR),
        )
    with pytest.raises(SafetyGateError):
        await svc(pool()).discard_draft(
            visit_id=VISIT,
            expected_version=3,
            reason="x",
            identity=who(ClinicRole.CSKH),
        )
    with pytest.raises(ConflictError):
        await svc(pool(*_co_ban())).discard_draft(
            visit_id=VISIT,
            expected_version=9,
            reason=None,
            identity=who(ClinicRole.TKYK),
        )
    d = pool(*_co_ban())
    await svc(d).discard_draft(
        visit_id=VISIT,
        expected_version=3,
        reason="Bác sĩ đổi",
        identity=who(ClinicRole.DOCTOR),
    )
    assert d.da_goi("discard_reason = $4")


@pytest.mark.asyncio
async def test_doc_nhap_va_chi_phi() -> None:
    from clinicai.services.service_order_service import ServiceOrderService

    assert (
        await ServiceOrderService(pool()).get_draft(
            visit_id=VISIT, identity=who(ClinicRole.DOCTOR)
        )
        is None
    )
    with pytest.raises(SafetyGateError):
        await ServiceOrderService(pool()).get_draft(
            visit_id=VISIT, identity=who(ClinicRole.CSKH)
        )
    with pytest.raises(SafetyGateError, match="bác sĩ khác"):
        await ServiceOrderService(
            pool(
                ("FROM public.thu_ky_bac_si", [BS1]),
                ("SELECT attending_doctor_id::text FROM visit", ME),
            )
        ).get_draft(visit_id=VISIT, identity=who(ClinicRole.TKYK))

    p = pool(
        (
            "SELECT visit_id, clinic_patient_id, status FROM visit",
            {"visit_id": VISIT, "clinic_patient_id": "k", "status": "OPEN"},
        ),
        (
            "JOIN node_definition n",
            [
                {
                    "node_code": "N",
                    "node_status": "PENDING",
                    "node_name": "SA",
                    "service_code": "SA",
                    "name": "Siêu âm",
                    "unit_price": 200000,
                },
                {
                    "node_code": "N",
                    "node_status": "PENDING",
                    "node_name": "SA",
                    "service_code": "X",
                    "name": "X",
                    "unit_price": None,
                },
            ],
        ),
        (
            "FROM payment",
            [
                {
                    "id": "p",
                    "kind": "dich_vu",
                    "status": "PAID",
                    "amount": 100000,
                    "paid_at": None,
                    "voided_at": None,
                    "void_reason": None,
                }
            ],
        ),
    )
    ch = await ServiceOrderService(p).charges(
        visit_id=VISIT, identity=who(ClinicRole.CASHIER)
    )
    assert (
        ch["line_count"],
        ch["unpriced_lines"],
        ch["subtotal"],
        ch["outstanding"],
    ) == (2, 1, 200000.0, 100000.0)


# ── clinical_sign_service ──────────────────────────────────────────────────


def _trang_thai(state: str, **kw: Any) -> dict[str, Any]:
    base = {
        "visit_id": VISIT,
        "patient_name": "K",
        "patient_code": "BN",
        "clinical_state": state,
        "version": 1,
        "record_revision": 5,
        "finalized_at": None,
        "signed_by_name": None,
        "released_at": None,
        "released_by_name": None,
        "last_amended_at": None,
        "soap_subjective": '{"a": "x"}',
        "soap_objective": '{"b": "y"}',
        "soap_assessment": '"z"',
        "soap_plan": ["p"],
    }
    base.update(kw)
    return base


@pytest.mark.asyncio
async def test_cho_phep_gui_va_dinh_chinh() -> None:
    from clinicai.services.clinical_sign_service import ClinicalSignService

    with pytest.raises(ValidationError, match="Phải hoàn tất khám"):
        await ClinicalSignService(
            pool(("FROM public.v_clinical_status", _trang_thai("DRAFT")))
        ).release(identity=who(ClinicRole.DOCTOR), visit_id=VISIT)
    assert (
        await ClinicalSignService(
            pool(("FROM public.v_clinical_status", _trang_thai("RELEASED")))
        ).release(identity=who(ClinicRole.DOCTOR), visit_id=VISIT)
    )["already_released"]
    r = pool(
        ("FROM public.v_clinical_status", _trang_thai("SIGNED")),
        ("SELECT visit_id FROM public.visit", VISIT),
        (
            "SELECT v.status",
            {
                "status": "FINALIZED",
                "attending_doctor_id": ME,
                "active_release": False,
                "latest_amendment_id": None,
            },
        ),
    )
    assert (
        await ClinicalSignService(r).release(
            identity=who(ClinicRole.DOCTOR), visit_id=VISIT, note="ok"
        )
    )["state"] == "RELEASED"
    assert r.da_goi("INSERT INTO public.clinical_release")

    svc = ClinicalSignService
    with pytest.raises(ValidationError, match="lý do"):
        await svc(pool()).amend(
            identity=who(ClinicRole.DOCTOR),
            visit_id=VISIT,
            reason=" ",
            corrected={},
            expected_revision=5,
        )
    with pytest.raises(ValidationError, match="Chưa có nội dung"):
        await svc(pool()).amend(
            identity=who(ClinicRole.DOCTOR),
            visit_id=VISIT,
            reason="x",
            corrected={"khac": 1},
            expected_revision=5,
        )
    with pytest.raises(ValidationError, match="ít nhất 5"):
        await svc(pool()).amend(
            identity=who(ClinicRole.DOCTOR),
            visit_id=VISIT,
            reason="sai",
            corrected={"don_thuoc": []},
            expected_revision=5,
            expected_rx="0" * 64,
        )
    with pytest.raises(ValidationError, match="chưa hoàn tất"):
        await svc(
            pool(
                ("SELECT visit_id FROM public.visit", VISIT),
                (
                    "SELECT v.status, v.clinic_patient_id::text",
                    {
                        "status": "OPEN",
                        "clinic_patient_id": BS1,
                        "attending_doctor_id": ME,
                        "record_revision": 5,
                        "was_released": False,
                    },
                ),
            )
        ).amend(
            identity=who(ClinicRole.DOCTOR),
            visit_id=VISIT,
            reason="x",
            corrected={"soap_plan": "y"},
            expected_revision=5,
        )
    a = pool(
        ("SELECT visit_id FROM public.visit", VISIT),
        (
            "SELECT v.status, v.clinic_patient_id::text",
            {
                "status": "FINALIZED",
                "clinic_patient_id": BS1,
                "attending_doctor_id": ME,
                "record_revision": 5,
                "was_released": True,
            },
        ),
        (
            "FROM public.clinical_record WHERE visit_id",
            {
                "soap_subjective": '"a"',
                "soap_objective": "b",
                "soap_assessment": None,
                "soap_plan": '{"x": 1}',
            },
        ),
    )
    out = await svc(a).amend(
        identity=who(ClinicRole.DOCTOR),
        visit_id=VISIT,
        reason="Sai chẩn đoán",
        corrected={"soap_assessment": "mới", "soap_plan": {"x": 2}},
        expected_revision=5,
    )
    assert out["ok"] and a.da_goi("INSERT INTO public.visit_amendment")
    [amend_args] = a.da_goi("INSERT INTO public.visit_amendment")
    assert amend_args[1] == who(ClinicRole.DOCTOR).clinic_id
    assert a.da_goi("UPDATE public.clinical_release")


@pytest.mark.asyncio
async def test_dinh_chinh_don_khoa_visit_roi_prescription_roi_allocation() -> None:
    from clinicai.services.clinical_sign_service import ClinicalSignService
    from clinicai.services.dinh_chinh_don import prescription_fingerprint

    rx = "10000000-0000-4000-8000-000000000001"
    old = {
        "id": rx,
        "drug_catalog_id": None,
        "drug_name_raw": "Thuốc cũ",
        "quantity": "10 viên",
        "dosage_instructions": "Sáng 1",
        "caution": None,
        # Mức B + đổi thuốc buộc replacement và nhánh khóa allocation.
        "muc": 1,
    }
    p = pool(
        ("SELECT visit_id FROM public.visit", VISIT),
        (
            "SELECT v.status, v.clinic_patient_id::text",
            {
                "status": "FINALIZED",
                "clinic_patient_id": BS1,
                "attending_doctor_id": ME,
                "record_revision": 5,
                "was_released": False,
            },
        ),
        ("SELECT attending_doctor_id::text FROM public.visit", ME),
        ("SELECT r.id, r.drug_catalog_id", [old]),
        (
            "FROM public.clinical_record WHERE visit_id",
            {
                "soap_subjective": '"s"',
                "soap_objective": '"o"',
                "soap_assessment": '"a"',
                "soap_plan": '"p"',
            },
        ),
    )
    await ClinicalSignService(p).amend(
        identity=who(ClinicRole.DOCTOR),
        visit_id=VISIT,
        reason="Đổi thuốc sau khi ký",
        corrected={
            "don_thuoc": [
                {
                    "id": rx,
                    "drug_name": "Thuốc mới",
                    "quantity": "10 viên",
                    "dosage": "Sáng 1",
                }
            ]
        },
        expected_revision=5,
        expected_rx=prescription_fingerprint([old]),
    )

    queries = [query for _, query, _ in p.calls]
    visit_lock = next(
        i
        for i, query in enumerate(queries)
        if "SELECT visit_id FROM public.visit" in query and "FOR UPDATE" in query
    )
    rx_lock = next(i for i, query in enumerate(queries) if "FOR UPDATE OF r" in query)
    allocation_lock = next(
        i
        for i, query in enumerate(queries)
        if "FROM public.prescription_allocation" in query and "FOR UPDATE" in query
    )
    assert visit_lock < rx_lock < allocation_lock


@pytest.mark.asyncio
async def test_ky_sieu_am_theo_bac_si_nhan_ca(monkeypatch: pytest.MonkeyPatch) -> None:
    from clinicai.services.clinical_sign_service import ClinicalSignService

    svc = ClinicalSignService
    sa = who(ClinicRole.ULTRASOUND_DOCTOR)
    with pytest.raises(ValidationError, match="Không tìm thấy"):
        await svc(pool()).sign_ultrasound(identity=sa, ultrasound_id="u")
    assert (
        await svc(
            pool(
                (
                    "SELECT performed_by, signed_at",
                    {"performed_by": None, "signed_at": 1},
                )
            )
        ).sign_ultrasound(identity=sa, ultrasound_id="u")
    )["already_signed"]
    with pytest.raises(ValidationError, match="thực hiện"):
        await svc(
            pool(
                (
                    "SELECT performed_by, signed_at",
                    {"performed_by": BS1, "signed_at": None},
                ),
                ("SELECT w.assigned_to::text", BS1),
            )
        ).sign_ultrasound(identity=sa, ultrasound_id="u")
    ok = pool(
        ("SELECT performed_by, signed_at", {"performed_by": BS1, "signed_at": None}),
        ("SELECT w.assigned_to::text", ME),
    )
    assert (await svc(ok).sign_ultrasound(identity=sa, ultrasound_id="u"))["signed"]
    # 28/09: ký hỏi QUYỀN duyệt kết quả (không hỏi vai) — người không có quyền
    # thì dừng ở cửa quyền, trước mọi truy vấn.
    from tests.quyen_gia import doi_quyen_theo_nhom_mau

    monkeypatch.setattr(
        "clinicai.services.clinical_sign_service.doi_quyen", doi_quyen_theo_nhom_mau
    )
    with pytest.raises(SafetyGateError):
        await svc(pool()).sign_ultrasound(
            identity=who(ClinicRole.CSKH), ultrasound_id="u"
        )
