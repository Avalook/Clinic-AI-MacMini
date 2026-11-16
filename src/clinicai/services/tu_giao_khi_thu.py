"""Thu tiền thuốc xong là GIAO luôn — trừ kho ngay lúc thu (Tuyền 16/11/2026).

Thực tế quầy: tạo bill thu tiền là xong việc, không ai bấm "Giao thuốc" nữa —
nên kho quầy không bao giờ bị trừ và kiểm ca lệch. Từ nay, lần thu tiền thuốc
vừa thành PAID (tiền mặt lúc thu, chuyển khoản / QR lúc xác minh) giao luôn số
khách đã mua, trong CÙNG giao dịch với lần thu, qua đúng thân hàm giao
(`PharmacyService.giao_trong_giao_dich` → `_giao_tu_chon_lo`). Không có đường giao
thứ hai.

* Trừ QUẦY trước (FEFO); quầy không đủ → phần còn lại trừ ở KHO (FEFO, chỉ cơ sở
  đã tách kho), dòng sổ ghi "lấy từ kho"; cả hai thiếu → phần thiếu vào sổ "đã
  giao, chưa gắn lô". Thu tiền KHÔNG bao giờ bị chặn vì kho.
* Khoá MỌI lô có thể giao của MỌI thuốc trong lần thu một lần, id tăng dần, trước
  khi giao từng dòng — khoá theo từng thuốc thì kiểm ca / hoàn tác kiểm kho / lần
  thu khác (khoá nhiều thuốc theo id) khoá chéo được → deadlock.
* Dòng không giao được (đã bán theo lô, dòng đã chốt…) → bỏ qua, nút Giao vẫn còn
  cho dòng ấy. Mỗi dòng một savepoint: dòng hỏng không kéo lần thu đổ theo. Dòng
  bỏ qua được TRẢ VỀ cho người gọi: lần thu trả cho màn, lỗi Postgres còn ghi kho
  lỗi `loi_nhom` (/ops "Lỗi & cảnh báo") — không chỉ nằm trong log.
* Hoàn tác lần thu đảo mọi lần giao về ĐÚNG lô đã lấy — lô quầy về quầy, lô kho
  về kho (`dao_giao_khi_huy_phieu`) — và huỷ phần chờ gán, nên thu → hoàn tác →
  mọi lô về đúng số cũ.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from decimal import Decimal

import asyncpg
import structlog

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.services.kho_loi import ghi_loi

logger = structlog.get_logger()

#: Vị trí ghi ở kho lỗi `loi_nhom` khi Postgres từ chối giao một dòng lúc thu.
VI_TRI_LOI = "tu_giao_khi_thu: giao lúc thu bị Postgres từ chối"
_CHUA_GIAO = "Chưa giao được lúc thu — bấm Giao thuốc cho dòng này."


@dataclass
class KetQuaTuGiao:
    """Kết quả tự giao của MỘT lần thu."""

    da_giao: int = 0
    #: Mỗi dòng bỏ qua: {"prescription_id", "ly_do"} — cho màn biết dòng nào còn
    #: phải bấm Giao.
    bo_qua: list[dict[str, str]] = field(default_factory=list)
    #: Lỗi Postgres (deadlock, chốt kho…) — ghi kho lỗi SAU khi giao dịch xong.
    loi_db: list[BaseException] = field(default_factory=list)


async def ghi_loi_tu_giao(pool: asyncpg.Pool | None, kq: KetQuaTuGiao) -> None:
    """Ghi các lỗi Postgres của lần tự giao vào kho lỗi. Gọi NGOÀI giao dịch của
    lần thu (kho lỗi có pool riêng, trần 0,5 giây, không bao giờ ném)."""
    for loi in kq.loi_db:
        await ghi_loi(pool, nguon="api", vi_tri=VI_TRI_LOI, exc=loi)


async def tu_giao_khi_thu(
    conn: asyncpg.Connection,
    *,
    identity: StaffIdentity,
    cycle_id: str,
) -> KetQuaTuGiao:
    """Giao phần đã mua mà chưa giao của mọi dòng thuốc trong lần thu `cycle_id`.

    Người gọi đang giữ giao dịch của lần thu (lượt đã khoá) và lần thu đã PAID."""
    from clinicai.services.pharmacy_service import PharmacyService, khoa_lo_de_giao

    kq = KetQuaTuGiao()
    # Công tắc tắt khẩn (đổi biến môi trường, không cần deploy). Mặc định BẬT.
    # Test kiểm cơ chế nút Giao (vẫn sống cho lượt cũ / dòng bị bỏ qua) tắt nó.
    if os.getenv("CLINICAI_TU_GIAO_KHI_THU", "1").strip() == "0":
        return kq
    dong = await conn.fetch(
        """
        SELECT r.id::text AS rx, r.drug_catalog_id::text AS thuoc,
               public.co_so_cua_luot(r.clinic_id, r.visit_id)::text AS co_so,
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
    dong = [d for d in dong if Decimal(str(d["con"])) > 0]
    if not dong:
        return kq
    # Khoá một lần mọi lô của mọi thuốc (id tăng dần) — giữ tới hết giao dịch thu.
    # Savepoint riêng: bên khác khoá ngược thứ tự mà Postgres huỷ phía mình
    # (deadlock) thì lần thu vẫn xong, mọi dòng ghi "bỏ qua" + kho lỗi.
    co_so = dong[0]["co_so"] or identity.location_id
    try:
        async with conn.transaction():
            await khoa_lo_de_giao(
                conn,
                clinic_id=identity.clinic_id,
                co_so=co_so,
                thuoc_ids=[d["thuoc"] for d in dong if d["thuoc"]],
            )
    except asyncpg.PostgresError as exc:
        kq.loi_db.append(exc)
        kq.bo_qua = [{"prescription_id": d["rx"], "ly_do": _CHUA_GIAO} for d in dong]
        logger.warning(
            "tu_giao_khi_thu_khoa_lo_hong",
            payment_cycle_id=cycle_id,
            ly_do=str(exc)[:200],
        )
        return kq
    # Không dùng pool: mọi thứ chạy trên `conn` của lần thu.
    svc = PharmacyService(None)
    for d in dong:
        try:
            async with conn.transaction():
                await svc.giao_trong_giao_dich(
                    conn,
                    identity=identity,
                    prescription_id=d["rx"],
                    drug_batch_id=None,
                    luong=Decimal(str(d["con"])),
                )
            kq.da_giao += 1
        except (ConflictError, ValidationError, NotFoundError) as exc:
            kq.bo_qua.append({"prescription_id": d["rx"], "ly_do": str(exc)[:200]})
            logger.info(
                "tu_giao_khi_thu_bo_qua",
                prescription_id=d["rx"],
                payment_cycle_id=cycle_id,
                ly_do=str(exc)[:200],
            )
        except asyncpg.PostgresError as exc:
            # Chốt ở Postgres từ chối (deadlock, migration chốt kho chưa áp…):
            # savepoint của dòng đã cuộn lại sạch, lần thu vẫn xong — thu tiền không
            # bao giờ hỏng vì kho. Dòng còn chờ bấm Giao; người gọi ghi kho lỗi.
            kq.bo_qua.append({"prescription_id": d["rx"], "ly_do": _CHUA_GIAO})
            kq.loi_db.append(exc)
            logger.warning(
                "tu_giao_khi_thu_db_tu_choi",
                prescription_id=d["rx"],
                payment_cycle_id=cycle_id,
                ly_do=str(exc)[:200],
            )
    return kq
