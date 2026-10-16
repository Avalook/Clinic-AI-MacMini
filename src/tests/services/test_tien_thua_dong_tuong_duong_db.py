"""`_DONG_THUA_SQL` viết lại (đi từ lượt, 14/10/2026) PHẢI trả Y HỆT bản cũ.

    scripts/test-nhanh.sh src/tests/services/test_tien_thua_dong_tuong_duong_db.py

Bản cũ (đo prod: 171 ms × 67k lần) dựng cả bảng dòng hoá đơn đã thu rồi lọc theo
lượt ở cuối. Bản mới đi từ lượt. Đây là tiền: khác MỘT dòng / MỘT đồng là hỏng.
Bài này giữ NGUYÊN VĂN câu SQL cũ làm thước và so từng dòng, từng cột, đúng thứ
tự, trên dữ liệu do lệnh thật tạo (thu, huỷ phiếu, CK chờ, hoàn, bỏ chỉ định,
giữ lại, ghi nợ, về, tick / bỏ tick dịch vụ khám) — cho từng lượt, cho cả tập
lượt, cho tập con ngẫu nhiên và cho đầu vào rác.
"""

from __future__ import annotations

import random
import uuid
from typing import Any

import asyncpg
import pytest

from clinicai.core.exceptions import ClinicAIBaseException
from clinicai.services.bill_service import tinh_hoa_don
from clinicai.services.hoan_tac_service import HoanTacService
from clinicai.services.payment_service import PaymentService
from clinicai.services.phi_kham_service import PhiKhamService
from clinicai.services.tien_thua_service import _DONG_THUA_SQL, dong_tien_thua
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_full_chi_dinh_slice_ab_db import (
    BoKichBan,
    kban,  # noqa: F401
)
from tests.services.test_mo_phong_dong_tien_db import (  # noqa: F401
    VIEC,
    _lam_truoc_thu_sau,
    _luot,
)
from tests.services.test_phu_thu_cu_doc_duoc_db import (
    _dich_vu_co_dau_do,
    _gan_loai_kham_co_gia,
    _thu_ngan,
    _tick_cu,
)
from tests.services.test_thu_dich_vu_nhieu_lan_db import (
    _hd,
    _phi_kham_con,
    _thu,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import _dung
from tests.services.test_tien_thuoc_cp1_db import Quay, tao_quay

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

#: BẢN CŨ, nguyên văn (trước 14/10/2026) — thước đo, KHÔNG sửa.
_DONG_THUA_SQL_CU = """
WITH dong AS (
    SELECT bl.id::text AS line_id, bl.visit_id::text AS line_visit_id,
           bl.payment_cycle_id::text AS payment_cycle_id,
           hinh_thuc_hieu_luc(c.clinic_id, c.payment_cycle_id, c.method)
               AS hinh_thuc,
           bl.source_type,
           bl.source_id, bl.name_snapshot, bl.quantity, bl.line_total,
           CASE WHEN bl.source_type = 'service_order' THEN bl.source_id
                WHEN bl.source_type = 'phu_thu' THEN (
                    SELECT p.service_order_id::text FROM public.luot_phu_thu p
                     WHERE p.clinic_id = bl.clinic_id AND p.id::text = bl.source_id)
           END AS order_id,
           coalesce(h.sl, 0) AS da_hoan_sl, coalesce(h.tien, 0) AS da_hoan
      FROM public.payment_bill_line bl
      JOIN public.payment_cycle c
        ON c.clinic_id = bl.clinic_id AND c.payment_cycle_id = bl.payment_cycle_id
      LEFT JOIN LATERAL (
           SELECT sum(l.quantity) AS sl, sum(l.amount) AS tien
             FROM public.payment_refund_line l
             JOIN public.payment_refund r
               ON r.refund_id = l.refund_id AND r.clinic_id = l.clinic_id
            WHERE l.clinic_id = bl.clinic_id AND l.payment_bill_line_id = bl.id
              AND r.status IN ('PENDING', 'COMPLETED')) h ON true
     WHERE bl.clinic_id = $1::uuid AND c.status = 'PAID'
       AND bl.billing_owner = 'CLINIC' AND bl.kind = 'dich_vu'
       AND bl.source_type IN ('service_order', 'phu_thu', 'exam')
)
SELECT d.*, coalesce(o.visit_id::text, d.line_visit_id) AS visit_id,
       o.exec_status, o.cancel_reason, o.not_performed_reason
  FROM dong d
  LEFT JOIN public.service_order o
    ON o.clinic_id = $1::uuid AND o.id::text = d.order_id
 WHERE d.line_total - d.da_hoan > 0
   AND (
        (d.source_type IN ('service_order', 'phu_thu')
         AND o.exec_status IN ('cancelled', 'not_performed')
         AND o.visit_id::text = ANY($2::text[]))
     OR (d.source_type = 'exam' AND d.line_visit_id = ANY($2::text[])
         AND d.source_id LIKE 'exam-%-selected-%'
         AND NOT EXISTS (
             SELECT 1 FROM public.luot_phi_kham k
              WHERE k.clinic_id = $1::uuid AND k.visit_id::text = d.line_visit_id
                AND k.bo_luc IS NULL
                AND d.source_id = 'exam-' || k.visit_id::text || '-selected-'
                                  || k.service_price_id::text))
   )
 ORDER BY d.line_visit_id, d.payment_cycle_id, d.line_id
"""


async def _cu(conn: asyncpg.Connection, ids: list[str]) -> list[dict[str, Any]]:
    return [dict(r) for r in await conn.fetch(_DONG_THUA_SQL_CU, CLINIC, ids)]


async def _moi(conn: asyncpg.Connection, ids: list[str]) -> list[dict[str, Any]]:
    # Cùng bước lọc đầu vào như `dong_tien_thua` (rác bị bỏ trước khi vào SQL).
    sach = [s for s in ids if _la_uuid_thuong(s)]
    if not sach:
        return []
    return [dict(r) for r in await conn.fetch(_DONG_THUA_SQL, CLINIC, sach)]


def _la_uuid_thuong(s: str) -> bool:
    try:
        return str(uuid.UUID(s)) == s
    except ValueError:
        return False


async def _so_sanh(conn: asyncpg.Connection, ids: list[str]) -> int:
    """Hai bản trả CÙNG danh sách dòng (cột, giá trị, thứ tự). Trả số dòng."""
    cu, moi = await _cu(conn, ids), await _moi(conn, ids)
    assert moi == cu, f"khác nhau với {ids}:\ncũ={cu}\nmới={moi}"
    # Hàm công khai cũng khớp: gom theo lượt từ chính các dòng của bản cũ.
    ra = await dong_tien_thua(conn, CLINIC, ids)
    assert sorted(ra) == sorted({d["visit_id"] for d in cu})
    assert sum(len(v) for v in ra.values()) == len(cu)
    return len(cu)


async def test_tuong_duong_bam_ngau_nhien(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    visits: list[str] = []
    so_dong = 0
    so_lan = 0
    for hat in range(80):
        rnd = random.Random(1000 + hat)
        v, o = await _luot(pool, ca)
        visits.append(v)
        for _ in range(10):
            ten = rnd.choice(sorted(VIEC))
            try:
                await VIEC[ten](pool, ca, v, o)
            except (ClinicAIBaseException, AssertionError, asyncpg.PostgresError):
                continue  # màn không cho bước này — người thật cũng bị chặn
            async with pool.acquire() as conn:
                so_dong += await _so_sanh(conn, [v])
                so_lan += 1
    async with pool.acquire() as conn:
        # Cả tập lượt một lần + các tập con ngẫu nhiên + lượt xen lẫn rác.
        so_dong += await _so_sanh(conn, visits)
        rnd = random.Random(7)
        for _ in range(20):
            sub = rnd.sample(visits, rnd.randint(1, len(visits)))
            so_dong += await _so_sanh(conn, sub)
        rac = ["", "abc", "không-phải-uuid", visits[0].upper(), str(uuid.uuid4())]
        await _so_sanh(conn, rac)
        await _so_sanh(conn, [*rac, *visits[:5]])
        assert await dong_tien_thua(conn, CLINIC, []) == {}
        assert await dong_tien_thua(conn, CLINIC, rac) == {}
    # Bài không rỗng: có đủ ca CÓ tiền thừa để phép so sánh có nghĩa.
    assert so_lan >= 300
    assert so_dong >= 30, f"chỉ {so_dong} dòng tiền thừa — kịch bản quá nhạt"


async def test_tuong_duong_tien_kham_bo_tick(pool: asyncpg.Pool) -> None:  # noqa: F811
    """Dịch vụ khám đã thu rồi bỏ tick: dòng `exam` còn tiền thừa."""
    q: Quay = await tao_quay(pool)
    a = await _phi_kham_con(q, f"Khám A {q.duoi}", 180_000)
    b = await _phi_kham_con(q, f"Khám B {q.duoi}", 220_000)
    svc = PhiKhamService(q.pool)
    await svc.chon(visit_id=q.visit_id, ids=[a, b], identity=q.bac_si)
    hd = await _hd(q)
    await _thu(q, bill_revision=hd.revision)
    async with pool.acquire() as conn:
        assert await _so_sanh(conn, [q.visit_id]) == 0  # còn tick: chưa thừa
        await svc.chon(visit_id=q.visit_id, ids=[a], identity=q.bac_si)
        n = await _so_sanh(conn, [q.visit_id])
        assert n == 1, "bỏ tick một dịch vụ khám đã thu phải ra đúng một dòng thừa"
        ra = (await dong_tien_thua(conn, CLINIC, [q.visit_id]))[q.visit_id]
        assert ra[0]["loai"] == "BO_DICH_VU_KHAM" and ra[0]["so_tien"] == 220_000
        # Tick lại → hết thừa.
        await svc.chon(visit_id=q.visit_id, ids=[a, b], identity=q.bac_si)
        assert await _so_sanh(conn, [q.visit_id]) == 0


async def test_tuong_duong_phu_thu_cu_bo_chi_dinh(kban: BoKichBan) -> None:  # noqa: F811
    """Dòng PHỤ THU đã thu rồi bỏ chỉ định cha: nhánh (2) của bản mới phải ra
    đúng hai dòng (dịch vụ + phụ thu) như bản cũ."""
    await _gan_loai_kham_co_gia(kban)
    oid, mau = await _dich_vu_co_dau_do(kban)
    ai = await _thu_ngan(kban)
    await _tick_cu(kban, oid, mau)
    async with kban.pool.acquire() as conn:
        hd = await tinh_hoa_don(
            conn,
            clinic_id=kban.bac_si.clinic_id,
            visit_id=kban.visit_id,
            kind="dich_vu",
        )
    await PaymentService(kban.pool).record_payment(
        visit_id=kban.visit_id,
        kind="dich_vu",
        amount=None,
        clinic_patient_id=None,
        identity=ai,
        bill_revision=hd.revision,
        method="CASH",
        idempotency_key=f"thu-phu-thu-{uuid.uuid4().hex}",
    )
    async with kban.pool.acquire() as conn:
        assert await _so_sanh(conn, [kban.visit_id]) == 0  # chưa bỏ → chưa thừa
    await HoanTacService(kban.pool).huy_chi_dinh(
        order_id=oid, identity=kban.bac_si, xac_nhan=True, ly_do="Khách đổi ý"
    )
    async with kban.pool.acquire() as conn:
        cu = await _cu(conn, [kban.visit_id])
        assert {d["source_type"] for d in cu} == {"service_order", "phu_thu"}
        assert await _so_sanh(conn, [kban.visit_id]) == 2
