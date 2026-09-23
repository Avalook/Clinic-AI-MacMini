#!/usr/bin/env python3
"""KHÁCH GIẢ ĐI HẾT LUỒNG CHUẨN — mỗi bước: event nào phát ra, node nào nhận.

Tuyền 23/09/2026: *"mỗi khâu cứ gen khách giả định đi để biết event khách đó
phát ra là gì, các node khác có bắt được không"*. Luồng chuẩn 11 bước:
memory `luong-chuan-tuyen-2309.md`.

Mỗi bước in ba thứ:
  1. SỰ KIỆN MỚI (sổ `domain_event`, hệ lego mới) — và từng BÊN NHẬN
     (`event_delivery`): đã nhận/xử lý chưa. Script tự chạy người đưa tin một
     vòng, nên "chờ" sau đó nghĩa là bên nhận ấy thật sự không làm được.
  2. SỔ CŨ (`event_log`) — bước nào CHỈ có ở đây là bước CHƯA thành lego:
     nó ghi nhật ký nhưng không node nào nghe được.
  3. CÁC NODE ĐANG THẤY KHÁCH THẾ NÀO: tiếp đón (số booking / số quầy), đo
     sinh hiệu, hàng bác sĩ chính, hàng phòng dịch vụ, thu ngân, việc CSKH.

KHÔNG CẦN DỰNG LẠI DATABASE: dùng database đang có (dựng một lần), mỗi lần chạy
tạo một khách mới mang dấu `[khach-gia]`. Gọi đúng các LỆNH mà API gọi (router
mỏng), với tài khoản giả mang nhóm quyền mẫu của từng vai — không cần mật khẩu.

CHỈ CHẠY TRÊN MÁY LOCAL: từ chối mọi DATABASE_URL không phải 127.0.0.1/localhost.

    DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:55500/postgres \\
        PYTHONPATH=src poetry run python scripts/tests/khach-gia-luong-chuan.py

    # Chỉ một vài bước (vd khách thủ thuật bỏ qua sinh hiệu):
    ... khach-gia-luong-chuan.py --bo-sinh-hieu
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import tempfile
import traceback
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

# Tệp kết quả ghi ra đĩa: để trong thư mục tạm, không đụng kho thật.
os.environ.setdefault("MEDIA_ROOT", tempfile.mkdtemp(prefix="khach-gia-media-"))
os.environ.setdefault("MEDIA_MIN_FREE_BYTES", "0")

import asyncpg  # noqa: E402

from clinicai.api.identity import ClinicRole, StaffIdentity  # noqa: E402
from clinicai.events import worker as nguoi_dua_tin  # noqa: E402
from clinicai.events.catalogue import DONG_THOI_GIAN_LUOT  # noqa: E402
from clinicai.events.consumers import dong_thoi_gian, trach_nhiem  # noqa: E402,F401
from clinicai.services.booking_service import BookingService  # noqa: E402
from clinicai.services.chi_dinh_service import ChiDinhService  # noqa: E402
from clinicai.services.luot_kham_service import LuotKhamService  # noqa: E402
from clinicai.services.payment_service import PaymentService  # noqa: E402
from clinicai.services.service_execution_service import (  # noqa: E402
    ServiceExecutionService,
)
from clinicai.services.service_routing_service import (  # noqa: E402
    ServiceRoutingService,
)
from clinicai.services.service_selection_service import (  # noqa: E402
    ServiceSelectionService,
)
from clinicai.services.tep_ket_qua_service import TepKetQuaService  # noqa: E402

CLINIC = os.environ.get("CLINIC_ID", "a0000000-0000-4000-8000-000000000001")
BEN_NHAN = [DONG_THOI_GIAN_LUOT, trach_nhiem.TRACH_NHIEM]


def _khoa() -> str:
    return f"khach-gia-{uuid.uuid4().hex}"


class Khach:
    """Mọi mã của một khách giả — điền dần theo từng bước."""

    patient: str = ""
    appointment: str = ""
    visit: str = ""
    consultation: str = ""
    orders: list[str]

    def __init__(self) -> None:
        self.orders = []

    def ma_goc(self) -> list[str]:
        return [x for x in (self.patient, self.appointment, self.visit) if x] + list(
            self.orders
        )


# ── Người giả theo vai (nhóm quyền mẫu) ─────────────────────────────────────


async def _nguoi(conn: asyncpg.Connection, loc: str, vai: str) -> StaffIdentity:
    ten = f"[khach-gia] {vai} {uuid.uuid4().hex[:4]}"
    sid = await conn.fetchval(
        "INSERT INTO staff (full_name, primary_department, primary_location_id,"
        " is_active) VALUES ($1, $2, $3::uuid, true) RETURNING id::text",
        ten,
        vai,
        loc,
    )
    await conn.execute(
        "INSERT INTO clinic_membership (clinic_id, staff_id, role, is_active)"
        " VALUES ($1::uuid, $2::uuid, $3, true) ON CONFLICT DO NOTHING",
        CLINIC,
        sid,
        vai,
    )
    await conn.execute(
        "SELECT public.cap_quyen_theo_preset($1::uuid, $2::uuid, $3, '{}', $4)",
        CLINIC,
        sid,
        vai,
        "khách giả luồng chuẩn",
    )
    return StaffIdentity(
        staff_id=sid,
        auth_user_id=str(uuid.uuid4()),
        full_name=ten,
        department=vai,
        role=ClinicRole(vai),
        clinic_id=CLINIC,
        location_id=loc,
        location_name="Cơ sở",
    )


# ── Chụp sổ trước/sau mỗi bước ───────────────────────────────────────────────


async def _moc(pool: asyncpg.Pool) -> tuple[int, datetime]:
    seq = await pool.fetchval("SELECT coalesce(max(seq), 0) FROM domain_event")
    luc = await pool.fetchval("SELECT clock_timestamp()")
    return int(seq), luc


async def _chay_nguoi_dua_tin(pool: asyncpg.Pool) -> None:
    for ben in BEN_NHAN:
        while await nguoi_dua_tin.lam_mot_dong(pool, ben, ten_worker="khach-gia"):
            pass


async def _bao_cao_su_kien(
    pool: asyncpg.Pool, k: Khach, truoc: tuple[int, datetime]
) -> list[str]:
    seq, luc = truoc
    ma = k.ma_goc()
    dong: list[str] = []
    moi = await pool.fetch(
        """
        SELECT e.event_id, e.event_type, e.source_module
          FROM domain_event e
         WHERE e.clinic_id = $1::uuid AND e.seq > $2
           AND (e.aggregate_id::text = ANY($3::text[])
                OR e.correlation_id::text = ANY($3::text[]))
         ORDER BY e.seq
        """,
        CLINIC,
        seq,
        ma,
    )
    if not moi:
        dong.append("  • Sự kiện MỚI (lego): — KHÔNG CÓ —")
    for e in moi:
        nhan = await pool.fetch(
            "SELECT consumer, status, last_error FROM event_delivery"
            " WHERE event_id = $1 ORDER BY consumer",
            e["event_id"],
        )
        ds = (
            ", ".join(
                f"{r['consumer']}="
                + ("ĐÃ NHẬN" if r["status"].lower() == "done" else r["status"])
                + (f" ({r['last_error'][:60]})" if r["last_error"] else "")
                for r in nhan
            )
            or "không node nào đăng ký nghe"
        )
        nguon = f"[{e['source_module']}]"
        dong.append(f"  • Sự kiện MỚI: {e['event_type']}  {nguon} → {ds}")
    cu = await pool.fetch(
        """
        SELECT event_type FROM event_log
         WHERE clinic_id = $1::uuid AND recorded_at >= $2
           AND (aggregate_id::text = ANY($3::text[])
                OR correlation_id::text = ANY($3::text[]))
         ORDER BY recorded_at
        """,
        CLINIC,
        luc,
        ma,
    )
    if cu:
        dong.append(
            "  • Sổ CŨ (chỉ nhật ký, không ai nghe): "
            + ", ".join(dict.fromkeys(r["event_type"] for r in cu))
        )
    return dong


async def _node_thay_gi(pool: asyncpg.Pool, k: Khach) -> list[str]:
    if not k.appointment:
        return []
    a = await pool.fetchrow(
        "SELECT status, so_booking, so_tiep_don FROM appointment WHERE id = $1::uuid",
        k.appointment,
    )
    dong = [
        f"  ◦ Tiếp đón: lịch {a['status']} · Đặt #{a['so_booking']}"
        + (f" · Quầy {a['so_tiep_don']}" if a["so_tiep_don"] else "")
    ]
    if k.visit:
        f = await pool.fetchrow(
            "SELECT vitals_status, route_decision FROM encounter_flow"
            " WHERE visit_id = $1::uuid",
            k.visit,
        )
        if f:
            dong.append(
                f"  ◦ Đo sinh hiệu: {f['vitals_status']}"
                f" · đường đi: {f['route_decision']}"
            )
        hang = await pool.fetch(
            """
            SELECT q.lane, q.status, r.name AS phong
              FROM queue_entry q LEFT JOIN clinic_room r ON r.id = q.room_id
             WHERE q.visit_id = $1::uuid ORDER BY q.created_at
            """,
            k.visit,
        )
        for q in hang:
            noi = "Bác sĩ chính" if q["lane"] == "DOCTOR" else f"Phòng {q['phong']}"
            dong.append(f"  ◦ Hàng chờ {noi}: {q['status']}")
        tien = await pool.fetch(
            "SELECT kind, status FROM payment_cycle WHERE visit_id = $1::uuid",
            k.visit,
        )
        for t in tien:
            dong.append(f"  ◦ Thu ngân: {t['kind']} {t['status']}")
    viec = await pool.fetch(
        "SELECT trang_thai FROM v_viec_cskh WHERE clinic_patient_id = $1::uuid",
        k.patient,
    )
    if viec:
        dong.append("  ◦ Việc CSKH: " + ", ".join(r["trang_thai"] for r in viec))
    return dong


# ── Chạy ─────────────────────────────────────────────────────────────────────


async def main(bo_sinh_hieu: bool) -> int:
    url = os.environ.get("DATABASE_URL") or ""
    host = urlsplit(url.replace("postgresql+asyncpg", "postgresql")).hostname
    if host not in {"127.0.0.1", "localhost"}:
        print("TỪ CHỐI: chỉ chạy trên database local (127.0.0.1 / localhost).")
        return 2
    pool = await asyncpg.create_pool(
        url.replace("postgresql+asyncpg://", "postgresql://"), min_size=1, max_size=4
    )
    k = Khach()
    loi = 0
    try:
        async with pool.acquire() as conn:
            loc = await conn.fetchval(
                "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid"
                " AND is_active ORDER BY created_at, id LIMIT 1",
                CLINIC,
            )
            cskh = await _nguoi(conn, loc, "CSKH")
            le_tan = await _nguoi(conn, loc, "RECEPTION")
            dd = await _nguoi(conn, loc, "NURSE_ULTRASOUND")
            bs = await _nguoi(conn, loc, "DOCTOR")
            dv_kham = await conn.fetchval(
                "SELECT id::text FROM service_type WHERE is_active"
                " ORDER BY code LIMIT 1"
            )
            ma_sa = await conn.fetchval(
                "SELECT service_code FROM service_price WHERE clinic_id = $1::uuid"
                " AND active AND node_code = 'DICHVU-SIEUAM'"
                " ORDER BY service_code LIMIT 1",
                CLINIC,
            )
            k.patient = await conn.fetchval(
                "INSERT INTO patient (clinic_id, patient_code, full_name, location_id)"
                " VALUES ($1::uuid, $2, $3, $4::uuid)"
                " RETURNING clinic_patient_id::text",
                CLINIC,
                f"KG-{uuid.uuid4().hex[:8]}",
                "[khach-gia] Nguyễn Thị Giả",
                loc,
            )

        async def dat_lich() -> None:
            bd = datetime.now(UTC) + timedelta(minutes=20)
            kq = await BookingService(pool).create(
                clinic_patient_id=k.patient,
                service_type_id=dv_kham,
                location_id=loc,
                slot_start=bd,
                slot_end=bd + timedelta(minutes=15),
                identity=cskh,
                doctor_id=bs.staff_id,
                notes="[khach-gia]",
            )
            k.appointment = kq["appointment_id"]

        async def check_in() -> None:
            await BookingService(pool).apply_action(
                appointment_id=k.appointment, action="checkin", identity=le_tan
            )
            k.visit = await pool.fetchval(
                "SELECT visit_id::text FROM visit WHERE appointment_id = $1::uuid",
                k.appointment,
            )

        async def do_sinh_hieu() -> None:
            svc = LuotKhamService(pool)
            await svc.bat_dau_do_sinh_hieu(visit_id=k.visit, identity=dd)
            await svc.record_vitals(
                visit_id=k.visit,
                raw={"systolic": 118, "diastolic": 76, "pulse": 80},
                identity=dd,
            )

        async def bat_dau_kham() -> None:
            k.consultation = await pool.fetchval(
                "SELECT id::text FROM consultation WHERE visit_id = $1::uuid"
                " ORDER BY round_no LIMIT 1",
                k.visit,
            )
            await LuotKhamService(pool).start_consultation(
                consultation_id=k.consultation, identity=bs
            )

        async def chi_dinh() -> None:
            kq = await ChiDinhService(pool).dat_chi_dinh(
                consultation_id=k.consultation,
                service_codes=[ma_sa],
                identity=bs,
                idempotency_key=_khoa(),
            )
            k.orders = [str(x) for x in kq.get("ids", kq.get("order_ids", []))] or [
                r["id"]
                for r in await pool.fetch(
                    "SELECT id::text FROM service_order WHERE visit_id = $1::uuid",
                    k.visit,
                )
            ]

        async def chon_va_tra_tien() -> None:
            rev = await pool.fetchval(
                "SELECT coalesce((SELECT revision FROM service_selection_state"
                " WHERE visit_id = $1::uuid), 0)",
                k.visit,
            )
            await ServiceSelectionService(pool).confirm(
                visit_id=k.visit,
                order_ids_seen=k.orders,
                selected_order_ids=k.orders,
                expected_selection_revision=int(rev),
                identity=le_tan,
                idempotency_key=_khoa(),
            )
            await PaymentService(pool).record_payment(
                visit_id=k.visit,
                kind="dich_vu",
                amount=None,
                clinic_patient_id=k.patient,
                identity=le_tan,
                idempotency_key=_khoa(),
            )

        async def xep_phong() -> None:
            # Luồng chuẩn: trả tiền xong, phòng còn ổn thì đi; đầy thì lễ tân
            # điều phòng vắng hơn. Đã có phòng (tự xếp) thì bước này bỏ qua.
            o = await pool.fetchrow(
                "SELECT room_id, routing_revision FROM service_order"
                " WHERE id = $1::uuid",
                k.orders[0],
            )
            if o["room_id"] is not None:
                print("  (đã có phòng — không cần xếp tay)")
                return
            g = await ServiceRoutingService(pool).recommend(
                order_id=k.orders[0], identity=le_tan
            )
            if not g["candidates"]:
                raise RuntimeError("không phòng nào làm được dịch vụ này")
            await ServiceRoutingService(pool).assign(
                order_id=k.orders[0],
                room_id=g["candidates"][0]["room_id"],
                expected_routing_revision=int(o["routing_revision"] or 0),
                reason_code="INITIAL_ASSIGNMENT",
                recommendation_ref=g["recommendation_ref"],
                identity=le_tan,
                idempotency_key=_khoa(),
            )

        async def phong_lam() -> None:
            o = await pool.fetchrow(
                "SELECT execution_revision, routing_revision FROM service_order"
                " WHERE id = $1::uuid",
                k.orders[0],
            )
            svc = ServiceExecutionService(pool)
            mo = await svc.bat_dau(
                order_id=k.orders[0],
                expected_execution_revision=int(o["execution_revision"] or 0),
                expected_routing_revision=int(o["routing_revision"] or 0),
                identity=dd,
                idempotency_key=_khoa(),
            )
            await svc.xong(
                order_id=k.orders[0],
                attempt_id=mo["attempt_id"],
                expected_execution_revision=mo["execution_revision"],
                identity=dd,
                idempotency_key=_khoa(),
            )

        async def ket_qua_ve() -> None:
            await TepKetQuaService(pool).tai_len(
                identity=dd,
                clinic_patient_id=k.patient,
                data=b"%PDF-1.4\n%%EOF\n",
                ten_hien_thi="[khach-gia] ket-qua.pdf",
                service_order_id=k.orders[0],
            )

        async def kham_xong() -> None:
            await LuotKhamService(pool).kham_xong(
                consultation_id=k.consultation, identity=bs
            )

        buoc: list[tuple[str, Callable[[], Awaitable[None]]]] = [
            ("1. CSKH đặt lịch", dat_lich),
            ("4. Lễ tân check-in", check_in),
        ]
        if not bo_sinh_hieu:
            buoc.append(("5. Điều dưỡng bắt đầu đo + lưu sinh hiệu", do_sinh_hieu))
        buoc += [
            ("6. Bác sĩ chính bấm Bắt đầu khám", bat_dau_kham),
            ("7a. Bác sĩ chỉ định siêu âm", chi_dinh),
            ("7b. Lễ tân chốt dịch vụ khách chọn + thu tiền", chon_va_tra_tien),
            ("7c. Xếp/đổi phòng (lễ tân)", xep_phong),
            ("8. Phòng siêu âm Bắt đầu → Xong", phong_lam),
            ("11. Tệp kết quả về", ket_qua_ve),
            ("9. Bác sĩ chính Khám xong", kham_xong),
        ]

        print(f"\nKHÁCH GIẢ {k.patient} — luồng chuẩn 23/09/2026\n")
        for ten, lam in buoc:
            truoc = await _moc(pool)
            print(f"── {ten}")
            try:
                await lam()
            except Exception as exc:  # noqa: BLE001 — bước hỏng là một phát hiện
                loi += 1
                print(f"  ✗ HỎNG: {type(exc).__name__}: {exc}")
                if os.environ.get("CHI_TIET"):
                    traceback.print_exc()
            await _chay_nguoi_dua_tin(pool)
            for d in await _bao_cao_su_kien(pool, k, truoc):
                print(d)
            for d in await _node_thay_gi(pool, k):
                print(d)
            print()
    finally:
        await pool.close()
    print(f"Xong. {loi} bước hỏng." if loi else "Xong. Mọi bước chạy được.")
    return 1 if loi else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--bo-sinh-hieu",
        action="store_true",
        help="Khách không đo sinh hiệu (luồng chuẩn bước 6).",
    )
    sys.exit(asyncio.run(main(ap.parse_args().bo_sinh_hieu)))
