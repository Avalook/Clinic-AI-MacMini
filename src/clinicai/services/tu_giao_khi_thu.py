"""Thu tiền thuốc xong là GIAO luôn — trừ kho quầy ngay lúc thu (Tuyền 16/11/2026).

Thực tế quầy: tạo bill thu tiền là xong việc, không ai bấm "Giao thuốc" nữa —
nên kho quầy không bao giờ bị trừ và kiểm ca lệch. Từ nay, lần thu tiền thuốc
vừa thành PAID (tiền mặt lúc thu, chuyển khoản / QR lúc xác minh) giao luôn số
khách đã mua, trong CÙNG giao dịch với lần thu, qua đúng thân hàm giao
(`PharmacyService.giao_trong_giao_dich` → `_giao_tu_chon_lo`). Không có đường giao
thứ hai.

* Trừ QUẦY trước (FEFO); quầy không đủ → phần còn lại trừ ở KHO (FEFO), dòng sổ
  ghi "lấy từ kho"; cả hai thiếu → phần thiếu vào sổ "đã giao, chưa gắn lô". Thu
  tiền KHÔNG bao giờ bị chặn vì kho.
* Dòng không giao được (đã bán theo lô — công tắc giữ chỗ lô cũ, dòng đã chốt…)
  → bỏ qua, nút Giao vẫn còn cho dòng ấy. Mỗi dòng một savepoint: dòng hỏng
  không kéo lần thu đổ theo.
* Hoàn tác lần thu đảo mọi lần giao về ĐÚNG lô đã lấy — lô quầy về quầy, lô kho
  về kho (`dao_giao_khi_huy_phieu`) — và huỷ phần chờ gán, nên thu → hoàn tác →
  mọi lô về đúng số cũ.
"""

from __future__ import annotations

import os
from decimal import Decimal

import asyncpg
import structlog

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity

logger = structlog.get_logger()


async def tu_giao_khi_thu(
    conn: asyncpg.Connection,
    *,
    identity: StaffIdentity,
    cycle_id: str,
) -> int:
    """Giao phần đã mua mà chưa giao của mọi dòng thuốc trong lần thu `cycle_id`.

    Người gọi đang giữ giao dịch của lần thu (lượt đã khoá) và lần thu đã PAID.
    Trả số dòng đã giao."""
    from clinicai.services.pharmacy_service import PharmacyService

    # Công tắc tắt khẩn (đổi biến môi trường, không cần deploy). Mặc định BẬT.
    # Test kiểm cơ chế nút Giao (vẫn sống cho lượt cũ / dòng bị bỏ qua) tắt nó.
    if os.getenv("CLINICAI_TU_GIAO_KHI_THU", "1").strip() == "0":
        return 0
    dong = await conn.fetch(
        """
        SELECT r.id::text AS rx,
               b.quantity - coalesce(r.dispensed_qty, 0) AS con
          FROM public.payment_bill_line b
          JOIN public.prescription r
            ON r.id::text = b.source_id AND r.clinic_id = b.clinic_id
         WHERE b.clinic_id = $1::uuid AND b.payment_cycle_id = $2::uuid
           AND b.kind = 'thuoc' AND b.source_type = 'prescription'
           AND r.closed_at IS NULL AND r.removed_at IS NULL
         ORDER BY r.created_at, r.id
        """,
        identity.clinic_id,
        cycle_id,
    )
    # Không dùng pool: mọi thứ chạy trên `conn` của lần thu.
    svc = PharmacyService(None)
    da_giao = 0
    for d in dong:
        con = Decimal(str(d["con"]))
        if con <= 0:
            continue
        try:
            async with conn.transaction():
                await svc.giao_trong_giao_dich(
                    conn,
                    identity=identity,
                    prescription_id=d["rx"],
                    drug_batch_id=None,
                    luong=con,
                )
            da_giao += 1
        except (ConflictError, ValidationError, NotFoundError) as exc:
            logger.info(
                "tu_giao_khi_thu_bo_qua",
                prescription_id=d["rx"],
                payment_cycle_id=cycle_id,
                ly_do=str(exc)[:200],
            )
        except asyncpg.PostgresError as exc:
            # Chốt ở Postgres từ chối (vd. migration chốt kho chưa áp): savepoint
            # của dòng đã cuộn lại sạch, lần thu vẫn xong — thu tiền không bao giờ
            # hỏng vì kho. Mức cảnh báo: dòng này còn chờ bấm Giao.
            logger.warning(
                "tu_giao_khi_thu_db_tu_choi",
                prescription_id=d["rx"],
                payment_cycle_id=cycle_id,
                ly_do=str(exc)[:200],
            )
    return da_giao
