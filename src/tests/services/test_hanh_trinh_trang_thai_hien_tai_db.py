"""C18 (02/10/2026): hành trình theo TRẠNG THÁI HIỆN TẠI + dịch vụ khám hiện trên
hành trình + sửa tick dịch vụ khám tự bỏ.

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55600/postgres \\
        .venv/bin/pytest src/tests/services/test_hanh_trinh_trang_thai_hien_tai_db.py

Mối lo của Tuyền: mở sửa / hoàn tác chỉ định cho điều dưỡng, thư ký, bác sĩ làm
Hành trình khách ghi "xong ở bác sĩ chính" trong khi dịch vụ khám không thấy đâu.
Dữ liệu phải nhất quán vì AI sẽ đọc về sau. Bất biến:

  I2  mốc XONG của hành trình = trạng thái HIỆN TẠI (hoàn tác phải rút mốc)
  I3  không có vòng đọc mở mà rỗng yêu cầu
  I4  mọi tự huỷ (nháp, tick dịch vụ khám) có sự kiện domain_event
  P5  lượt tạo ngoài check-in vẫn mang loại khám của lịch hẹn
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

import asyncpg
import pytest

from clinicai.events.catalogue import DONG_THOI_GIAN_LUOT
from clinicai.phieu_kham.hanh_trinh import doc_hanh_trinh
from clinicai.services.chi_dinh_service import ChiDinhService
from clinicai.services.clinical_record_service import ClinicalRecordService
from clinicai.services.hanh_trinh_khach_service import doc_hanh_trinh_khach
from clinicai.services.hoan_tac_service import HoanTacService
from clinicai.services.phi_kham_service import PhiKhamService
from clinicai.services.ultrasound_service import UltrasoundService
from tests.chay_nguoi_dua_tin import chay_ben_nhan
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_hoan_tac_moi_thao_tac_db import (
    _kham_xong,
    _luot,
    _phien,
    _vao_kham,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    _benh_nhan,
    _check_in,
    _dung,
    _kham_va_chi_dinh,
    _khoa,
    _su_kien,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _buoc_kham(pool: asyncpg.Pool, visit: str) -> dict:  # type: ignore[type-arg]  # noqa: F811
    """Bước KHÁM trên Hành trình khách (dạng đầy đủ) sau khi dòng thời gian chạy."""
    await chay_ben_nhan(pool, DONG_THOI_GIAN_LUOT)
    async with pool.acquire() as conn:
        kq = await doc_hanh_trinh_khach(
            conn, clinic_id=CLINIC, visit_ids=[visit], kem_dich_vu_kham=True
        )
    return next(b for b in kq[visit]["buoc"] if b["ma"] == "KHAM")


async def _dich_vu_kham_con(
    pool: asyncpg.Pool,  # noqa: F811
    loai_kham: str,
    ten: str,
    gia: int,
) -> str:
    ma = f"T{uuid.uuid4().hex[:7]}"
    sp = await pool.fetchval(
        'INSERT INTO service_price (clinic_id, service_code, name, "group",'
        " unit_price, ma_kiotviet) VALUES ($1::uuid, $2, $3, 'dich_vu', $4, $2)"
        " RETURNING id::text",
        CLINIC,
        ma,
        ten,
        gia,
    )
    await pool.execute(
        "INSERT INTO loai_kham_phi (clinic_id, service_type_id, service_price_id)"
        " VALUES ($1::uuid, $2::uuid, $3::uuid)",
        CLINIC,
        loai_kham,
        sp,
    )
    return str(sp)


# ── I2 — hoàn tác Khám xong phải rút mốc XONG của hành trình ────────────────


async def test_hoan_tac_kham_xong_hanh_trinh_ve_dang_kham_lai(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    con = await _vao_kham(pool, ca, visit)
    await _kham_xong(pool, ca, con)

    b = await _buoc_kham(pool, visit)
    assert b["trang_thai"] == "xong" and b["kham_lai"] is False

    await HoanTacService(pool).mo_lai_kham(consultation_id=con, identity=ca.bac_si)
    b = await _buoc_kham(pool, visit)
    # Hành trình KHÔNG còn nói "xong ở bác sĩ chính".
    assert b["trang_thai"] == "dang"
    assert b["kham_lai"] is True and b["xong"] is None
    assert b["mo_lai_luc"] is not None
    # Dải mốc ở đầu phiếu khám (cùng sổ sự kiện) cũng rút mốc.
    async with pool.acquire() as conn:
        ht = await doc_hanh_trinh(conn, clinic_id=CLINIC, visit_id=visit)
    assert ht is not None
    moc = next(m for m in ht["moc"] if m["ma"] == "KHAM")
    assert moc["trang_thai"] == "dang" and moc["ket"] is None

    # Khám xong LẠI → xong lần nữa, hết "khám lại".
    await _kham_xong(pool, ca, con)
    b = await _buoc_kham(pool, visit)
    assert b["trang_thai"] == "xong" and b["kham_lai"] is False


async def test_hanh_trinh_theo_phien_ngay_ca_khi_dong_thoi_gian_chua_kip(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Dòng thời gian nhận sự kiện trễ vài giây: trạng thái PHIÊN vẫn quyết."""
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    con = await _vao_kham(pool, ca, visit)
    await _kham_xong(pool, ca, con)
    await chay_ben_nhan(pool, DONG_THOI_GIAN_LUOT)  # đã ghi "Khám xong"
    await HoanTacService(pool).mo_lai_kham(consultation_id=con, identity=ca.bac_si)
    # KHÔNG chạy bên nhận: dòng "mở lại" chưa vào dòng thời gian.
    async with pool.acquire() as conn:
        kq = await doc_hanh_trinh_khach(conn, clinic_id=CLINIC, visit_ids=[visit])
    b = next(x for x in kq[visit]["buoc"] if x["ma"] == "KHAM")
    assert b["trang_thai"] == "dang" and b["kham_lai"] is True


