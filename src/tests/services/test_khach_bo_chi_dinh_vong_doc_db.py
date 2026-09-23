"""Khách BỎ một chỉ định → vòng đọc không được treo (24/09/2026).

Bộ mô phỏng 20 khách (K04) bắt được: khách chọn làm siêu âm, bỏ xét nghiệm;
siêu âm xong mà vòng đọc vẫn "collecting" mãi — yêu cầu "cần kết quả" của xét
nghiệm khách bỏ không bao giờ đạt. Bác sĩ không được báo, lượt treo.

Luật sau khi sửa (cùng khuôn chỉ định KHÔNG THỰC HIỆN): chỉ định khách không
chọn → yêu cầu thành "bác sĩ quyết" (miễn / theo dõi). Không tự bỏ qua kết quả
(CONTEXT v1.0) — vòng mở để BÁC SĨ quyết, không tự đóng.
"""

from __future__ import annotations

import uuid

import pytest

from clinicai.services import luot_kham_rules as rules
from clinicai.services.service_selection_service import ServiceSelectionService
from tests.chay_nguoi_dua_tin import chay_ben_nhan
from tests.services.test_luot_kham_service_db import (
    KichBan,
    _cua,
    _hanh_trinh,
    _vao_kham,
    dieu_phoi_cu,
)

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


def test_luat_khach_khong_chon_la_viec_bac_si_quyet() -> None:
    bo = rules.RequirementView(
        "o1", "VALID_RESULT", "open", "authorized", False, "NOT_SELECTED"
    )
    lam = rules.RequirementView(
        "o2", "PERFORMED", "open", "performed", False, "SELECTED"
    )
    assert rules.requirement_state(bo) == "needs_decision"
    assert rules.round_ready([bo, lam])
    assert rules.can_quyet([bo, lam]) == ["o1"]
    # Không tự đóng vòng: chỉ đóng khi mọi yêu cầu đã được miễn / theo dõi.
    assert not rules.vong_khong_can_doc([bo, lam])


async def test_khach_bo_mot_chi_dinh_vong_doc_van_mo_cho_bac_si(kb: KichBan) -> None:
    phien = await _vao_kham(kb)
    duyet = await kb.svc.authorize_orders(
        consultation_id=phien,
        service_codes=[kb.ma_sa, kb.ma_mau],
        draft_order_ids=None,
        identity=kb.bac_si,
    )
    sa_id, mau_id = duyet["order_ids"]
    await kb.svc.kham_xong(consultation_id=phien, identity=kb.bac_si)
    await _hanh_trinh(kb.pool)

    # Khách chỉ làm siêu âm, BỎ xét nghiệm.
    await ServiceSelectionService(kb.pool).confirm(
        visit_id=kb.visit_id,
        order_ids_seen=[sa_id, mau_id],
        selected_order_ids=[sa_id],
        expected_selection_revision=0,
        identity=kb.le_tan,
        idempotency_key=uuid.uuid4().hex,
    )
    await chay_ben_nhan(kb.pool, "vong_doc_luot_kham")
    await dieu_phoi_cu(
        kb.svc,
        order_id=sa_id,
        room_id=kb.phong_sa,
        expected_version=None,
        identity=kb.truong_ca,
    )
    await kb.svc.start_service(order_id=sa_id, identity=kb.bs_sieu_am)
    await kb.svc.complete_service(
        order_id=sa_id,
        performed=True,
        reason=None,
        result_note="Bình thường.",
        identity=kb.bs_sieu_am,
    )
    await chay_ben_nhan(kb.pool, "vong_doc_luot_kham")

    luot = _cua(await kb.svc.bang(identity=kb.bac_si), kb.visit_id)
    vong = luot["vong"][-1]
    assert vong["trang_thai"] == "ready", vong
    yc = {y["chi_dinh_id"]: y["trang_thai"] for y in vong["yeu_cau"]}
    assert yc[mau_id] == "needs_decision"
    assert [p["loai"] for p in luot["phien"] if p["trang_thai"] == "queued"] == [
        "REVIEW"
    ]


async def test_mien_chi_dinh_khach_bo_roi_hoan_tat_thi_khep_luot(kb: KichBan) -> None:
    """Bác sĩ miễn chỉ định khách bỏ rồi Hoàn tất → KHÔNG mở vòng mới đòi lại nó
    (trước sửa: vòng 3 đòi lại → bác sĩ bị gọi mãi, lượt không khép)."""
    await test_khach_bo_mot_chi_dinh_vong_doc_van_mo_cho_bac_si(kb)
    luot = _cua(await kb.svc.bang(identity=kb.bac_si), kb.visit_id)
    review = next(p for p in luot["phien"] if p["trang_thai"] == "queued")
    await kb.svc.start_consultation(consultation_id=review["id"], identity=kb.bac_si)
    yc = await kb.pool.fetchval(
        "SELECT q.id::text FROM round_requirement q JOIN service_order o"
        " ON o.id = q.service_order_id WHERE o.visit_id = $1::uuid"
        " AND o.selection_status = 'NOT_SELECTED'",
        kb.visit_id,
    )
    await kb.svc.quyet_yeu_cau(
        requirement_id=yc,
        hanh_dong="WAIVE",
        ly_do="Khách không làm",
        identity=kb.bac_si,
    )
    await kb.svc.kham_xong(consultation_id=review["id"], identity=kb.bac_si)
    await chay_ben_nhan(kb.pool, "vong_doc_luot_kham")
    luot = _cua(await kb.svc.bang(identity=kb.bac_si), kb.visit_id)
    assert not [p for p in luot["phien"] if p["trang_thai"] == "queued"], luot["phien"]
    assert luot["ket_thuc_luc"] is not None
