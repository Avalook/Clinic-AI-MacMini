"""DB integration tests for Result File Confirmation queue & file read authorization.

Target:
1. Endpoint & Service: cho_xac_nhan(identity)
   - Fail-closed: 403 nếu không có capability ket_qua.xac_nhan.
   - PARTNER không bao giờ có quyền.
   - Quyền theo TỪNG phòng khám (CORE-B2): có quyền ở A thì làm ở A, sang B
     thì bị chặn. (Hệ cũ chặn hẳn người nhiều phòng khám vì quyền gắn theo
     người, không theo phòng khám — mơ hồ nên phải fail-closed.)
   - Trả về đúng tệp external (lam_ben_ngoai = true, service_order_id IS NOT NULL).
   - Loại trừ internal, orders bị hủy/draft, orders đã HOP_LE/TU_CHOI/THU_HOI.
   - Xếp theo thứ tự cũ nhất trước (tai_len_luc ASC, id ASC).
   - Tự tải lên (self-upload): co_the_xac_nhan = false và có thông báo lý do.
   - tai_len_boi_vai lấy từ clinic_membership.role (PARTNER -> "PARTNER").

2. Endpoint & Service: duong_dan_de_doc(identity, tep_id)
   - Nhóm vai đọc cũ (NORMAL_READ_ROLES) vẫn đọc bình thường mọi tệp.
   - Nhân viên không vai đọc cũ và không capability -> SafetyGateError (403).
   - Người chỉ có capability ket_qua.xac_nhan:
     * ĐƯỢC đọc tệp external đang CHO_XAC_NHAN cùng clinic.
     * KHÔNG ĐƯỢC đọc tệp internal (dù cùng clinic).
     * KHÔNG ĐƯỢC đọc tệp đã HOP_LE, TU_CHOI, THU_HOI.
     * KHÔNG ĐƯỢC đọc tệp khác clinic (cross-clinic fail).
"""

from __future__ import annotations

import dataclasses
import os
import pathlib
from typing import Any

import asyncpg
import pytest
import pytest_asyncio

