"""BÁC SĨ CỦA PHIÊN, trên Postgres thật (Tuyền chốt 29/09/2026).

"ĐD và TKYK trọn quyền như bác sĩ, thao tác HỘ bác sĩ. Nhân sự được xếp lịch
cùng phòng với bác sĩ thì mọi thứ liên thông song song. Mọi chỗ hiển thị 'bác
sĩ' phải ra TÊN BÁC SĨ (không phải người bấm); người bấm chỉ ghi ở lịch sử."

Ba kẽ hở đã soát:
  * ĐD bấm Bắt đầu khám cho khách CHƯA gán bác sĩ → phiên không bác sĩ, không
    phòng; chỗ chờ không ghi bác sĩ → khách hiện ở hàng chờ MỌI phòng.
  * Thư ký phân theo BS Y, hôm nay được xếp phòng BS X → không thấy / không khám
    được khách của X ("Khách này của bác sĩ khác").
  * Check-out: hàng "Khám với bác sĩ" cột người làm "—".
"""

from __future__ import annotations

import pytest

import clinicai.events.consumers.dong_thoi_gian  # noqa: F401 — đăng ký bên nhận
from clinicai.core.exceptions import SafetyGateError
from clinicai.events.catalogue import DONG_THOI_GIAN_LUOT
from clinicai.services.checkout_service import CheckoutService
from clinicai.services.hanh_trinh_khach_service import doc_hanh_trinh_khach
from clinicai.services.thu_ky_bac_si import khach_duoc_xem
from tests.chay_nguoi_dua_tin import chay_ben_nhan
from tests.services.test_luot_kham_service_db import CLINIC, KichBan, _hanh_trinh
from tests.services.test_tro_ly_bac_si_tron_quyen_db import _phong_kham_moi, _xep

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _do_va_vao_hang(kb: KichBan) -> str:
    """Đo sinh hiệu → khối Hành trình mở phiên khám chính + chỗ chờ. Trả mã
    phiên vòng 1."""
    await kb.svc.bat_dau_do_sinh_hieu(visit_id=kb.visit_id, identity=kb.dieu_duong)
    await kb.svc.record_vitals(
        visit_id=kb.visit_id,
        raw={"systolic": 118, "diastolic": 76},
        identity=kb.dieu_duong,
    )
    await _hanh_trinh(kb.pool)
    async with kb.pool.acquire() as conn:
        phien = await conn.fetchval(
            "SELECT id::text FROM consultation WHERE visit_id = $1::uuid"
            " AND round_no = 1",
            kb.visit_id,
        )
    assert phien is not None
    return str(phien)


async def test_dieu_duong_bat_dau_khach_chua_gan_bac_si_ghi_bac_si_phong(
    kb: KichBan,
) -> None:
    """ĐD bấm Bắt đầu khám cho khách chưa gán bác sĩ, ở phòng có ĐÚNG MỘT bác
    sĩ trong ca → phiên, chỗ chờ, lượt đều ghi bác sĩ ấy; khách định vị về
    đúng phòng; người bấm chỉ ở `started_by`."""
    async with kb.pool.acquire() as conn:
        await conn.execute(
            "UPDATE visit SET attending_doctor_id = NULL WHERE visit_id = $1::uuid",
            kb.visit_id,
        )
        phong = await _phong_kham_moi(conn, kb.location_id)
        await _xep(conn, phong, kb.bac_si)
        await _xep(conn, phong, kb.dieu_duong)
    phien = await _do_va_vao_hang(kb)
    async with kb.pool.acquire() as conn:
        truoc = await conn.fetchrow(
            "SELECT c.doctor_staff_id AS c_bs, q.doctor_staff_id AS q_bs"
            "  FROM consultation c JOIN queue_entry q ON q.ref_id = c.id"
            " WHERE c.id = $1::uuid",
            phien,
        )
    assert truoc["c_bs"] is None and truoc["q_bs"] is None, "khách chưa gán BS"

    # Bác sĩ KHÁC (không lịch) mở "khách của tôi": khách chưa gán thì thấy.
    hc = await kb.svc.hang_cho(identity=kb.bac_si_2, room_id=None)
    assert any(r["visit_id"] == kb.visit_id for r in hc["hang_cho"])

    await kb.svc.start_consultation(consultation_id=phien, identity=kb.dieu_duong)

    async with kb.pool.acquire() as conn:
        sau = await conn.fetchrow(
            "SELECT c.doctor_staff_id::text AS c_bs, c.started_by::text AS boi,"
            "       q.doctor_staff_id::text AS q_bs, q.status AS q_tt,"
            "       v.attending_doctor_id::text AS v_bs,"
            "       v.current_room_id::text AS phong"
            "  FROM consultation c"
            "  JOIN queue_entry q ON q.ref_id = c.id"
            "  JOIN visit v ON v.visit_id = c.visit_id"
            " WHERE c.id = $1::uuid",
            phien,
        )
    assert sau["c_bs"] == kb.bac_si.staff_id, "phiên ghi TÊN BÁC SĨ phòng"
    assert sau["q_bs"] == kb.bac_si.staff_id, "chỗ chờ ghi bác sĩ"
    assert sau["v_bs"] == kb.bac_si.staff_id, "lượt có bác sĩ chính"
    assert sau["boi"] == kb.dieu_duong.staff_id, "người bấm ở lịch sử"
    assert sau["q_tt"] == "serving"
    assert sau["phong"] == phong, "khách định vị đúng phòng bác sĩ"

    # Đã có người nhận → không còn hiện ở hàng chờ của bác sĩ khác.
    hc = await kb.svc.hang_cho(identity=kb.bac_si_2, room_id=None)
    assert not any(r["visit_id"] == kb.visit_id for r in hc["hang_cho"])

    # Sự kiện ghi cả người bấm (actor) lẫn bác sĩ của phiên.
    async with kb.pool.acquire() as conn:
        bs_sk = await conn.fetchval(
            "SELECT payload->>'bac_si_id' FROM event_log"
            " WHERE event_type = 'consult.started' AND aggregate_id = $1"
            " ORDER BY occurred_at DESC LIMIT 1",
            kb.visit_id,
        )
    assert bs_sk == kb.bac_si.staff_id


