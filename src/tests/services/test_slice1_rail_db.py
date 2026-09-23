"""Slice 1 trên Postgres thật: chỉ định → thực hiện → kết quả → đọc lại → theo dõi.

Bốn contract (HANDOFF-NOW §3), mỗi contract ít nhất một ca:
  * PERFORMED — làm xong là đạt, khách quay lại bác sĩ.
  * VALID_RESULT — lấy mẫu xong CHƯA đủ; kết quả gắn vào chỉ định mới đủ.
  * FOLLOW_UP — không giữ lượt chờ; mở follow_up_case có người phụ trách và hạn.
  * NOT_PERFORMED — không tự đạt; bác sĩ phải miễn/chuyển theo dõi, có lý do,
    có nhật ký.

Dùng lại kịch bản của ``test_luot_kham_service_db`` (người và lượt riêng mỗi
test, không cần dọn).
"""

from __future__ import annotations

from typing import Any

import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.core.exceptions import SafetyGateError
from clinicai.services.luot_kham_service import LuotKhamConflictError
from clinicai.services.tep_ket_qua_service import TepKetQuaService
from tests.services.test_luot_kham_service_db import (
    KichBan,
    _cua,
    _vao_kham,
    dieu_phoi_cu,
)

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest.fixture(autouse=True)
def _vong_doc_chay_ngay(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tệp kết quả → khối VÒNG ĐỌC (sự kiện, 24/09): chạy ngay như worker."""
    from tests.chay_nguoi_dua_tin import vong_doc_chay_ngay_sau_lenh_tep

    vong_doc_chay_ngay_sau_lenh_tep(monkeypatch)


@pytest.fixture(autouse=True)
def _bat_buoc_xac_nhan_tep_doi_tac(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bước xác nhận tệp đối tác OFF từ 23/09/2026 khuya (tệp vào thẳng phiếu
    khám). Bài này canh ĐƯỜNG CŨ (còn giữ, bật lại được) nên bật cờ."""
    import clinicai.services.tep_ket_qua_service as tep_mod

    monkeypatch.setattr(tep_mod, "XAC_NHAN_TEP_DOI_TAC", True)


async def _chi_dinh(kb: KichBan, phien: str, *ma: str) -> list[str]:
    duyet = await kb.svc.authorize_orders(
        consultation_id=phien,
        service_codes=list(ma),
        draft_order_ids=None,
        identity=kb.bac_si,
    )
    return list(duyet["order_ids"])


async def _lam(kb: KichBan, oid: str, *, performed: bool = True, **kw: Any) -> None:
    """Xếp phòng (nếu chưa), bắt đầu, xong — như người thực hiện bấm."""
    ex = await kb.pool.fetchval(
        "SELECT exec_status FROM service_order WHERE id = $1::uuid", oid
    )
    if ex == "authorized":
        node = await kb.pool.fetchval(
            "SELECT node_code FROM service_order WHERE id = $1::uuid", oid
        )
        await dieu_phoi_cu(
            kb.svc,
            order_id=oid,
            room_id=kb.phong_sa if node == "DICHVU-SIEUAM" else kb.phong_mau,
            expected_version=None,
            identity=kb.truong_ca,
        )
    nguoi = kb.bs_sieu_am if kw.pop("sa", False) else kb.dieu_duong
    await kb.svc.start_service(order_id=oid, identity=nguoi)
    await kb.svc.complete_service(
        order_id=oid,
        performed=performed,
        reason=kw.get("reason"),
        result_note=kw.get("result_note"),
        identity=nguoi,
    )


async def _vong(kb: KichBan) -> list[dict[str, Any]]:
    return list(_cua(await kb.svc.bang(identity=kb.bac_si), kb.visit_id)["vong"])


async def _da_khep(kb: KichBan) -> bool:
    return bool(
        await kb.pool.fetchval(
            "SELECT finished_at IS NOT NULL FROM encounter_flow"
            " WHERE visit_id = $1::uuid",
            kb.visit_id,
        )
    )


async def _cho_doc(kb: KichBan) -> list[str]:
    rows = await kb.pool.fetch(
        "SELECT status FROM queue_entry WHERE visit_id = $1::uuid"
        " AND reason = 'REVIEW' AND status NOT IN ('done','left','cancelled')",
        kb.visit_id,
    )
    return [r["status"] for r in rows]


# ── mức cần mặc định ───────────────────────────────────────────────────────


async def test_kham_xong_lay_mau_gui_ngoai_mac_dinh_can_ket_qua(kb: KichBan) -> None:
    phien = await _vao_kham(kb)
    mau, sa = await _chi_dinh(kb, phien, kb.ma_mau, kb.ma_sa)
    await kb.svc.kham_xong(consultation_id=phien, identity=kb.bac_si)
    [vong] = await _vong(kb)
    can = {y["chi_dinh_id"]: y["can"] for y in vong["yeu_cau"]}
    assert can == {mau: "VALID_RESULT", sa: "PERFORMED"}


# ── VALID_RESULT ───────────────────────────────────────────────────────────


async def test_lay_mau_xong_chua_du_phai_co_ket_qua(kb: KichBan) -> None:
    phien = await _vao_kham(kb)
    [mau] = await _chi_dinh(kb, phien, kb.ma_mau)
    await kb.svc.complete_consultation(
        consultation_id=phien,
        outcome="SERVICES",
        requirements=[{"order_id": mau, "need": "VALID_RESULT"}],
        identity=kb.bac_si,
    )
    await _lam(kb, mau)  # lấy mẫu xong, chưa có kết quả
    [vong] = await _vong(kb)
    assert vong["trang_thai"] == "collecting"
    assert await _cho_doc(kb) == []
    assert not await _da_khep(kb)

    # Tệp kết quả tải lên (ở trạng thái CHO_XAC_NHAN) -> vẫn chưa đủ (Blocker 1)
    khach = await kb.pool.fetchval(
        "SELECT clinic_patient_id::text FROM visit WHERE visit_id = $1::uuid",
        kb.visit_id,
    )
    tep = await TepKetQuaService(kb.pool).tai_len(
        identity=kb.dieu_duong,
        clinic_patient_id=khach,
        data=b"%PDF-1.4\n%%EOF\n",
        ten_hien_thi="ket-qua-mau.pdf",
        service_order_id=mau,
    )
    [vong] = await _vong(kb)
    assert vong["trang_thai"] == "collecting"

    # Xác nhận HOP_LE (yêu cầu capability ket_qua.xac_nhan) -> vòng SẴN SÀNG
    await kb.pool.execute(
        "INSERT INTO capability_grant (clinic_id, staff_id, capability, tu_khoi)"
        " VALUES ($2::uuid, $1::uuid, 'result.file.confirm', 'xac_nhan_ket_qua')"
        " ON CONFLICT DO NOTHING",
        kb.truong_ca.staff_id,
        kb.truong_ca.clinic_id,
    )
    await TepKetQuaService(kb.pool).xac_nhan_tep(
        identity=kb.truong_ca,
        tep_id=str(tep["id"]),
        trang_thai="HOP_LE",
    )
    [vong] = await _vong(kb)
    assert vong["trang_thai"] == "ready"
    assert vong["yeu_cau"][0]["trang_thai"] == "satisfied"
    assert await _cho_doc(kb) == ["waiting"]


async def test_ghi_ket_qua_luc_xong_dich_vu_la_du(kb: KichBan) -> None:
    phien = await _vao_kham(kb)
    [sa] = await _chi_dinh(kb, phien, kb.ma_sa)
    await kb.svc.complete_consultation(
        consultation_id=phien,
        outcome="SERVICES",
        requirements=[{"order_id": sa, "need": "VALID_RESULT"}],
        identity=kb.bac_si,
    )
    await _lam(kb, sa, sa=True, result_note="Tử cung bình thường.")
    [vong] = await _vong(kb)
    assert vong["trang_thai"] == "ready"


# ── PERFORMED ──────────────────────────────────────────────────────────────


async def test_performed_la_du_khach_quay_lai_bac_si_roi_khep(kb: KichBan) -> None:
    phien = await _vao_kham(kb)
    [sa] = await _chi_dinh(kb, phien, kb.ma_sa)
    await kb.svc.kham_xong(consultation_id=phien, identity=kb.bac_si)
    await _lam(kb, sa, sa=True)
    assert await _cho_doc(kb) == ["waiting"]
    phien2 = next(
        p["id"]
        for p in _cua(await kb.svc.bang(identity=kb.bac_si), kb.visit_id)["phien"]
        if p["loai"] == "REVIEW"
    )
    await kb.svc.start_consultation(consultation_id=phien2, identity=kb.bac_si)
    assert (await _vong(kb))[0]["trang_thai"] == "in_review"
    await kb.svc.kham_xong(consultation_id=phien2, identity=kb.bac_si)
    assert (await _vong(kb))[0]["trang_thai"] == "closed"
    assert await _da_khep(kb)


# ── FOLLOW_UP ──────────────────────────────────────────────────────────────


async def test_theo_doi_khong_mo_vong_doc_va_khep_khi_lam_xong(kb: KichBan) -> None:
    phien = await _vao_kham(kb)
    [mau] = await _chi_dinh(kb, phien, kb.ma_mau)
    await kb.svc.kham_xong(
        consultation_id=phien,
        identity=kb.bac_si,
        ke_hoach={mau: "FOLLOW_UP"},
    )
    assert await _vong(kb) == []
    f = await kb.pool.fetchrow(
        "SELECT status, owner_staff_id::text AS owner, due_at, visit_id::text AS v,"
        " created_by::text AS by FROM follow_up_case WHERE service_order_id ="
        " $1::uuid",
        mau,
    )
    assert f is not None
    assert (f["status"], f["owner"], f["v"], f["by"]) == (
        "OPEN",
        kb.bac_si.staff_id,
        kb.visit_id,
        kb.bac_si.staff_id,
    )
    assert f["due_at"] is not None
    assert not await _da_khep(kb)  # mẫu chưa lấy
    await _lam(kb, mau)
    assert await _da_khep(kb)  # không chờ kết quả
    assert await _cho_doc(kb) == []


async def test_thu_ky_khong_tu_cho_khach_ve_theo_doi(kb: KichBan) -> None:
    phien = await _vao_kham(kb)
    [mau] = await _chi_dinh(kb, phien, kb.ma_mau)
    await kb.pool.execute(
        "INSERT INTO thu_ky_bac_si (clinic_id, thu_ky_staff_id, bac_si_staff_id)"
        " VALUES ($1::uuid, $2::uuid, $3::uuid) ON CONFLICT DO NOTHING",
        kb.bac_si.clinic_id,
        kb.thu_ky.staff_id,
        kb.bac_si.staff_id,
    )
    with pytest.raises(SafetyGateError):
        await kb.svc.kham_xong(
            consultation_id=phien,
            identity=kb.thu_ky,
            ke_hoach={mau: "FOLLOW_UP"},
        )


async def test_ket_qua_muon_chuyen_theo_doi_roi_duyet_sau_khi_ky(
    kb: KichBan,
) -> None:
    phien = await _vao_kham(kb)
    [mau] = await _chi_dinh(kb, phien, kb.ma_mau)
    await kb.svc.kham_xong(consultation_id=phien, identity=kb.bac_si)
    await _lam(kb, mau)
    [vong] = await _vong(kb)
    assert vong["trang_thai"] == "collecting"  # chờ kết quả
    rid = await kb.pool.fetchval(
        "SELECT id::text FROM round_requirement WHERE service_order_id = $1::uuid",
        mau,
    )
    # Thiếu lý do → từ chối.
    with pytest.raises(ValidationError):
        await kb.svc.quyet_yeu_cau(
            requirement_id=rid, hanh_dong="FOLLOW_UP", ly_do="  ", identity=kb.bac_si
        )
    await kb.svc.quyet_yeu_cau(
        requirement_id=rid,
        hanh_dong="FOLLOW_UP",
        ly_do="Kết quả đối tác trả sau 3 ngày",
        han="2026-09-21",
        identity=kb.bac_si,
    )
    [vong] = await _vong(kb)
    assert vong["trang_thai"] == "closed"  # không giữ khách chờ đọc
    assert vong["yeu_cau"][0]["trang_thai"] == "follow_up"
    assert await _cho_doc(kb) == []
    assert await _da_khep(kb)
    q = await kb.pool.fetchrow(
        "SELECT waived_by::text AS by, waived_reason, followup_owner::text AS owner,"
        " followup_due::text AS due, follow_up_case_id IS NOT NULL AS co_case"
        " FROM round_requirement WHERE id = $1::uuid",
        rid,
    )
    assert q is not None
    assert (q["by"], q["owner"], q["due"], q["co_case"]) == (
        kb.bac_si.staff_id,
        kb.bac_si.staff_id,
        "2026-09-21",
        True,
    )
    # Bác sĩ ký bệnh án (lượt FINALIZED) rồi kết quả mới về: vẫn duyệt được, và
    # duyệt xong thì việc theo dõi đóng.
    khach = await kb.pool.fetchval(
        "SELECT clinic_patient_id::text FROM visit WHERE visit_id = $1::uuid",
        kb.visit_id,
    )
    tep = await TepKetQuaService(kb.pool).tai_len(
        identity=kb.dieu_duong,
        clinic_patient_id=khach,
        data=b"%PDF-1.4\n%%EOF\n",
        ten_hien_thi="ket-qua-mau.pdf",
        service_order_id=mau,
    )
    await kb.pool.execute(
        "INSERT INTO capability_grant (clinic_id, staff_id, capability, tu_khoi)"
        " VALUES ($2::uuid, $1::uuid, 'result.file.confirm', 'xac_nhan_ket_qua')"
        " ON CONFLICT DO NOTHING",
        kb.truong_ca.staff_id,
        kb.truong_ca.clinic_id,
    )
    await TepKetQuaService(kb.pool).xac_nhan_tep(
        identity=kb.truong_ca,
        tep_id=str(tep["id"]),
        trang_thai="HOP_LE",
    )
    await kb.pool.execute(
        "UPDATE visit SET status = 'FINALIZED' WHERE visit_id = $1::uuid",
        kb.visit_id,
    )
    await kb.svc.duyet_ket_qua(order_id=mau, danh_gia=None, identity=kb.bac_si)
    assert (
        await kb.pool.fetchval(
            "SELECT status FROM follow_up_case WHERE service_order_id = $1::uuid", mau
        )
        == "DONE"
    )


# ── NOT_PERFORMED ──────────────────────────────────────────────────────────


async def _khong_lam_duoc(kb: KichBan) -> tuple[str, str, str]:
    """Hai dịch vụ, siêu âm làm xong, lấy mẫu KHÔNG làm được. Trả
    (phiên đọc, mã yêu cầu lấy mẫu, mã chỉ định lấy mẫu)."""
    phien = await _vao_kham(kb)
    mau, sa = await _chi_dinh(kb, phien, kb.ma_mau, kb.ma_sa)
    await kb.svc.kham_xong(consultation_id=phien, identity=kb.bac_si)
    await _lam(kb, sa, sa=True)
    await _lam(kb, mau, performed=False, reason="Khách sợ kim, từ chối lấy máu")
    phien2 = next(
        p["id"]
        for p in _cua(await kb.svc.bang(identity=kb.bac_si), kb.visit_id)["phien"]
        if p["loai"] == "REVIEW"
    )
    rid = await kb.pool.fetchval(
        "SELECT id::text FROM round_requirement WHERE service_order_id = $1::uuid",
        mau,
    )
    return str(phien2), str(rid), mau


async def test_khong_thuc_hien_khong_tu_dat_bac_si_phai_quyet(kb: KichBan) -> None:
    phien2, rid, _ = await _khong_lam_duoc(kb)
    # Khách được đưa về bác sĩ (không kẹt ở "đang thu")…
    assert await _cho_doc(kb) == ["waiting"]
    [vong] = await _vong(kb)
    # Trạng thái lưu vẫn là "open" — không thực hiện KHÔNG thành "satisfied".
    assert {y["trang_thai"] for y in vong["yeu_cau"]} == {"satisfied", "open"}
    # …nhưng không đóng vòng được khi chưa quyết.
    await kb.svc.start_consultation(consultation_id=phien2, identity=kb.bac_si)
    with pytest.raises(LuotKhamConflictError) as e:
        await kb.svc.kham_xong(consultation_id=phien2, identity=kb.bac_si)
    assert e.value.error_code == "REQUIREMENT_DECISION_REQUIRED"
    assert not await _da_khep(kb)


async def test_chi_bac_si_phu_trach_quyet_va_co_nhat_ky(kb: KichBan) -> None:
    phien2, rid, mau = await _khong_lam_duoc(kb)
    for nguoi in (kb.thu_ky, kb.bac_si_2):
        with pytest.raises(SafetyGateError):
            await kb.svc.quyet_yeu_cau(
                requirement_id=rid,
                hanh_dong="WAIVE",
                ly_do="Không cần",
                identity=nguoi,
            )
    await kb.svc.quyet_yeu_cau(
        requirement_id=rid,
        hanh_dong="WAIVE",
        ly_do="Đổi kế hoạch: làm xét nghiệm lần tái khám",
        identity=kb.bac_si,
    )
    with pytest.raises(LuotKhamConflictError) as e:
        await kb.svc.quyet_yeu_cau(
            requirement_id=rid, hanh_dong="WAIVE", ly_do="Lần hai", identity=kb.bac_si
        )
    assert e.value.error_code == "REQUIREMENT_DECIDED"
    ev = await kb.pool.fetchrow(
        "SELECT payload, metadata FROM event_log WHERE event_type ="
        " 'requirement.waived' AND aggregate_id = $1::uuid",
        kb.visit_id,
    )
    assert ev is not None
    assert rid in str(ev["payload"]) and "Đổi kế hoạch" not in str(ev["payload"])
    assert kb.bac_si.staff_id in str(ev["metadata"])
    await kb.svc.start_consultation(consultation_id=phien2, identity=kb.bac_si)
    await kb.svc.kham_xong(consultation_id=phien2, identity=kb.bac_si)
    assert await _da_khep(kb)
    assert (
        await kb.pool.fetchval(
            "SELECT status FROM round_requirement WHERE id = $1::uuid", rid
        )
        == "waived"
    )


# ── checkout đọc rail mới ─────────────────────────────────────────────────


async def test_checkout_doc_rail_moi(kb: KichBan) -> None:
    from clinicai.services.checkout_service import CheckoutService

    quay = CheckoutService(kb.pool)

    async def vuong() -> tuple[set[str], int]:
        r = await quay.readiness(identity=kb.le_tan, visit_id=kb.visit_id)
        return {str(b["type"]) for b in r["blockers"]}, int(r["so_theo_doi"])

    phien = await _vao_kham(kb)
    [mau] = await _chi_dinh(kb, phien, kb.ma_mau)
    loai, _ = await vuong()
    assert {"service_open", "exam_open"} <= loai
    await kb.svc.kham_xong(consultation_id=phien, identity=kb.bac_si)
    await _lam(kb, mau)
    loai, _ = await vuong()
    # Mẫu đã lấy, kết quả chưa về: quầy thấy bác sĩ còn chờ kết quả.
    assert "service_open" not in loai and "lab_pending" in loai
    rid = await kb.pool.fetchval(
        "SELECT id::text FROM round_requirement WHERE service_order_id = $1::uuid",
        mau,
    )
    await kb.svc.quyet_yeu_cau(
        requirement_id=rid,
        hanh_dong="FOLLOW_UP",
        ly_do="Kết quả về sau",
        identity=kb.bac_si,
    )
    loai, so_theo_doi = await vuong()
    assert not loai & {"service_open", "lab_pending", "exam_open"}
    assert so_theo_doi == 1


async def test_checkout_chi_tiet_khong_lam_duoc_khong_hien_la_xong(
    kb: KichBan,
) -> None:
    """Smoke 18/09: dịch vụ KHÔNG làm được hiện "✓ Xong" ở màn check-out."""
    from clinicai.services.checkout_service import CheckoutService

    await _khong_lam_duoc(kb)
    ct = await CheckoutService(kb.pool).chi_tiet(
        identity=kb.le_tan, visit_id=kb.visit_id
    )
    trang_thai = sorted(d["status"] for d in ct["dich_vu"] if d["ten"] != "Khám")
    assert "NOT_PERFORMED" in trang_thai
    assert trang_thai.count("NOT_PERFORMED") == 1


async def test_checkout_chi_tiet_moc_that_va_tep_that(kb: KichBan) -> None:
    """Smoke 18/09: dòng thời gian check-out hiện bước DỰ KIẾN (work_item tạo
    lúc check-in) như việc đã làm, và mục hồ sơ báo "chưa có kho lưu tệp" dù
    tệp kết quả đã có."""
    from clinicai.services.checkout_service import CheckoutService
    from clinicai.services.tep_ket_qua_service import TepKetQuaService

    phien = await _vao_kham(kb)
    [sa] = await _chi_dinh(kb, phien, kb.ma_sa)
    await kb.svc.kham_xong(consultation_id=phien, identity=kb.bac_si)
    await _lam(kb, sa, sa=True, result_note="Bình thường")
    khach = await kb.pool.fetchval(
        "SELECT clinic_patient_id::text FROM visit WHERE visit_id = $1::uuid",
        kb.visit_id,
    )
    await TepKetQuaService(kb.pool).tai_len(
        identity=kb.bs_sieu_am,
        clinic_patient_id=khach,
        data=b"%PDF-1.4\n%%EOF\n",
        ten_hien_thi="phieu-sa.pdf",
        service_order_id=sa,
    )
    ct = await CheckoutService(kb.pool).chi_tiet(
        identity=kb.le_tan, visit_id=kb.visit_id
    )
    da_ghi = {
        r["event_type"]
        for r in await kb.pool.fetch(
            "SELECT event_type FROM event_log WHERE aggregate_id = $1::uuid",
            kb.visit_id,
        )
    }
    assert ct["moc_thoi_gian"], "phải có mốc thật"
    # Mọi mốc là một sự kiện đã ghi — không có bước "create" dự kiến.
    assert {m["lenh"] for m in ct["moc_thoi_gian"]} <= da_ghi | {
        r["event_type"]
        for r in await kb.pool.fetch(
            "SELECT e.event_type FROM event_log e JOIN visit v"
            " ON e.aggregate_id = v.appointment_id WHERE v.visit_id = $1::uuid",
            kb.visit_id,
        )
    }
    assert "service.performed" in {m["lenh"] for m in ct["moc_thoi_gian"]}
    [tep] = ct["ho_so_tra"]["muc"]
    assert tep["ten"] == "phieu-sa.pdf"
    assert tep["trang_thai"] in {"CHO_BAC_SI", "DUOC_GUI"}


# ── CSKH kết quả muộn đọc rail mới ─────────────────────────────────────────


async def test_cskh_ket_qua_muon_doc_rail_moi(kb: KichBan) -> None:
    async def viec() -> list[tuple[str, str]]:
        rows = await kb.pool.fetch(
            "SELECT trang_thai, han_xu_ly::text AS han FROM v_viec_cskh v"
            " JOIN visit vi ON vi.clinic_patient_id = v.clinic_patient_id"
            " WHERE vi.visit_id = $1::uuid"
            " AND trang_thai IN ('CHO_KQ_XN', 'CHO_BAC_SI', 'KQ_CHUA_GUI')",
            kb.visit_id,
        )
        return sorted((r["trang_thai"], r["han"]) for r in rows)

    phien = await _vao_kham(kb)
    [mau] = await _chi_dinh(kb, phien, kb.ma_mau)
    await kb.svc.kham_xong(
        consultation_id=phien,
        identity=kb.bac_si,
        ke_hoach={mau: "FOLLOW_UP"},
    )
    assert await viec() == []  # chưa lấy mẫu thì chưa có gì để chờ
    await _lam(kb, mau)
    han = await kb.pool.fetchval(
        "SELECT (due_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date::text"
        " FROM follow_up_case WHERE service_order_id = $1::uuid",
        mau,
    )
    assert await viec() == [("CHO_KQ_XN", han)]
    # Tệp kết quả về và được xác nhận HOP_LE: CSKH gửi được NGAY — không còn
    # "chờ bác sĩ duyệt" (Tuyền chốt 23/09/2026, migration 20260923000021).
    khach = await kb.pool.fetchval(
        "SELECT clinic_patient_id::text FROM visit WHERE visit_id = $1::uuid",
        kb.visit_id,
    )
    tep = await TepKetQuaService(kb.pool).tai_len(
        identity=kb.dieu_duong,
        clinic_patient_id=khach,
        data=b"%PDF-1.4\n%%EOF\n",
        ten_hien_thi="ket-qua-mau.pdf",
        service_order_id=mau,
    )
    await kb.pool.execute(
        "INSERT INTO capability_grant (clinic_id, staff_id, capability, tu_khoi)"
        " VALUES ($2::uuid, $1::uuid, 'result.file.confirm', 'xac_nhan_ket_qua')"
        " ON CONFLICT DO NOTHING",
        kb.truong_ca.staff_id,
        kb.truong_ca.clinic_id,
    )
    await TepKetQuaService(kb.pool).xac_nhan_tep(
        identity=kb.truong_ca,
        tep_id=str(tep["id"]),
        trang_thai="HOP_LE",
    )
    assert [t for t, _ in await viec()] == ["KQ_CHUA_GUI"]
    # Bác sĩ duyệt vẫn làm được (việc chuyên môn của bác sĩ) nhưng không đổi
    # việc của CSKH: tệp chưa gửi thì vẫn là việc "chưa gửi".
    await kb.svc.duyet_ket_qua(order_id=mau, danh_gia=None, identity=kb.bac_si)
    assert [t for t, _ in await viec()] == ["KQ_CHUA_GUI"]
    await TepKetQuaService(kb.pool).danh_dau_da_gui(
        identity=kb.truong_ca, tep_id=str(tep["id"]), kenh="ZALO"
    )
    assert await viec() == []


# ── bác sĩ thấy việc chờ mình quyết ───────────────────────────────────────


async def test_bac_si_thay_viec_cho_ket_qua_va_can_quyet(kb: KichBan) -> None:
    phien = await _vao_kham(kb)
    mau, sa = await _chi_dinh(kb, phien, kb.ma_mau, kb.ma_sa)
    await kb.svc.kham_xong(consultation_id=phien, identity=kb.bac_si)

    async def cua(ai: Any) -> list[tuple[str, str]]:
        kq = await kb.svc.cho_quyet(identity=ai)
        return sorted(
            (v["dich_vu"], v["trang_thai"])
            for v in kq["viec"]
            if v["visit_id"] == kb.visit_id
        )

    assert await cua(kb.bac_si) == []  # chưa làm gì: việc của phòng dịch vụ
    await _lam(kb, mau)
    await _lam(kb, sa, sa=True, performed=False, reason="Máy siêu âm hỏng")
    ten_mau, ten_sa = [
        await kb.pool.fetchval(
            "SELECT service_name FROM service_order WHERE id = $1::uuid", o
        )
        for o in (mau, sa)
    ]
    assert await cua(kb.bac_si) == sorted(
        [(ten_mau, "cho_ket_qua"), (ten_sa, "can_quyet")]
    )
    assert await cua(kb.bac_si_2) == []  # khách của bác sĩ khác
    kq = await kb.svc.cho_quyet(identity=kb.bac_si)
    assert kq["duoc_quyet"] is True


# ── không để việc theo dõi mồ côi (rà độc lập 18/09) ──────────────────────


async def test_khong_lam_duoc_thi_chi_mien_khong_theo_doi(kb: KichBan) -> None:
    _, rid, _ = await _khong_lam_duoc(kb)
    with pytest.raises(LuotKhamConflictError) as e:
        await kb.svc.quyet_yeu_cau(
            requirement_id=rid,
            hanh_dong="FOLLOW_UP",
            ly_do="Hẹn làm sau",
            identity=kb.bac_si,
        )
    assert e.value.error_code == "FOLLOW_UP_NEEDS_RESULT"


async def test_yeu_cau_da_dat_khong_quyet_lai(kb: KichBan) -> None:
    phien = await _vao_kham(kb)
    [sa] = await _chi_dinh(kb, phien, kb.ma_sa)
    await kb.svc.kham_xong(consultation_id=phien, identity=kb.bac_si)
    await _lam(kb, sa, sa=True)
    rid = await kb.pool.fetchval(
        "SELECT id::text FROM round_requirement WHERE service_order_id = $1::uuid",
        sa,
    )
    with pytest.raises(LuotKhamConflictError) as e:
        await kb.svc.quyet_yeu_cau(
            requirement_id=rid, hanh_dong="WAIVE", ly_do="x", identity=kb.bac_si
        )
    assert e.value.error_code == "REQUIREMENT_SATISFIED"


async def test_theo_doi_huy_khi_mau_khong_lay_duoc(kb: KichBan) -> None:
    phien = await _vao_kham(kb)
    [mau] = await _chi_dinh(kb, phien, kb.ma_mau)
    with pytest.raises(ValidationError):
        await kb.svc.kham_xong(
            consultation_id=phien,
            identity=kb.bac_si,
            ke_hoach={mau: {"need": "FOLLOW_UP", "han": "2026-13-40"}},
        )
    await kb.svc.kham_xong(
        consultation_id=phien, identity=kb.bac_si, ke_hoach={mau: "FOLLOW_UP"}
    )
    await _lam(kb, mau, performed=False, reason="Khách về trước khi lấy máu")
    assert (
        await kb.pool.fetchval(
            "SELECT status FROM follow_up_case WHERE service_order_id = $1::uuid", mau
        )
        == "CANCELLED"
    )
    assert await _da_khep(kb)
