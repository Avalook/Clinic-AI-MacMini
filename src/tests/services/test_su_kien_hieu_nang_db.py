"""Hợp đồng tốc độ của đường sự kiện — đo thật, không hứa suông.

Tuyền chốt (#43): thao tác lõi không được chờ AI, không N+1, và người bấm không
phải trả giá cho việc nền. Ở đây đo ba thứ có thể làm chậm bàn khám:

  1. Phát một sự kiện tốn bao lâu — nó nằm TRONG giao dịch của người bấm.
  2. Lấy việc ra giao có dùng chỉ mục không, hay quét cả bảng.
  3. Câu hỏi quyền (`can`) tốn bao lâu — nó chạy ở MỌI lệnh.

Ngưỡng đặt rộng rãi vì máy chạy test không phải máy chủ thật; mục đích là bắt
kiểu hỏng "chậm gấp trăm lần" (quét bảng, thiếu chỉ mục), không phải đo chính xác
mili giây.
"""

from __future__ import annotations

import os
import statistics
import time
import uuid
from typing import Any

import asyncpg
import pytest
import pytest_asyncio

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.events.catalogue import ChiDinhDaDat
from clinicai.events.emit import HE_THONG, emit_event
from clinicai.permissions import cache
from clinicai.permissions.can import can

CLINIC = "a0000000-0000-4000-8000-000000000001"

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

#: Phát một sự kiện + sinh dòng giao, tính trung bình trên 50 lần.
NGUONG_PHAT_MS = 25.0
#: Một câu hỏi quyền.
NGUONG_HOI_QUYEN_MS = 15.0


@pytest_asyncio.fixture
async def pool() -> Any:
    url = os.environ.get("DATABASE_URL") or ""
    if not url:
        pytest.skip("cần DATABASE_URL_TEST trỏ tới database dùng một lần")
    dsn = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    p = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=4)
    yield p
    await p.close()


def _payload(order_id: str, visit_id: str) -> ChiDinhDaDat:
    return ChiDinhDaDat(
        order_id=order_id,
        service_code="SA-DAUDO",
        service_name="Siêu âm đầu dò",
        consultation_id=str(uuid.uuid4()),
        visit_id=visit_id,
        selection_status="PENDING",
        billing_status="UNPAID",
    )


async def test_phat_su_kien_khong_lam_cham_nguoi_bam(pool: asyncpg.Pool) -> None:
    """Đo mức GIỮA, không đo trung bình.

    Đo bằng trung bình thì một lượt "nguội" là hỏng cả phép đo: lần phát đầu sau
    khi máy rảnh hoặc sau một đợt ghi lớn mất ~35ms, còn mức thường là ~1,5ms.
    Trung bình của 49 lượt nhanh và 1 lượt nguội vẫn báo động — và một bài kiểm
    hay báo động nhầm là một bài kiểm sẽ bị nới cho im.

    Đo thật ngày 23/09 trên sổ 500.000 sự kiện (224 MB): 1,3–1,7ms mỗi lượt. Sổ
    lớn dần KHÔNG làm chậm việc phát, vì nó chỉ thêm vào cuối.
    """
    visit_id = str(uuid.uuid4())

    async def mot_luot(conn: asyncpg.Connection) -> float:
        bat_dau = time.perf_counter()
        async with conn.transaction():
            order_id = str(uuid.uuid4())
            await emit_event(
                conn,
                ten="service_order.placed",
                clinic_id=CLINIC,
                aggregate_id=order_id,
                aggregate_version=1,
                payload=_payload(order_id, visit_id),
                boi=HE_THONG,
            )
        return (time.perf_counter() - bat_dau) * 1000

    async with pool.acquire() as conn:
        for _ in range(5):  # làm nóng: chuẩn bị câu lệnh, đánh thức kết nối
            await mot_luot(conn)
        do_duoc = [await mot_luot(conn) for _ in range(50)]

    giua_ms = statistics.median(do_duoc)
    assert giua_ms < NGUONG_PHAT_MS, (
        f"Phát một sự kiện mất {giua_ms:.1f}ms (mức giữa của 50 lượt) — người bấm "
        "đang trả giá cho việc nền. Xem lại chỉ mục hoặc số dòng giao mỗi lần."
    )