async def test_dieu_duong_phong_nhieu_bac_si_khong_doan(kb: KichBan) -> None:
    """Phòng có HAI bác sĩ trong ca → không biết ai, không đoán tên."""
    async with kb.pool.acquire() as conn:
        await conn.execute(
            "UPDATE visit SET attending_doctor_id = NULL WHERE visit_id = $1::uuid",
            kb.visit_id,
        )
        phong = await _phong_kham_moi(conn, kb.location_id)
        await _xep(conn, phong, kb.bac_si)
        await _xep(conn, phong, kb.bac_si_2)
        await _xep(conn, phong, kb.dieu_duong)
    phien = await _do_va_vao_hang(kb)
    await kb.svc.start_consultation(consultation_id=phien, identity=kb.dieu_duong)
    async with kb.pool.acquire() as conn:
        bs = await conn.fetchval(
            "SELECT doctor_staff_id FROM consultation WHERE id = $1::uuid", phien
        )
    assert bs is None


async def test_thu_ky_phan_bs_y_xep_phong_bs_x_thay_va_kham_khach_x(
    kb: KichBan,
) -> None:
    """TKYK phân theo BS Y (bac_si_2) nhưng hôm nay xếp lịch phòng BS X
    (bac_si) → lịch phòng là HỢP với phân công: thấy + khám được khách của X."""
    async with kb.pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO thu_ky_bac_si (clinic_id, thu_ky_staff_id, bac_si_staff_id)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid)",
            CLINIC,
            kb.thu_ky.staff_id,
            kb.bac_si_2.staff_id,
        )
    phien = await _do_va_vao_hang(kb)

    # Chưa xếp lịch: khách của X là "của bác sĩ khác".
    with pytest.raises(SafetyGateError):
        await kb.svc.start_consultation(consultation_id=phien, identity=kb.thu_ky)
    duoc = await khach_duoc_xem(kb.pool, kb.thu_ky)
    async with kb.pool.acquire() as conn:
        khach = await conn.fetchval(
            "SELECT clinic_patient_id::text FROM visit WHERE visit_id = $1::uuid",
            kb.visit_id,
        )
    assert duoc is not None and khach not in duoc

    async with kb.pool.acquire() as conn:
        phong = await _phong_kham_moi(conn, kb.location_id)
        await _xep(conn, phong, kb.bac_si)
        await _xep(conn, phong, kb.thu_ky)

    duoc = await khach_duoc_xem(kb.pool, kb.thu_ky)
    assert duoc is not None and khach in duoc, "thấy khách của BS cùng phòng"
    hc = await kb.svc.hang_cho(identity=kb.thu_ky, room_id=None)
    assert any(r["visit_id"] == kb.visit_id for r in hc["hang_cho"])
    hc_phong = await kb.svc.hang_cho(identity=kb.thu_ky, room_id=phong)
    assert any(r["visit_id"] == kb.visit_id for r in hc_phong["hang_cho"])

    kq = await kb.svc.start_consultation(consultation_id=phien, identity=kb.thu_ky)
    assert kq["ok"] is True
    async with kb.pool.acquire() as conn:
        c = await conn.fetchrow(
            "SELECT doctor_staff_id::text AS bs, started_by::text AS boi"
            " FROM consultation WHERE id = $1::uuid",
            phien,
        )
    assert c["bs"] == kb.bac_si.staff_id, "phiên vẫn của BS X"
    assert c["boi"] == kb.thu_ky.staff_id


