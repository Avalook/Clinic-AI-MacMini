"""Sinh hiệu của lượt khám — gọi đo, bắt đầu đo, ghi số đo, đồng bộ từ hồ sơ.

Bóc khỏi ``luot_kham_service`` ngày 24/09/2026 (bước 4 đợt bóc lõi). Khối
``vitals`` (modules.py): ghi bảng của mình rồi PHÁT ``vitals.started`` /
``vitals.recorded``; xếp hàng tiếp theo là việc khối Hành trình nghe sự kiện.
Chỉ dựa vào nền chung (``lenh_kham_core``, ``hang_cho``), không dựa khối Khám.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any

import asyncpg
import structlog

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import (
    StaffIdentity,
)
from clinicai.core.clock import CLINIC_TZ
from clinicai.events.catalogue import (
    SinhHieuBatDau,
    SinhHieuDaDo,
)
from clinicai.events.emit import emit_event, nguoi
from clinicai.permissions.can import doi_quyen
from clinicai.services import luot_kham_rules as rules
from clinicai.services.audit import record_event
from clinicai.services.hang_cho import (
    cap_nhat_vi_tri,
)
from clinicai.services.lenh_kham_core import (
    LuotKhamConflictError,
    bien_nhan_doc,
    bien_nhan_ghi,
    khoa_flow,
    khoa_luot,
)
from clinicai.services.lenh_kham_core import ma_uuid as _uuid

logger = structlog.get_logger()

#: Giữ nguồn nhật ký cũ — đọc lại event_log không phải đổi truy vấn.
ORIGIN = "api:luot-kham"


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


class SinhHieuService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def goi_do_sinh_hieu(
        self, *, visit_id: str, identity: StaffIdentity
    ) -> dict[str, Any]:
        """Điều dưỡng GỌI khách vào đo sinh hiệu (Tuyền 17/09/2026: *"điều
        dưỡng gọi và đo sinh hiệu"*). Gọi lại thì cập nhật giờ gọi."""
        cid = identity.clinic_id
        vid = _uuid(visit_id, "Mã lượt khám không hợp lệ.")
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(conn, identity, "vitals.measure")
            await khoa_luot(conn, cid, vid)
            flow = await khoa_flow(conn, cid, vid)
            if flow["vitals_status"] == "recorded":
                raise LuotKhamConflictError(
                    "VITALS_DONE", "Khách này đã đo sinh hiệu rồi."
                )
            lan_goi_lai = await conn.fetchval(
                "SELECT goi_do_luc IS NOT NULL FROM encounter_flow"
                " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid",
                cid,
                vid,
            )
            await conn.execute(
                """
                UPDATE encounter_flow
                   SET goi_do_luc = now(), goi_do_boi = $3::uuid,
                       version = version + 1, updated_at = now()
                 WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                """,
                cid,
                vid,
                identity.staff_id,
            )
            await record_event(
                conn,
                event_type="vitals.called",
                aggregate_type="visit",
                aggregate_id=vid,
                identity=identity,
                origin=ORIGIN,
                payload={"visit_id": vid},
            )
        return {"ok": True, "lan_goi_lai": bool(lan_goi_lai)}

    async def bat_dau_do_sinh_hieu(
        self, *, visit_id: str, identity: StaffIdentity
    ) -> dict[str, Any]:
        """`StartVitals` — điều dưỡng bấm [Bắt đầu] đo cho khách này.

        Thay cho [Gọi vào đo] (Tuyền chốt 23/09/2026: `Gọi vào → Bắt đầu` là
        hai bước cho một việc). `pending → in_progress`, ghi ai bắt đầu và lúc
        nào, phát `vitals.started` ĐÚNG MỘT LẦN.

        BA TÌNH HUỐNG BẤM TRÙNG, xử lý khác nhau có chủ ý:

          * cùng người bấm hai lần (double-click, mạng chập) → `already=True`,
            không sự kiện thứ hai. Không phải lỗi, không làm người ta hoảng.
          * người KHÁC bấm sau → từ chối, nói rõ ai đã bắt đầu, lúc mấy giờ.
            Hai điều dưỡng cùng đo một khách là chuyện phải biết ngay.
          * hai người bấm CÙNG LÚC → `_lock_flow` khoá dòng; người sau chờ,
            rồi rơi vào một trong hai trường hợp trên.

        Mốc này là để ĐO THỜI GIAN CHỜ, không phải cửa khoá: lưu sinh hiệu mà
        chưa ai bấm [Bắt đầu] vẫn được (xem migration 20260923000015).

        CỬA QUYỀN theo VAI, không theo capability — CỐ Ý, và là nợ biết trước.
        Lệnh anh em ngay bên cạnh (`record_vitals`) vẫn gác bằng `VITALS_ROLES`.
        Hai nút trên CÙNG một màn mà gác bằng hai luật khác nhau thì lễ tân sẽ
        lưu được sinh hiệu nhưng không bấm được [Bắt đầu] (nhóm mẫu lễ tân
        chưa có khối Sinh hiệu). Chuyển cả hai sang `vitals.measure` là một
        bước riêng.
        """
        cid = identity.clinic_id
        vid = _uuid(visit_id, "Mã lượt khám không hợp lệ.")
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(conn, identity, "vitals.measure")
            await khoa_luot(conn, cid, vid)
            flow = await khoa_flow(conn, cid, vid)
            if flow["vitals_status"] == "recorded":
                raise LuotKhamConflictError(
                    "VITALS_DONE", "Khách này đã đo sinh hiệu rồi."
                )
            if flow["vitals_status"] == "in_progress":
                ai = await conn.fetchrow(
                    "SELECT f.vitals_started_by::text AS boi,"
                    "       f.vitals_started_at AS luc, s.full_name AS ten"
                    "  FROM encounter_flow f"
                    "  LEFT JOIN staff s ON s.id = f.vitals_started_by"
                    " WHERE f.clinic_id = $1::uuid AND f.visit_id = $2::uuid",
                    cid,
                    vid,
                )
                assert ai is not None  # vừa khoá trong cùng giao dịch
                if ai["boi"] == identity.staff_id:
                    return {
                        "ok": True,
                        "already": True,
                        "vitals_status": "in_progress",
                        "bat_dau_do_luc": _iso(ai["luc"]),
                    }
                gio = (
                    ai["luc"].astimezone(CLINIC_TZ).strftime("%H:%M")
                    if ai["luc"]
                    else "?"
                )
                raise LuotKhamConflictError(
                    "VITALS_STARTED_BY_OTHER",
                    f"{ai['ten'] or 'Người khác'} đã bắt đầu đo cho khách này"
                    f" lúc {gio}.",
                )

            luc = await conn.fetchval(
                """
                UPDATE encounter_flow
                   SET vitals_status = 'in_progress',
                       vitals_started_at = now(), vitals_started_by = $3::uuid,
                       version = version + 1, updated_at = now()
                 WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                RETURNING vitals_started_at
                """,
                cid,
                vid,
                identity.staff_id,
            )
            await record_event(
                conn,
                event_type="vitals.started",
                aggregate_type="visit",
                aggregate_id=vid,
                identity=identity,
                origin=ORIGIN,
                payload={"visit_id": vid},
            )
            await emit_event(
                conn,
                ten="vitals.started",
                clinic_id=cid,
                aggregate_id=vid,
                payload=SinhHieuBatDau(visit_id=vid),
                boi=nguoi(identity),
                correlation_id=vid,
            )
        return {
            "ok": True,
            "already": False,
            "vitals_status": "in_progress",
            "bat_dau_do_luc": _iso(luc),
        }

    async def dong_bo_sinh_hieu_tu_ho_so(
        self, conn: asyncpg.Connection, identity: StaffIdentity, visit_id: str
    ) -> str | None:
        """Sinh hiệu lưu qua BIỂU MẪU BỆNH ÁN (đường cũ) cũng đẩy khách vào luồng.

        17/09/2026: ĐD Huế lưu sinh hiệu cho khách "Khám Hôm Na" qua biểu mẫu
        bệnh án (bấm tên khách ở Trang chủ) — `vital_measurement` có dòng nhưng
        `encounter_flow` không biết "đã đo", không quyết tuyến, không mở phiên
        khám, nên bác sĩ và thư ký KHÔNG BAO GIỜ thấy khách trong hàng chờ.
        Chạy trong CÙNG giao dịch của lệnh lưu. Chưa có huyết áp thì chưa đủ
        điều kiện (luật I8) — để nguyên như màn Đo sinh hiệu.
        """
        cid = identity.clinic_id
        co_huyet_ap = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM vital_measurement
                 WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                   AND systolic IS NOT NULL AND diastolic IS NOT NULL)
            """,
            cid,
            visit_id,
        )
        if not co_huyet_ap:
            return None
        await khoa_luot(conn, cid, visit_id)
        flow = await khoa_flow(conn, cid, visit_id)
        if flow["vitals_status"] == "recorded":
            return str(flow["route_decision"]) if flow["route_decision"] else None
        await conn.execute(
            """
            UPDATE encounter_flow
               SET vitals_status = 'recorded',
                   content_revision = content_revision + 1,
                   version = version + 1, updated_at = now()
             WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
            """,
            cid,
            visit_id,
        )
        await record_event(
            conn,
            event_type="vitals.recorded",
            aggregate_type="visit",
            aggregate_id=visit_id,
            identity=identity,
            origin=ORIGIN,
            payload={"visit_id": visit_id, "qua": "ho_so_benh_an"},
        )
        # Sổ MỚI nữa: khối Hành trình nghe sự kiện này (sổ cũ không ai nghe).
        await emit_event(
            conn,
            ten="vitals.recorded",
            clinic_id=cid,
            aggregate_id=visit_id,
            payload=SinhHieuDaDo(visit_id=visit_id, qua_duong="ho_so_benh_an"),
            boi=nguoi(identity),
            correlation_id=visit_id,
        )
        # Xếp hàng KHÔNG làm ở đây nữa: khối Hành trình nghe sự thật (24/09).
        await cap_nhat_vi_tri(conn, cid, visit_id)
        flow_moi = await khoa_flow(conn, cid, visit_id)
        return str(flow_moi["route_decision"]) if flow_moi["route_decision"] else None

    async def record_vitals(
        self,
        *,
        visit_id: str,
        raw: Any,
        identity: StaffIdentity,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        vid = _uuid(visit_id, "Mã lượt khám không hợp lệ.")
        vitals, loi = rules.parse_vitals(raw)
        if vitals is None:
            raise ValidationError(loi or "Sinh hiệu không hợp lệ.")
        payload = {
            "visit_id": vid,
            **{k: str(v) if v is not None else None for k, v in asdict(vitals).items()},
        }
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(conn, identity, "vitals.measure")
            await khoa_luot(conn, identity.clinic_id, vid)
            cached = await bien_nhan_doc(
                conn, identity, "vitals.record", idempotency_key, payload
            )
            if cached is not None:
                return cached
            # LẦN LƯU ĐẦU PHẢI SAU [Bắt đầu] (chốt 23/09/2026). Bỏ qua được thì
            # lại có lượt "đã đo" mà không biết bắt đầu lúc nào — đúng cái lỗ
            # StartVitals sinh ra để bịt. KHÔNG tự bắt đầu thay người dùng:
            # `vitals_started_at` khi ấy sẽ là giờ LƯU, sai nghĩa.
            # Kiểm SAU khoá encounter_flow nên không có kẽ tranh chấp.
            # Đã `recorded` → lưu thêm vẫn được. Người bắt đầu và người lưu
            # được phép khác nhau (bàn giao giữa hai điều dưỡng).
            flow = await khoa_flow(conn, identity.clinic_id, vid)
            if flow["vitals_status"] == "pending":
                raise LuotKhamConflictError(
                    "VITALS_NOT_STARTED",
                    "Bấm [Bắt đầu] trước khi lưu sinh hiệu.",
                )
            co_thai = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1 FROM pregnancy p JOIN visit v
                      ON v.clinic_id = p.clinic_id
                     AND v.clinic_patient_id = p.clinic_patient_id
                   WHERE v.clinic_id = $1::uuid AND v.visit_id = $2::uuid
                     AND coalesce(p.outcome, 'ONGOING') = 'ONGOING')
                """,
                identity.clinic_id,
                vid,
            )
            loi_thai = rules.thieu_sinh_hieu_khi_co_thai(vitals, co_thai=bool(co_thai))
            if loi_thai:
                raise ValidationError(loi_thai)
            await conn.execute(
                """
                INSERT INTO vital_measurement
                    (clinic_id, visit_id, systolic, diastolic, pulse, temperature,
                     weight_kg, height_cm, respiratory_rate, spo2, bmi,
                     pain_score, recorded_by)
                VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7, $8, $9, $10,
                        $11, $12, $13::uuid)
                """,
                identity.clinic_id,
                vid,
                vitals.systolic,
                vitals.diastolic,
                vitals.pulse,
                vitals.temperature,
                vitals.weight_kg,
                vitals.height_cm,
                vitals.respiratory_rate,
                vitals.spo2,
                vitals.bmi,
                vitals.pain_score,
                identity.staff_id,
            )
            await conn.execute(
                """
                UPDATE encounter_flow
                   SET vitals_status = 'recorded',
                       content_revision = content_revision + 1,
                       version = version + 1, updated_at = now()
                 WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                """,
                identity.clinic_id,
                vid,
            )
            await record_event(
                conn,
                event_type="vitals.recorded",
                aggregate_type="visit",
                aggregate_id=vid,
                identity=identity,
                origin=ORIGIN,
                payload={"visit_id": vid},
            )
            # Sự kiện nghiệp vụ, CÙNG giao dịch với việc ghi sinh hiệu. Payload
            # KHÔNG mang chỉ số: huyết áp là dữ liệu lâm sàng, còn sổ sự kiện
            # thì không xoá được.
            await emit_event(
                conn,
                ten="vitals.recorded",
                clinic_id=identity.clinic_id,
                aggregate_id=vid,
                payload=SinhHieuDaDo(visit_id=vid),
                boi=nguoi(identity),
                correlation_id=vid,
            )
            # Xếp hàng do khối Hành trình (nghe `vitals.recorded`), không gọi
            # thẳng ở đây nữa (chuẩn lego, 24/09/2026).
            await cap_nhat_vi_tri(conn, identity.clinic_id, vid)
            flow_moi = await khoa_flow(conn, identity.clinic_id, vid)
            route = flow_moi["route_decision"]
            result = {"ok": True, "visit_id": vid, "route": route}
            await bien_nhan_ghi(
                conn, identity, "vitals.record", idempotency_key, payload, vid, result
            )
        return result