async def test_lay_viec_ra_giao_dung_chi_muc(pool: asyncpg.Pool) -> None:
    """Không được quét cả bảng: hàng đợi chỉ to lên theo ngày.

    Phải bơm dữ liệu trước rồi mới hỏi kế hoạch: với bảng vài chục dòng thì quét
    hết CÒN nhanh hơn dùng chỉ mục, nên Postgres chọn quét — và bài kiểm sẽ đỏ vì
    một lý do không có thật.
    """
    visit_id = str(uuid.uuid4())
    async with pool.acquire() as conn:
        async with conn.transaction():
            for _ in range(300):
                order_id = str(uuid.uuid4())
                await emit_event(
                    conn,
                    ten="service_order.placed",
                    clinic_id=CLINIC,
                    aggregate_id=order_id,
                    aggregate_version=1,
                    payload=_payload(order_id, visit_id),
                    boi=HE_THONG,
                )
        await conn.execute("ANALYZE event_delivery")

    ke_hoach = await pool.fetch(
        """
        EXPLAIN (FORMAT TEXT)
        SELECT d.event_id FROM event_delivery d
         WHERE d.consumer = 'dong_thoi_gian_luot'
           AND d.status IN ('PENDING', 'RETRY')
           AND d.next_attempt_at <= now()
         ORDER BY d.next_attempt_at
         LIMIT 1
        """
    )
    chu = "\n".join(r["QUERY PLAN"] for r in ke_hoach)
    assert "Seq Scan" not in chu, f"Câu lấy việc đang quét cả bảng:\n{chu}"


async def test_hoi_quyen_du_nhanh_de_dung_o_moi_lenh(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        loc = await conn.fetchval(
            "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid"
            " AND is_active ORDER BY created_at, id LIMIT 1",
            CLINIC,
        )
        sid = await conn.fetchval(
            "INSERT INTO staff (full_name, primary_department, primary_location_id,"
            " is_active) VALUES ('Test toc do', 'DOCTOR', $1::uuid, true)"
            " RETURNING id::text",
            loc,
        )
        await conn.execute(
            "INSERT INTO clinic_membership (clinic_id, staff_id, role, is_active)"
            " VALUES ($1::uuid, $2::uuid, 'DOCTOR', true)"
            " ON CONFLICT (clinic_id, staff_id, role) DO NOTHING",
            CLINIC,
            sid,
        )
        # Người THẬT SỰ có quyền: đó mới là đường chạy vài nghìn lượt mỗi ca.
        await conn.execute(
            "INSERT INTO capability_grant (clinic_id, staff_id, capability, tu_khoi)"
            " VALUES ($1::uuid, $2::uuid, 'clinical.order.place', 'chi_dinh')"
            " ON CONFLICT DO NOTHING",
            CLINIC,
            sid,
        )
        identity = StaffIdentity(
            staff_id=sid,
            auth_user_id=str(uuid.uuid4()),
            full_name="Test toc do",
            department="DOCTOR",
            role=ClinicRole.DOCTOR,
            clinic_id=CLINIC,
            location_id=loc,
            location_name="Cơ sở test",
        )
        cache.quen(CLINIC, sid)
        await can(conn, identity, "clinical.order.place")  # làm nóng + nạp nhớ

        so_lan = 50
        bat_dau = time.perf_counter()
        for _ in range(so_lan):
            await can(conn, identity, "clinical.order.place")
        trung_binh_ms = (time.perf_counter() - bat_dau) * 1000 / so_lan

    assert trung_binh_ms < NGUONG_HOI_QUYEN_MS, (
        f"Hỏi quyền mất {trung_binh_ms:.1f}ms mà mọi lệnh đều hỏi — "
        "xem lại chỉ mục trên capability_grant."
    )


async def test_hoi_quyen_khong_quet_ca_bang(pool: asyncpg.Pool) -> None:
    ke_hoach = await pool.fetch(
        """
        EXPLAIN (FORMAT TEXT)
        SELECT 1 FROM v_quyen_hieu_luc q
         WHERE q.clinic_id = $1::uuid
           AND q.staff_id = $1::uuid
           AND q.capability = 'clinical.order.place'
        """,
        CLINIC,
    )
    chu = "\n".join(r["QUERY PLAN"] for r in ke_hoach)
    assert "Seq Scan on capability_grant" not in chu, (
        f"Câu hỏi quyền đang quét cả bảng cấp quyền:\n{chu}"
    )