async def test_check_out_hien_ten_bac_si(kb: KichBan) -> None:
    """Hàng "Khám với bác sĩ": chưa khám → "BS X (dự kiến)"; trợ lý bấm Bắt đầu
    → tên bác sĩ, không phải người bấm; trạng thái khám + đang ở theo hành
    trình."""
    async with kb.pool.acquire() as conn:
        phong = await _phong_kham_moi(conn, kb.location_id)
        await _xep(conn, phong, kb.bac_si)
        await _xep(conn, phong, kb.dieu_duong)
        ten_phong = await conn.fetchval(
            "SELECT name FROM clinic_room WHERE id = $1::uuid", phong
        )
    phien = await _do_va_vao_hang(kb)
    ct = CheckoutService(kb.pool)

    truoc = await ct.chi_tiet(identity=kb.le_tan, visit_id=kb.visit_id)
    kham = [x for x in truoc["dich_vu"] if x["ten"] == "Khám với bác sĩ"]
    assert kham and kham[0]["nguoi_lam"] == f"BS {kb.bac_si.full_name} (dự kiến)"
    assert truoc["trang_thai_kham"] == "Chờ khám"

    await kb.svc.start_consultation(consultation_id=phien, identity=kb.dieu_duong)
    sau = await ct.chi_tiet(identity=kb.le_tan, visit_id=kb.visit_id)
    kham = [x for x in sau["dich_vu"] if x["ten"] == "Khám với bác sĩ"]
    assert kham[0]["nguoi_lam"] == kb.bac_si.full_name, "tên BS, không phải ĐD"
    assert sau["trang_thai_kham"] == "Đang khám"
    assert sau["dang_o"] and ten_phong in sau["dang_o"]

    await kb.svc.complete_consultation(
        consultation_id=phien,
        outcome="NO_SERVICES",
        requirements=None,
        identity=kb.dieu_duong,
    )
    xong = await ct.chi_tiet(identity=kb.le_tan, visit_id=kb.visit_id)
    kham = [x for x in xong["dich_vu"] if x["ten"] == "Khám với bác sĩ"]
    assert kham[0]["nguoi_lam"] == kb.bac_si.full_name
    assert kham[0]["status"] == "COMPLETED"
    if xong["visit_status"] in ("OPEN", "IN_PROGRESS"):
        assert xong["trang_thai_kham"] == "Đã khám xong"


async def test_hanh_trinh_gio_that_do_lai_va_bac_si_phong(kb: KichBan) -> None:
    """Hành trình đọc DB thật: sinh hiệu xong = lần đo ĐẦU, đo lại trả riêng
    kèm người đo; ĐD bấm khám → bước Khám ghi tên BÁC SĨ + phòng của bác sĩ."""
    async with kb.pool.acquire() as conn:
        await conn.execute(
            "UPDATE visit SET attending_doctor_id = NULL WHERE visit_id = $1::uuid",
            kb.visit_id,
        )
        phong = await _phong_kham_moi(conn, kb.location_id)
        await _xep(conn, phong, kb.bac_si)
        await _xep(conn, phong, kb.dieu_duong)
        ten_phong = await conn.fetchval(
            "SELECT name FROM clinic_room WHERE id = $1::uuid", phong
        )
    phien = await _do_va_vao_hang(kb)
    # ĐO LẠI sau lần đầu.
    await kb.svc.record_vitals(
        visit_id=kb.visit_id,
        raw={"systolic": 121, "diastolic": 79},
        identity=kb.dieu_duong,
    )
    await kb.svc.start_consultation(consultation_id=phien, identity=kb.dieu_duong)
    await chay_ben_nhan(kb.pool, DONG_THOI_GIAN_LUOT)
    async with kb.pool.acquire() as conn:
        ht = (
            await doc_hanh_trinh_khach(
                conn, clinic_id=CLINIC, visit_ids=[kb.visit_id], kem_ai=True
            )
        )[kb.visit_id]
        do = await conn.fetch(
            "SELECT occurred_at FROM luot_dong_thoi_gian WHERE visit_id = $1::uuid"
            " AND event_type = 'vitals.recorded' ORDER BY occurred_at",
            kb.visit_id,
        )
    assert len(do) >= 2, "hai lần đo vào dòng thời gian"
    buoc = {b["ma"]: b for b in ht["buoc"]}
    sh = buoc["SINH_HIEU"]
    assert sh["xong"] == do[0]["occurred_at"].isoformat(), "xong = lần đo ĐẦU"
    assert len(sh["do_lai"]) == len(do) - 1
    assert [x["ai"] for x in sh["lan_do"]] == [kb.dieu_duong.full_name] * len(do)
    assert ht["gon"]["do_lai"] == sh["do_lai"]
    kham = buoc["KHAM"]
    assert kham["ai"] == kb.bac_si.full_name, "tên BÁC SĨ, không phải ĐD"
    assert kham["noi"] == ten_phong and not kham["du_kien"]
    assert buoc["CHECK_OUT"]["du_kien"] and buoc["CHECK_OUT"]["xong"] is None