# ── Dịch vụ khám hiện trên hành trình + tick không tự bỏ ────────────────────


async def test_tick_dich_vu_kham_phat_su_kien_va_hien_tren_hanh_trinh(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    a = await _dich_vu_kham_con(pool, ca.loai_kham, "Tư vấn phụ khoa (thử)", 300000)
    svc = PhiKhamService(pool)

    # Chưa tick: dòng "Loại khám … · 0đ (chưa chọn dịch vụ khám con)" — 0đ không lỗi.
    b = await _buoc_kham(pool, visit)
    assert b["dich_vu_kham"].startswith("Loại khám Khám nhóm hai")
    assert "(chưa chọn dịch vụ khám con)" in b["dich_vu_kham"]

    await svc.chon(visit_id=visit, them_vao=[a], identity=ca.bac_si)
    b = await _buoc_kham(pool, visit)
    assert b["dich_vu_kham"] == "Dịch vụ khám: Tư vấn phụ khoa (thử) · 300.000đ"
    [ev] = await _su_kien(pool, "visit.exam_service_changed", visit)
    assert ev["ai"] == ca.bac_si.staff_id
    pl = json.loads(ev["payload"])
    assert [x["ten"] for x in pl["them"]] == ["Tư vấn phụ khoa (thử)"]
    assert pl["them"][0]["gia"] == 300000 and pl["bo"] == []
    # Dòng thời gian của lượt có câu tiếng Việt (ai / lúc nào nằm ở cột riêng).
    nhan = await pool.fetchval(
        "SELECT nhan FROM luot_dong_thoi_gian WHERE visit_id = $1::uuid"
        " AND event_type = 'visit.exam_service_changed'",
        visit,
    )
    assert nhan == "Chọn dịch vụ khám: Tư vấn phụ khoa (thử) · 300.000đ"


async def test_tick_hai_lan_cung_dich_vu_khong_bo_tick_va_khong_ghi_su_kien_thua(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Gốc rễ lỗi tick tự bỏ (prod 30/09): gửi lại cùng một tick không được bỏ."""
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    a = await _dich_vu_kham_con(pool, ca.loai_kham, "Khám A (thử)", 100000)
    svc = PhiKhamService(pool)
    kq1 = await svc.chon(visit_id=visit, them_vao=[a], identity=ca.bac_si)
    kq2 = await svc.chon(visit_id=visit, them_vao=[a], identity=ca.bac_si)
    assert kq1["da_chon"] == [a] and kq2["da_chon"] == [a]
    assert len(await _su_kien(pool, "visit.exam_service_changed", visit)) == 1


async def test_tab_cu_gui_bo_tick_dich_vu_khac_khong_ghi_de_tick_nguoi_khac(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Hai người cùng mở một lượt: gửi THEO TỪNG DỊCH VỤ nên không ghi đè nhau —
    dạng gửi cả tập cũ (ids) mới làm mất tick của người kia."""
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    a = await _dich_vu_kham_con(pool, ca.loai_kham, "Khám A (thử)", 100000)
    b = await _dich_vu_kham_con(pool, ca.loai_kham, "Khám B (thử)", 200000)
    svc = PhiKhamService(pool)
    await svc.chon(visit_id=visit, them_vao=[a], identity=ca.bac_si)  # người 1
    # Người 2 (thu ngân) mở lượt TRƯỚC khi người 1 tick (cầm tập rỗng) rồi tick B.
    kq = await svc.chon(visit_id=visit, them_vao=[b], identity=ca.thu_ngan)
    assert set(kq["da_chon"]) == {a, b}
    # Người 2 bỏ B: A của người 1 còn nguyên.
    kq = await svc.chon(visit_id=visit, bo_di=[b], identity=ca.thu_ngan)
    assert kq["da_chon"] == [a]
    # Bỏ lần nữa (tab cũ gửi lại): không làm gì, không sự kiện thừa.
    n = len(await _su_kien(pool, "visit.exam_service_changed", visit))
    kq = await svc.chon(visit_id=visit, bo_di=[b], identity=ca.thu_ngan)
    assert kq["da_chon"] == [a]
    assert len(await _su_kien(pool, "visit.exam_service_changed", visit)) == n
    # Dạng cũ (đặt cả tập) vẫn chạy cho khách gọi cũ.
    kq = await svc.chon(visit_id=visit, ids=[a, b], identity=ca.bac_si)
    assert set(kq["da_chon"]) == {a, b}


async def test_bo_tick_ghi_su_kien_bo_va_hanh_trinh_ve_dang_0d(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    a = await _dich_vu_kham_con(pool, ca.loai_kham, "Khám A (thử)", 100000)
    svc = PhiKhamService(pool)
    await svc.chon(visit_id=visit, them_vao=[a], identity=ca.bac_si)
    await svc.chon(visit_id=visit, bo_di=[a], identity=ca.thu_ngan)
    evs = await _su_kien(pool, "visit.exam_service_changed", visit)
    assert len(evs) == 2
    pl = json.loads(evs[1]["payload"])
    assert [x["ten"] for x in pl["bo"]] == ["Khám A (thử)"] and pl["them"] == []
    assert evs[1]["ai"] == ca.thu_ngan.staff_id  # ai bỏ tick nằm trong sổ
    b = await _buoc_kham(pool, visit)
    assert "(chưa chọn dịch vụ khám con)" in b["dich_vu_kham"]


# ── I4 — nháp tự huỷ khi "Khám xong — không cần dịch vụ" có sự kiện ──────────


async def test_kham_xong_khong_can_dich_vu_huy_nhap_co_su_kien_tung_cai(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    con = await _vao_kham(pool, ca, visit)
    nhap = []
    for i in range(2):
        nhap.append(
            str(
                await pool.fetchval(
                    "INSERT INTO service_order (clinic_id, visit_id, consultation_id,"
                    " service_code, service_name, node_code, exec_status,"
                    " recorded_by) VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5,"
                    " 'DICHVU-SIEUAM', 'draft', $6::uuid) RETURNING id::text",
                    CLINIC,
                    visit,
                    con,
                    ca.ma_dv,
                    f"Nháp của điều dưỡng {i}",
                    ca.dd.staff_id,
                )
            )
        )
    await _kham_xong(pool, ca, con)  # NO_SERVICES — nháp tự huỷ
    for oid in nhap:
        assert (
            await pool.fetchval(
                "SELECT exec_status FROM service_order WHERE id = $1::uuid", oid
            )
            == "cancelled"
        )
        [ev] = await _su_kien(pool, "service_order.cancelled", oid)
        assert ev["ai"] == ca.bac_si.staff_id  # ai bấm Khám xong
        pl = json.loads(ev["payload"])
        assert pl["ly_do"] and "Khám xong" in pl["ly_do"]  # vì sao
        assert pl["service_name"].startswith("Nháp của điều dưỡng")
    # Lên dòng thời gian của lượt để người xem Hành trình thấy.
    await chay_ben_nhan(pool, DONG_THOI_GIAN_LUOT)
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM luot_dong_thoi_gian WHERE visit_id = $1::uuid"
            " AND event_type = 'service_order.cancelled'",
            visit,
        )
        == 2
    )


# ── I3 — huỷ chỉ định cuối sau Khám xong không để vòng đọc rỗng treo ─────────


async def test_huy_chi_dinh_cuoi_sau_kham_xong_dong_vong_rong_va_khep_luot(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    con, order = await _kham_va_chi_dinh(pool, ca, visit)
    await _kham_xong(pool, ca, con)
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM review_round WHERE visit_id = $1::uuid"
            " AND status <> 'closed'",
            visit,
        )
        == 1
    )

    await HoanTacService(pool).huy_chi_dinh(order_id=order, identity=ca.bac_si)

    # Không còn vòng đọc MỞ mà rỗng yêu cầu.
    treo = await pool.fetchval(
        "SELECT count(*) FROM review_round r WHERE r.visit_id = $1::uuid"
        " AND r.status <> 'closed' AND NOT EXISTS ("
        "   SELECT 1 FROM round_requirement q WHERE q.round_id = r.id)",
        visit,
    )
    assert treo == 0
    # Phiên đọc / chỗ chờ đọc của vòng ấy cũng gỡ — khách không chờ ai gọi.
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM queue_entry WHERE visit_id = $1::uuid"
            " AND reason = 'REVIEW' AND status IN ('waiting','called','blocked',"
            " 'serving')",
            visit,
        )
        == 0
    )
    # Lượt nhất quán: đã Khám xong và không còn việc → khép như thường.
    assert (await _phien(pool, visit))["status"] == "completed"
    assert (await _luot(pool, visit))["exam_completed_at"] is not None