from clinicai.api.exceptions import NotFoundError
from clinicai.core.exceptions import SafetyGateError
from clinicai.schemas.staff import Capability
from clinicai.services.tep_ket_qua_service import TepKetQuaService
from tests.services.test_xac_nhan_tep_ket_qua_db import (
    CLINIC_A,
    CLINIC_B,
    PDF_DUMMY,
    _tao_benh_nhan_va_visit,
    _tao_external_order,
    _tao_staff,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest.fixture(autouse=True)
def _bat_buoc_xac_nhan_tep_doi_tac(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bước xác nhận tệp đối tác OFF từ 23/09/2026 khuya (tệp vào thẳng phiếu
    khám). Bài này canh ĐƯỜNG CŨ (còn giữ, bật lại được) nên bật cờ."""
    import clinicai.services.tep_ket_qua_service as tep_mod

    monkeypatch.setattr(tep_mod, "XAC_NHAN_TEP_DOI_TAC", True)


@pytest_asyncio.fixture
async def pool() -> Any:
    url = os.environ.get("DATABASE_URL") or os.environ.get("DATABASE_URL_TEST") or ""
    if not url:
        pytest.skip("cần DATABASE_URL_TEST trỏ tới database dùng một lần")
    dsn = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    p = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=8)
    yield p
    await p.close()


async def test_cho_xac_nhan_queue_auth_fail_closed(pool: asyncpg.Pool) -> None:
    """Kiểm tra hàng chờ xác nhận fail-closed với ai không có capability."""
    async with pool.acquire() as conn:
        staff_no_cap = await _tao_staff(conn, CLINIC_A, "CASHIER")
        partner = await _tao_staff(
            conn, CLINIC_A, "PARTNER", caps=[Capability.KET_QUA_XAC_NHAN.value]
        )
        staff_multi = await _tao_staff(
            conn, CLINIC_A, "CASHIER", caps=[Capability.KET_QUA_XAC_NHAN.value]
        )
        # Tạo thêm active membership ở clinic B cho staff_multi
        await conn.execute(
            """
            INSERT INTO clinic (id, name, code)
            VALUES ($1::uuid, 'Clinic B Test', 'CLINIC_B')
            ON CONFLICT (id) DO NOTHING
            """,
            CLINIC_B,
        )
        await conn.execute(
            """
            INSERT INTO clinic_membership (clinic_id, staff_id, role, is_active)
            VALUES ($1::uuid, $2::uuid, 'CASHIER', true)
            ON CONFLICT (clinic_id, staff_id, role) DO UPDATE SET is_active = true
            """,
            CLINIC_B,
            staff_multi.staff_id,
        )

    svc = TepKetQuaService(pool)

    # 1. Không có capability -> 403
    with pytest.raises(SafetyGateError):
        await svc.cho_xac_nhan(identity=staff_no_cap)

    # 2. PARTNER dù có capability row vẫn bị cấm -> 403
    with pytest.raises(SafetyGateError):
        await svc.cho_xac_nhan(identity=partner)

    # 3. Quyền theo từng phòng khám (CORE-B2, capability_grant.clinic_id):
    #    cấp ở A → làm được ở A; đứng ở B (chưa ai cấp) → 403.
    assert isinstance(await svc.cho_xac_nhan(identity=staff_multi), list)
    with pytest.raises(SafetyGateError):
        await svc.cho_xac_nhan(
            identity=dataclasses.replace(staff_multi, clinic_id=CLINIC_B)
        )


async def test_cho_xac_nhan_queue_filters_and_ordering(
    pool: asyncpg.Pool, monkeypatch: Any, tmp_path: pathlib.Path
) -> None:
    """Kiểm tra hàng chờ xác nhận lọc đúng external CHO_XAC_NHAN, xếp cũ trước."""
    import clinicai.services.media_service as media
    import clinicai.services.tep_ket_qua_service as tep_mod

    monkeypatch.setattr(media, "MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(tep_mod, "MEDIA_ROOT", tmp_path)
    monkeypatch.delenv("MEDIA_MARKER", raising=False)

    async with pool.acquire() as conn:
        doc = await _tao_staff(conn, CLINIC_A, "DOCTOR")
        partner = await _tao_staff(conn, CLINIC_A, "PARTNER")
        confirmer = await _tao_staff(
            conn, CLINIC_A, "CASHIER", caps=[Capability.KET_QUA_XAC_NHAN.value]
        )
        pid, aid, vid = await _tao_benh_nhan_va_visit(conn, CLINIC_A, doc.staff_id)
        oid_ext = await _tao_external_order(conn, CLINIC_A, vid)

    svc = TepKetQuaService(pool)

    # 1. Tải tệp 1 (external, CHO_XAC_NHAN)
    res1 = await svc.tai_len(
        identity=partner,
        clinic_patient_id=pid,
        data=PDF_DUMMY,
        ten_hien_thi="file_1_old.pdf",
        service_order_id=oid_ext,
    )
    tep1_id = res1["id"]

    # 2. Tải tệp 2 (external, CHO_XAC_NHAN)
    res2 = await svc.tai_len(
        identity=partner,
        clinic_patient_id=pid,
        data=PDF_DUMMY,
        ten_hien_thi="file_2_new.pdf",
        service_order_id=oid_ext,
    )
    tep2_id = res2["id"]

    # 3. Tải tệp 3 (internal: không có service_order_id -> xac_nhan_trang_thai = NULL)
    res3 = await svc.tai_len(
        identity=doc,
        clinic_patient_id=pid,
        data=PDF_DUMMY,
        ten_hien_thi="file_internal.pdf",
    )
    tep3_id = res3["id"]

    # Chỉnh giờ tai_len_luc để đảm bảo tep1 < tep2
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE tep_ket_qua SET tai_len_luc = now() - interval '10 minutes' "
            "WHERE id = $1::uuid",
            tep1_id,
        )
        await conn.execute(
            "UPDATE tep_ket_qua SET tai_len_luc = now() - interval '5 minutes' "
            "WHERE id = $1::uuid",
            tep2_id,
        )

    queue = await svc.cho_xac_nhan(identity=confirmer)
    tep_ids_in_queue = [q["tep_id"] for q in queue]

    # Kiểm tra: tep1 và tep2 có trong queue, xếp cũ nhất trước
    assert tep1_id in tep_ids_in_queue
    assert tep2_id in tep_ids_in_queue
    assert tep_ids_in_queue.index(tep1_id) < tep_ids_in_queue.index(tep2_id)

    # Kiểm tra: tep3 (internal) không có trong queue
    assert tep3_id not in tep_ids_in_queue

    # Kiểm tra các trường dữ liệu của tệp trong queue
    item1 = next(q for q in queue if q["tep_id"] == tep1_id)
    assert item1["ten_khach"] == "Bệnh nhân test"
    assert item1["ten_dich_vu"] == "Dịch vụ gửi ngoài"
    assert item1["ten_hien_thi"] == "file_1_old.pdf"
    assert item1["tai_len_boi_vai"] == "PARTNER"
    assert item1["co_the_xac_nhan"] is True
    assert item1["khong_the_xac_nhan_ly_do"] is None

    # Xác nhận hợp lệ tệp 1 -> tệp 1 phải biến mất khỏi queue
    await svc.xac_nhan_tep(identity=confirmer, tep_id=tep1_id, trang_thai="HOP_LE")
    queue_after = await svc.cho_xac_nhan(identity=confirmer)
    assert tep1_id not in [q["tep_id"] for q in queue_after]
    assert tep2_id in [q["tep_id"] for q in queue_after]


async def test_cho_xac_nhan_queue_self_upload_blocked(
    pool: asyncpg.Pool, monkeypatch: Any, tmp_path: pathlib.Path
) -> None:
    """Người tải tệp có capability vẫn thấy dòng nhưng co_the_xac_nhan=False."""
    import clinicai.services.media_service as media
    import clinicai.services.tep_ket_qua_service as tep_mod

    monkeypatch.setattr(media, "MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(tep_mod, "MEDIA_ROOT", tmp_path)
    monkeypatch.delenv("MEDIA_MARKER", raising=False)

    async with pool.acquire() as conn:
        doc = await _tao_staff(conn, CLINIC_A, "DOCTOR")
        uploader_confirmer = await _tao_staff(
            conn, CLINIC_A, "CASHIER", caps=[Capability.KET_QUA_XAC_NHAN.value]
        )
        pid, aid, vid = await _tao_benh_nhan_va_visit(conn, CLINIC_A, doc.staff_id)
        oid_ext = await _tao_external_order(conn, CLINIC_A, vid)

    svc = TepKetQuaService(pool)

    res = await svc.tai_len(
        identity=uploader_confirmer,
        clinic_patient_id=pid,
        data=PDF_DUMMY,
        ten_hien_thi="self_upload.pdf",
        service_order_id=oid_ext,
    )
    tep_id = res["id"]

    queue = await svc.cho_xac_nhan(identity=uploader_confirmer)
    item = next(q for q in queue if q["tep_id"] == tep_id)

    assert item["co_the_xac_nhan"] is False
    assert (
        item["khong_the_xac_nhan_ly_do"]
        == "Bạn là người tải tệp này — cần người khác xác nhận."
    )

    # Thử gọi POST xác nhận -> bị backend chặn 403
    with pytest.raises(SafetyGateError, match="không được tự xác nhận"):
        await svc.xac_nhan_tep(
            identity=uploader_confirmer, tep_id=tep_id, trang_thai="HOP_LE"
        )


async def test_duong_dan_de_doc_authorizations(
    pool: asyncpg.Pool, monkeypatch: Any, tmp_path: pathlib.Path
) -> None:
    """Kiểm tra phân quyền đọc nội dung tệp:

    - Nhóm đọc cũ (NORMAL_READ_ROLES) đọc được mọi tệp trong clinic.
    - Nhân viên không thuộc nhóm đọc cũ + không capability -> 403.
    - Người có capability ket_qua.xac_nhan (không thuộc nhóm đọc cũ):
      * Đọc được external pending (CHO_XAC_NHAN).
      * KHÔNG đọc được tệp internal.
      * KHÔNG đọc được external khi đã HOP_LE / TU_CHOI.
      * KHÔNG đọc được tệp clinic khác.
    """
    import clinicai.services.media_service as media
    import clinicai.services.tep_ket_qua_service as tep_mod

    monkeypatch.setattr(media, "MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(tep_mod, "MEDIA_ROOT", tmp_path)
    monkeypatch.delenv("MEDIA_MARKER", raising=False)

    async with pool.acquire() as conn:
        doc = await _tao_staff(conn, CLINIC_A, "DOCTOR")
        cskh = await _tao_staff(conn, CLINIC_A, "CSKH")
        partner = await _tao_staff(conn, CLINIC_A, "PARTNER")
        # 27/09/2026: thu ngân ĐỌC được tệp để IN phiếu (QUYEN_IN_PHIEU) — ca
        # "không vai đọc, không quyền" nay dùng tài khoản tivi (DISPLAY).
        thu_ngan = await _tao_staff(conn, CLINIC_A, "CASHIER")
        plain_cashier = await _tao_staff(conn, CLINIC_A, "DISPLAY")
        cap_cashier = await _tao_staff(
            conn, CLINIC_A, "DISPLAY", caps=[Capability.KET_QUA_XAC_NHAN.value]
        )
        pid_a, aid_a, vid_a = await _tao_benh_nhan_va_visit(
            conn, CLINIC_A, doc.staff_id
        )
        oid_ext = await _tao_external_order(conn, CLINIC_A, vid_a)

        # Clinic B
        await conn.execute(
            """
            INSERT INTO clinic (id, name, code)
            VALUES ($1::uuid, 'Clinic B Test', 'CLINIC_B')
            ON CONFLICT (id) DO NOTHING
            """,
            CLINIC_B,
        )
        doc_b = await _tao_staff(conn, CLINIC_B, "DOCTOR")
        partner_b = await _tao_staff(conn, CLINIC_B, "PARTNER")
        pid_b, aid_b, vid_b = await _tao_benh_nhan_va_visit(
            conn, CLINIC_B, doc_b.staff_id
        )
        oid_ext_b = await _tao_external_order(conn, CLINIC_B, vid_b)

    svc = TepKetQuaService(pool)

    # Tạo tệp external CHO_XAC_NHAN ở clinic A
    res_ext = await svc.tai_len(
        identity=partner,
        clinic_patient_id=pid_a,
        data=PDF_DUMMY,
        ten_hien_thi="ext_pending.pdf",
        service_order_id=oid_ext,
    )
    tep_ext_id = res_ext["id"]

    # Tạo tệp internal ở clinic A
    res_int = await svc.tai_len(
        identity=doc,
        clinic_patient_id=pid_a,
        data=PDF_DUMMY,
        ten_hien_thi="internal.pdf",
    )
    tep_int_id = res_int["id"]

    # Tạo tệp external ở clinic B
    res_ext_b = await svc.tai_len(
        identity=partner_b,
        clinic_patient_id=pid_b,
        data=PDF_DUMMY,
        ten_hien_thi="ext_b.pdf",
        service_order_id=oid_ext_b,
    )
    tep_ext_b_id = res_ext_b["id"]

    # 1. Nhóm vai đọc cũ (DOCTOR, CSKH) đọc được cả external pending và internal
    p_doc, _, _, _ = await svc.duong_dan_de_doc(identity=doc, tep_id=tep_ext_id)
    assert p_doc.exists()

    p_cskh, _, _, _ = await svc.duong_dan_de_doc(identity=cskh, tep_id=tep_int_id)
    assert p_cskh.exists()

    # 1b. Thu ngân đọc được để in (27/09/2026, QUYEN_IN_PHIEU)
    p_tn, _, _, _ = await svc.duong_dan_de_doc(identity=thu_ngan, tep_id=tep_int_id)
    assert p_tn.exists()

    # 2. Nhân viên không có vai đọc cũ và không capability (plain_cashier) -> 403
    with pytest.raises(SafetyGateError):
        await svc.duong_dan_de_doc(identity=plain_cashier, tep_id=tep_ext_id)
    with pytest.raises(SafetyGateError):
        await svc.duong_dan_de_doc(identity=plain_cashier, tep_id=tep_int_id)

    # 3. Người có capability (cap_cashier):
    # - Đọc được external pending
    p_cap, _, _, _ = await svc.duong_dan_de_doc(identity=cap_cashier, tep_id=tep_ext_id)
    assert p_cap.exists()

    # - KHÔNG đọc được internal
    with pytest.raises(SafetyGateError):
        await svc.duong_dan_de_doc(identity=cap_cashier, tep_id=tep_int_id)

    # - KHÔNG đọc được tệp clinic B (cross-clinic) -> NotFoundError hoặc SafetyGateError
    with pytest.raises((NotFoundError, SafetyGateError)):
        await svc.duong_dan_de_doc(identity=cap_cashier, tep_id=tep_ext_b_id)

    # 4. Khi tệp chuyển sang HOP_LE: cap_cashier KHÔNG còn đọc được nhờ capability
    await svc.xac_nhan_tep(identity=cap_cashier, tep_id=tep_ext_id, trang_thai="HOP_LE")
    with pytest.raises(SafetyGateError):
        await svc.duong_dan_de_doc(identity=cap_cashier, tep_id=tep_ext_id)

    # Vai đọc cũ vẫn đọc được tệp HOP_LE
    p_doc_after, _, _, _ = await svc.duong_dan_de_doc(identity=doc, tep_id=tep_ext_id)
    assert p_doc_after.exists()
