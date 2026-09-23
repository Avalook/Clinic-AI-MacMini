"""Lệnh `PlaceServiceOrders` — bác sĩ/thư ký y khoa chốt chỉ định dịch vụ.

LÁT CD-01. Đặc tả đầy đủ: `docs/slices/CD-01-bac-si-chi-dinh-dich-vu.md`.

VÌ SAO CÓ FILE MỚI THAY VÌ SỬA ĐƯỜNG CŨ. Đường cũ là hai bước: thư ký gửi
`draft-orders`, rồi bác sĩ bấm `authorize-orders`. Tuyền đã chốt (22/09, tin
#149): **thư ký y khoa ngang quyền bác sĩ về chỉ định, chỉ định là chỉ định
luôn**, không có bước duyệt. Nhưng đường cũ đang phục vụ bệnh nhân thật, nên nó
được GIỮ NGUYÊN và lệnh mới nằm cạnh — đổi đường bằng cách chuyển màn sang gọi
lệnh mới, không phải bằng cách sửa ruột đường cũ (branch by abstraction). Khi
màn cuối cùng đã chuyển, đường cũ bị xoá trong một commit.

KHÁC ĐƯỜNG CŨ Ở BỐN CHỖ
  1. Một lệnh thay hai bước; không còn trạng thái `draft`.
  2. Thư ký y khoa (TKYK) chỉ định được, không cần ai duyệt.
  3. Mỗi dịch vụ phát một sự kiện `service_order.placed` vào `domain_event`,
     cùng giao dịch với việc ghi chỉ định.
  4. Chống bấm trùng bằng `Idempotency-Key`, và biên nhận nằm TRONG chính giao
     dịch ấy.

CÁI GIỮ NGUYÊN: tự xếp phòng sau khi chỉ định, và `record_event` vào nhật ký
thao tác — vì màn "Lịch sử thao tác" đang đọc sổ ấy. Ghi cả hai sổ ở giai đoạn
giao thời là có chủ ý, và sẽ bỏ khi màn nhật ký chuyển sang đọc `domain_event`.
"""

from __future__ import annotations

from typing import Any

import asyncpg

from clinicai.api.identity import StaffIdentity
from clinicai.events.catalogue import ChiDinhDaDat
from clinicai.events.emit import emit_event, nguoi
from clinicai.permissions.can import doi_quyen
from clinicai.services.audit import record_event
from clinicai.services.luot_kham_service import (
    LuotKhamConflictError,
    LuotKhamService,
    _uuid,
)
from clinicai.services.luot_kham_service import (
    LuotKhamValidationError as ValidationError,
)

#: Quyền cần có để chỉ định. KHÔNG phải một tập vai: ai được cấp khối "Chỉ định
#: dịch vụ" thì làm được, kể cả vai mà hôm nay chưa nghĩ tới. Bác sĩ và thư ký y
#: khoa có sẵn trong preset (Tuyền, tin #149); quản lý cấp thêm cho ai là việc
#: của màn phân quyền, không phải việc của file này.
QUYEN_CHI_DINH = "clinical.order.place"

ACTION = "chi_dinh.dat"
ORIGIN = "api:chi-dinh"


class ChiDinhService:
    """Cửa duy nhất để tạo chỉ định chính thức theo lát CD-01."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def dat_chi_dinh(
        self,
        *,
        consultation_id: str,
        service_codes: list[str],
        identity: StaffIdentity,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Chốt một loạt chỉ định cho phiên khám. Trả về danh sách id đã tạo."""
        cid = identity.clinic_id
        con_id = _uuid(consultation_id, "Mã phiên khám không hợp lệ.")
        codes = [c.strip() for c in service_codes if isinstance(c, str) and c.strip()]
        if not codes:
            raise ValidationError("NO_SERVICE", "Chưa chọn dịch vụ nào.")
        # Bấm nhầm hai lần cùng một dịch vụ trong một lần gửi: coi là một.
        codes = list(dict.fromkeys(codes))

        payload_bien_nhan = {"consultation_id": con_id, "codes": sorted(codes)}
        luot_kham = LuotKhamService(self._pool)

        async with self._pool.acquire() as conn, conn.transaction():
            # Kiểm quyền TRƯỚC mọi thứ khác, và kiểm trong chính giao dịch này.
            await doi_quyen(conn, identity, QUYEN_CHI_DINH)
            vid = await LuotKhamService._visit_of(conn, "consultation", cid, con_id)
            await LuotKhamService._lock_visit(conn, cid, vid)

            cached = await LuotKhamService._receipt_get(
                conn, identity, ACTION, idempotency_key, payload_bien_nhan
            )
            if cached is not None:
                return cached

            consultation = await luot_kham._consultation_in_progress(conn, cid, con_id)

            dich_vu = await luot_kham._services(conn, cid, codes)
            ids: list[str] = []
            for s in dich_vu:
                order_id = await conn.fetchval(
                    """
                    INSERT INTO service_order
                        (clinic_id, visit_id, consultation_id, service_code,
                         service_name, node_code, exec_status, recorded_by,
                         authorized_by, authorized_at, selection_status,
                         routing_status)
                    VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6,
                            'authorized', $7::uuid, $7::uuid, now(),
                            'PENDING', 'UNASSIGNED')
                    RETURNING id::text
                    """,
                    cid,
                    vid,
                    con_id,
                    s["service_code"],
                    s["name"],
                    s["node_code"],
                    identity.staff_id,
                )
                ids.append(order_id)

                # Sự kiện đi CÙNG giao dịch với chỉ định: lệnh hỏng thì không có
                # sự kiện mồ côi, và ngược lại.
                await emit_event(
                    conn,
                    ten="service_order.placed",
                    clinic_id=cid,
                    aggregate_id=order_id,
                    aggregate_version=1,
                    payload=ChiDinhDaDat(
                        order_id=order_id,
                        service_code=s["service_code"],
                        service_name=s["name"],
                        consultation_id=con_id,
                        visit_id=vid,
                        selection_status="PENDING",
                        billing_status="UNPAID",
                    ),
                    boi=nguoi(identity),
                    # Cả chuỗi việc của một lượt khám nối với nhau bằng đây.
                    correlation_id=vid,
                )

            # Giữ nguyên hành vi cũ: chỉ định xong tự vào hàng chờ phòng làm
            # được. Không ném lỗi làm hỏng lệnh (xem _tu_xep_phong).
            await luot_kham._tu_xep_phong(conn, identity, vid)

            await record_event(
                conn,
                event_type="service_order.placed",
                aggregate_type="visit",
                aggregate_id=vid,
                identity=identity,
                origin=ORIGIN,
                payload={
                    "visit_id": vid,
                    "consultation_id": con_id,
                    "order_ids": ids,
                    "round_no": consultation["round_no"],
                },
            )

            result = {"ok": True, "order_ids": ids}
            await LuotKhamService._receipt_put(
                conn,
                identity,
                ACTION,
                idempotency_key,
                payload_bien_nhan,
                con_id,
                result,
            )
        return result


__all__ = ["ACTION", "QUYEN_CHI_DINH", "ChiDinhService", "LuotKhamConflictError"]