async def test_huy_chi_dinh_cuoi_nhung_con_chi_dinh_khac_thi_vong_van_mo(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Chỉ đóng vòng RỖNG: còn một chỉ định thì vòng đọc giữ nguyên."""
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    con, order = await _kham_va_chi_dinh(pool, ca, visit)
    moi = await ChiDinhService(pool).dat_chi_dinh(
        consultation_id=con,
        service_codes=[ca.ma_dv],
        identity=ca.bac_si,
        idempotency_key=_khoa(),
    )
    giu = str(moi["order_ids"][0])
    await _kham_xong(pool, ca, con)
    await HoanTacService(pool).huy_chi_dinh(order_id=order, identity=ca.bac_si)
    vong = await pool.fetch(
        "SELECT r.status, (SELECT count(*) FROM round_requirement q"
        "   WHERE q.round_id = r.id) AS yc FROM review_round r"
        " WHERE r.visit_id = $1::uuid",
        visit,
    )
    assert [(v["status"] != "closed", v["yc"]) for v in vong] == [(True, 1)]
    assert giu


# ── P5 — lượt tạo ngoài check-in mang loại khám của lịch hẹn ─────────────────


async def test_luot_tao_tu_ghi_benh_an_mang_loai_kham_cua_lich_hen(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    bd = datetime.now(UTC) + timedelta(minutes=30)
    appt = await pool.fetchval(
        "INSERT INTO appointment (clinic_id, clinic_patient_id, location_id,"
        " service_type_id, slot_start, slot_end, doctor_id, status)"
        " VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5, $6, $7::uuid,"
        " 'CONFIRMED') RETURNING id::text",
        CLINIC,
        pid,
        ca.loc,
        ca.loai_kham,
        bd,
        bd + timedelta(minutes=15),
        ca.bac_si.staff_id,
    )
    async with pool.acquire() as conn, conn.transaction():
        vid = await ClinicalRecordService(pool)._writable_visit(
            conn,
            appointment_id=appt,
            clinic_patient_id=pid,
            appointment_doctor_id=ca.bac_si.staff_id,
            identity=ca.bac_si,
            vitals_only=False,
        )
        loai = await conn.fetchval(
            "SELECT service_type_id::text FROM visit WHERE visit_id = $1::uuid", vid
        )
    assert loai == ca.loai_kham


async def test_luot_tao_tu_sieu_am_mang_loai_kham_cua_lich_hen(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    pid = await _benh_nhan(pool, ca)
    bd = datetime.now(UTC) + timedelta(minutes=30)
    appt = await pool.fetchval(
        "INSERT INTO appointment (clinic_id, clinic_patient_id, location_id,"
        " service_type_id, slot_start, slot_end, doctor_id, status)"
        " VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5, $6, $7::uuid,"
        " 'CONFIRMED') RETURNING id::text",
        CLINIC,
        pid,
        ca.loc,
        ca.loai_kham,
        bd,
        bd + timedelta(minutes=15),
        ca.bac_si.staff_id,
    )
    await UltrasoundService(pool).save_measurements(
        appointment_id=appt,
        clinic_patient_id=pid,
        measurements={"bpd": 30},
        is_abnormal=False,
        status=None,
        identity=ca.bac_si,
    )
    loai = await pool.fetchval(
        "SELECT service_type_id::text FROM visit WHERE appointment_id = $1::uuid",
        appt,
    )
    assert loai == ca.loai_kham
