"""Luồng khám lát 1 — lệnh và bảng làm việc.

Contract: demo-clinicai/docs/handoff/DANH-GIA-THIET-KE-CLAUDE-20260911-v2.md §3.

Luật QUYẾT nằm ở ``luot_kham_rules`` (thuần, test không cần database). File này
đọc, khoá, gọi luật, rồi ghi. Mỗi lệnh chạy trong MỘT transaction và khoá dòng
``visit`` đầu tiên: hai lệnh trên cùng một lượt khám luôn chạy nối tiếp, và thứ
tự khoá cố định (visit → dòng của lệnh) nên không có deadlock chéo.

BIÊN NHẬN NẰM TRONG CÙNG TRANSACTION. Khoá gửi lại (Idempotency-Key) được giữ
bằng advisory lock theo (phòng khám, người gọi, lệnh, khoá), đọc biên nhận, làm
việc, ghi biên nhận, commit — tất cả một lần. Chết giữa chừng thì cả việc lẫn
biên nhận cùng mất; gửi lại thì làm lại từ đầu, không có khoảng hở "đã commit
mà chưa lưu biên nhận" như ``api/idempotency.py`` (S6).

GIỚI HẠN CỦA LÁT 1, nói rõ:
  * Chưa có kết quả theo phiên bản, nên yêu cầu "có kết quả hợp lệ" bị từ chối
    thay vì để vòng đọc kẹt mãi — chỉ nhận "đã làm".
  * Chưa có nhánh kế hoạch trước, huỷ/miễn yêu cầu, rời tạm.
"""

from __future__ import annotations

from typing import Any

import asyncpg
import structlog

from clinicai.api.exceptions import NotFoundError, ValidationError
from clinicai.api.identity import (
    StaffIdentity,
)
from clinicai.core.clock import CLINIC_TZ_NAME
from clinicai.core.exceptions import SafetyGateError
from clinicai.core.tran import canh_bao_neu_day
from clinicai.events.catalogue import (
    ChiDinhDaHuy,
    DaHenTaiKham,
    DaXepDuongDi,
    KetQuaDaDuyet,
    KhamXong,
    LuotDaKhamXong,
    PhienKhamBatDau,
    PhienKhamTiepTuc,
    TuVanXong,
)
from clinicai.events.emit import HE_THONG, emit_event, nguoi, nguoi_lam_thay
from clinicai.permissions.ca_truc import kiem_dung_ca
from clinicai.permissions.can import can, doi_quyen
from clinicai.services import luot_kham_rules as rules
from clinicai.services.audit import record_event
from clinicai.services.bac_si_phu_trach import (
    bac_si_cua_phien,
    bac_si_cung_phong_hom_nay,
    bac_si_trong,
    la_bac_si_khac,
)
from clinicai.services.day_noi import doc_day
from clinicai.services.doi_tac_service import DoiTacService
from clinicai.services.hang_cho import (
    cap_nhat_vi_tri,
    chan_cho_khac,
    khach_dang_duoc_phuc_vu,
    mo_cho_bi_chan,
    vao_hang,
)

# Hai lỗi có mã nay ở nền chung; xuất lại ở đây (dạng `X as X`) để nơi cũ
# `from luot_kham_service import LuotKhamConflictError` vẫn đúng.
from clinicai.services.lenh_kham_core import (
    LuotKhamConflictError as LuotKhamConflictError,
)
from clinicai.services.lenh_kham_core import (
    LuotKhamValidationError as LuotKhamValidationError,
)
from clinicai.services.lenh_kham_core import (
    bien_nhan_doc,
    bien_nhan_ghi,
    khoa_flow,
    khoa_luot,
    luot_cua,
)
from clinicai.services.lenh_kham_core import ma_uuid as _uuid
from clinicai.services.luot_kham_chung import (
    _CAU_CHAN_DIEU_PHOI as _CAU_CHAN_DIEU_PHOI,
)
from clinicai.services.luot_kham_chung import (
    _LIVE as _LIVE,
)
from clinicai.services.luot_kham_chung import (
    _TAP_NOI_DUOC as _TAP_NOI_DUOC,
)
from clinicai.services.luot_kham_chung import (
    BOARD_ROLES as BOARD_ROLES,
)
from clinicai.services.luot_kham_chung import (
    CHECKIN_ROLES as CHECKIN_ROLES,
)
from clinicai.services.luot_kham_chung import (
    CHI_DINH_CON_VIEC_GIU_LUOT_SQL as CHI_DINH_CON_VIEC_GIU_LUOT_SQL,
)
from clinicai.services.luot_kham_chung import (
    CHI_DINH_CON_VIEC_SQL as CHI_DINH_CON_VIEC_SQL,
)
from clinicai.services.luot_kham_chung import (
    CLINICAL_READ_ROLES as CLINICAL_READ_ROLES,
)
from clinicai.services.luot_kham_chung import (
    CO_KET_QUA_VONG_SQL as CO_KET_QUA_VONG_SQL,
)
from clinicai.services.luot_kham_chung import (
    CONSULT_ROLES as CONSULT_ROLES,
)
from clinicai.services.luot_kham_chung import (
    DISPATCH_ROLES as DISPATCH_ROLES,
)
from clinicai.services.luot_kham_chung import (
    DOCTOR_ROLES as DOCTOR_ROLES,
)
from clinicai.services.luot_kham_chung import (
    DRAFT_ROLES as DRAFT_ROLES,
)
from clinicai.services.luot_kham_chung import (
    HO_TRO_PHONG as HO_TRO_PHONG,
)
from clinicai.services.luot_kham_chung import (
    NOTE_ROLES as NOTE_ROLES,
)
from clinicai.services.luot_kham_chung import (
    ORIGIN as ORIGIN,
)
from clinicai.services.luot_kham_chung import (
    PERFORMER_ROLES as PERFORMER_ROLES,
)
from clinicai.services.luot_kham_chung import (
    REVIEW_ROLES as REVIEW_ROLES,
)
from clinicai.services.luot_kham_chung import (
    VITALS_ROLES as VITALS_ROLES,
)
from clinicai.services.luot_kham_chung import (
    _cung_ngay_vn as _cung_ngay_vn,
)
from clinicai.services.luot_kham_chung import (
    _iso as _iso,
)
from clinicai.services.luot_kham_chung import (
    _num as _num,
)
from clinicai.services.luot_kham_chung import (
    _require as _require,
)
from clinicai.services.luot_kham_chung import (
    _theo_luat_xep_hang as _theo_luat_xep_hang,
)
from clinicai.services.luot_kham_doc import BangLuotKham
from clinicai.services.sinh_hieu_buoi import sinh_hieu_cua_buoi
from clinicai.services.sinh_hieu_service import SinhHieuService
from clinicai.services.thu_ky_bac_si import bac_si_cua_thu_ky

logger = structlog.get_logger()

#: Lý do ghi cho chỉ định NHÁP tự huỷ khi bác sĩ bấm "Khám xong — không cần dịch
#: vụ" (hiện trên Hành trình khách / lịch sử lượt).
LY_DO_HUY_NHAP_KHI_KHAM_XONG = (
    "Nháp không được duyệt — tự huỷ khi bác sĩ bấm Khám xong, không cần dịch vụ"
)


class LuotKhamService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    # ------------------------------------------------------------------
    # Nền: khoá, biên nhận, hàng chờ, D1, D2
    # ------------------------------------------------------------------

    # Nền chung của mọi lệnh trên lượt khám — nay ở `lenh_kham_core` (bóc
    # 24/09/2026). Giữ tên cũ để lệnh trong file này đọc như trước. Khoá lượt
    # (`khoa_luot`) nói riêng câu cho INCOMPLETE (khách bỏ về giữa chừng) và
    # chặn lượt đã đóng (FINALIZED / AMENDED) — mọi lệnh ở đây đi qua nó.
    _lock_visit = staticmethod(khoa_luot)
    _lock_flow = staticmethod(khoa_flow)
    _visit_of = staticmethod(luot_cua)
    _receipt_get = staticmethod(bien_nhan_doc)
    _receipt_put = staticmethod(bien_nhan_ghi)

    # Hàng chờ — nay ở `hang_cho` (bóc 24/09/2026). Tên cũ trỏ về đó.
    _visit_busy = staticmethod(khach_dang_duoc_phuc_vu)
    _block_others = staticmethod(chan_cho_khac)
    _release_blocked = staticmethod(mo_cho_bi_chan)

    async def _enqueue(self, conn: asyncpg.Connection, **kw: Any) -> None:
        await vao_hang(conn, **kw)

    # ------------------------------------------------------------------
    # Lệnh xếp hàng — CHỈ khối Hành trình gọi (events/consumers/hanh_trinh.py)
    # ------------------------------------------------------------------
    #
    # Trước 24/09 các lệnh ghi (check-in, lưu sinh hiệu) tự gọi thẳng việc xếp
    # hàng. Nay đúng chuẩn lego (docs/CHUAN-CAM-LEGO.md): khối Hành trình nghe
    # sự thật rồi gửi các lệnh dưới. Cả ba đều CHẠY LẠI ĐƯỢC (người đưa tin giao
    # ít nhất một lần): làm rồi thì không làm lại, không sinh event thứ hai.

    async def _mo_hang_bac_si_chinh(
        self, conn: asyncpg.Connection, clinic_id: str, visit_id: str
    ) -> str:
        """Phiên khám chính + chỗ chờ bác sĩ chính. Trả mã phiên."""
        doctor_id = await conn.fetchval(
            "SELECT attending_doctor_id::text FROM visit"
            " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid",
            clinic_id,
            visit_id,
        )
        consultation_id = str(
            await conn.fetchval(
                """
                INSERT INTO consultation
                    (clinic_id, visit_id, round_no, kind, status, doctor_staff_id)
                VALUES ($1::uuid, $2::uuid, 1, 'PRIMARY', 'queued', $3::uuid)
                -- Phiên đã HUỶ (khách được đưa lại về tư vấn, 25/09) thì mở lại.
                ON CONFLICT (visit_id, round_no) DO UPDATE SET updated_at = now(),
                    status = CASE WHEN consultation.status = 'cancelled'
                                  THEN 'queued' ELSE consultation.status END
                RETURNING id::text
                """,
                clinic_id,
                visit_id,
                doctor_id,
            )
        )
        await self._enqueue(
            conn,
            clinic_id=clinic_id,
            visit_id=visit_id,
            lane="DOCTOR",
            reason="PRIMARY",
            ref_id=consultation_id,
            doctor_id=doctor_id,
        )
        return consultation_id

    async def _phat_da_xep(
        self,
        conn: asyncpg.Connection,
        *,
        clinic_id: str,
        visit_id: str,
        dich: str,
        ly_do: str,
        causation_id: str | None,
    ) -> None:
        await emit_event(
            conn,
            ten="visit.routed",
            clinic_id=clinic_id,
            aggregate_id=visit_id,
            payload=DaXepDuongDi(visit_id=visit_id, dich=dich, ly_do=ly_do),
            boi=HE_THONG,
            correlation_id=visit_id,
            causation_id=causation_id,
        )

    async def xep_sau_check_in(
        self,
        conn: asyncpg.Connection,
        *,
        clinic_id: str,
        visit_id: str,
        causation_id: str | None = None,
    ) -> str | None:
        """`RouteAfterCheckIn` — dây H1/H2: loại khám qua tư vấn → hàng TƯ VẤN;
        lịch "đi thẳng phòng" có chỉ định mang sang → thẳng DỊCH VỤ (không vào
        hàng bác sĩ nào — phòng nhận khách khi chỉ định được xếp, H4); còn lại →
        hàng bác sĩ chính. Đã có đường đi thì thôi (chạy lại được).

        Hàng tư vấn: chưa có sinh hiệu thì "chờ đo sinh hiệu" (blocked) — đo
        trước rồi mới tư vấn (Tuyền 24/09) — nhưng KHÔNG khoá: tư vấn vẫn nhận
        được sớm (xem `start_consultation`).

        Lịch đi thẳng phòng mà KHÔNG có chỉ định nào mang sang (hẹn thủ thuật
        nhưng chưa ai chỉ định cụ thể) → hàng bác sĩ chính: phải có người quyết
        làm gì, khách không được đứng im ở một đường không ai nhận.

        CÙNG BUỔI (27/09/2026, dây ``h1_cung_buoi_thang_dich_vu``): lượt thứ hai
        cùng ngày của cùng khách nhận lần đo sinh hiệu của buổi (không đo lại,
        chỗ chờ tư vấn là "chờ tư vấn" chứ không "chờ đo"); khách đã được bác sĩ
        chính khám ở lượt trước + có chỉ định mang sang → thẳng DỊCH VỤ như lịch
        đi thẳng phòng. Luật đường đi: ``rules.duong_sau_check_in``.
        """
        v = await conn.fetchrow(
            """
            SELECT v.status, coalesce(st.qua_tu_van, false) AS qua_tu_van,
                   coalesce(st.di_thang_phong, false) AS di_thang_phong,
                   EXISTS (
                       SELECT 1 FROM service_order o
                        WHERE o.clinic_id = v.clinic_id AND o.visit_id = v.visit_id
                          AND o.mang_tu_visit_id IS NOT NULL
                          AND o.exec_status <> 'cancelled') AS co_mang_sang,
                   -- KHÁCH QUEN của bác sĩ chính (Tuyền 24/09/2026: "người quen
                   -- bác sĩ chính vào thẳng bác sĩ chính luôn"): lịch đánh dấu
                   -- tái khám, lịch nối từ lượt trước, hoặc đã từng được CHÍNH
                   -- bác sĩ này khám xong ở một lượt khác.
                   (coalesce(a.patient_kind, '') = 'RETURN'
                    OR a.lich_truoc_id IS NOT NULL
                    OR EXISTS (
                        SELECT 1 FROM visit v2
                          JOIN consultation c
                            ON c.visit_id = v2.visit_id AND c.clinic_id = v2.clinic_id
                         WHERE v2.clinic_id = v.clinic_id
                           AND v2.clinic_patient_id = v.clinic_patient_id
                           AND v2.visit_id <> v.visit_id
                           AND c.kind = 'PRIMARY' AND c.status = 'completed'
                           AND c.doctor_staff_id = v.attending_doctor_id))
                     AS khach_quen
              FROM visit v
              LEFT JOIN service_type st ON st.id = v.service_type_id
              LEFT JOIN appointment a
                ON a.id = v.appointment_id AND a.clinic_id = v.clinic_id
             WHERE v.clinic_id = $1::uuid AND v.visit_id = $2::uuid
               FOR UPDATE OF v
            """,
            clinic_id,
            visit_id,
        )
        if v is None or v["status"] not in ("OPEN", "IN_PROGRESS"):
            return None
        flow = await self._lock_flow(conn, clinic_id, visit_id)
        if flow["route_decision"] is not None:
            return None
        quen_vao_thang = bool(
            v["qua_tu_van"]
            and v["khach_quen"]
            and await doc_day(conn, clinic_id, "h1_khach_quen_vao_thang_bs")
        )
        # CÙNG BUỔI (27/09/2026, đợt 3 — dây RIÊNG, không dính khách quen):
        # khách check-in thêm lượt trong ngày thì không đo lại sinh hiệu, và đã
        # được khám + có chỉ định mang sang thì đi thẳng phòng dịch vụ.
        cung_buoi_da_kham = False
        if await doc_day(conn, clinic_id, "h1_cung_buoi_thang_dich_vu"):
            da_do = await self._nhan_sinh_hieu_cua_buoi(
                conn, clinic_id, visit_id, flow["vitals_status"]
            )
            if da_do:
                flow = await self._lock_flow(conn, clinic_id, visit_id)
            cung_buoi_da_kham = bool(
                await conn.fetchval(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM visit v
                          JOIN visit x
                            ON x.clinic_id = v.clinic_id
                           AND x.clinic_patient_id = v.clinic_patient_id
                           AND x.visit_id <> v.visit_id
                          JOIN consultation c
                            ON c.clinic_id = x.clinic_id AND c.visit_id = x.visit_id
                         WHERE v.clinic_id = $1::uuid AND v.visit_id = $2::uuid
                           AND c.kind = 'PRIMARY'
                           AND c.status IN ('in_progress', 'completed')
                           AND coalesce(x.checked_in_at, x.created_at)
                               < coalesce(v.checked_in_at, v.created_at)
                           AND (coalesce(x.checked_in_at, x.created_at)
                                AT TIME ZONE $3)::date
                               = (coalesce(v.checked_in_at, v.created_at)
                                  AT TIME ZONE $3)::date)
                    """,
                    clinic_id,
                    visit_id,
                    CLINIC_TZ_NAME,
                )
            )
        dich, ly_do = rules.duong_sau_check_in(
            qua_tu_van=bool(v["qua_tu_van"]),
            di_thang_phong=bool(v["di_thang_phong"]),
            cung_buoi_da_kham=cung_buoi_da_kham,
            co_mang_sang=bool(v["co_mang_sang"]),
            quen_vao_thang=quen_vao_thang,
        )
        if dich == rules.SERVICES:
            # Không vào hàng bác sĩ nào — phòng nhận khách khi chỉ định được
            # xếp (H4: đã trả thì xếp ngay trong cùng lần giao tin).
            pass
        elif dich == rules.TU_VAN:
            con_id = await conn.fetchval(
                """
                INSERT INTO consultation
                    (clinic_id, visit_id, round_no, kind, status)
                VALUES ($1::uuid, $2::uuid, 0, 'TU_VAN', 'queued')
                -- Phiên đã HUỶ (vd đổi dịch vụ khám sang loại không qua tư vấn
                -- rồi đổi lại — V5 30/09) thì mở lại, như phiên bác sĩ chính.
                ON CONFLICT (visit_id, round_no) DO UPDATE SET updated_at = now(),
                    status = CASE WHEN consultation.status = 'cancelled'
                                  THEN 'queued' ELSE consultation.status END
                RETURNING id::text
                """,
                clinic_id,
                visit_id,
            )
            da_do = flow["vitals_status"] == "recorded"
            await conn.execute(
                """
                INSERT INTO queue_entry
                    (clinic_id, visit_id, lane, reason, ref_id, status, eligible_at)
                VALUES ($1::uuid, $2::uuid, 'TU_VAN', 'TU_VAN', $3::uuid, $4,
                        CASE WHEN $4 = 'waiting' THEN now() END)
                ON CONFLICT (visit_id, reason, ref_id)
                    WHERE status NOT IN ('done', 'left', 'cancelled')
                DO NOTHING
                """,
                clinic_id,
                visit_id,
                con_id,
                "waiting" if da_do else "blocked",
            )
        else:
            await self._mo_hang_bac_si_chinh(conn, clinic_id, visit_id)
        await conn.execute(
            """
            UPDATE encounter_flow
               SET route_decision = $3, route_decided_at = now(), route_reason = $4,
                   version = version + 1, updated_at = now()
             WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
               AND route_decision IS NULL
            """,
            clinic_id,
            visit_id,
            dich,
            ly_do,
        )
        await self._phat_da_xep(
            conn,
            clinic_id=clinic_id,
            visit_id=visit_id,
            dich=dich,
            ly_do=ly_do,
            causation_id=causation_id,
        )
        # CON TRỎ "khách đang ở đâu" rời quầy Đo chỉ số (check-in đặt ở trạm
        # đầu, `place_visit_at_first_station`) khi lượt KHÔNG cần đo: buổi đã
        # đo, hay đi thẳng dịch vụ. Lượt chưa đo mà vào hàng bác sĩ chính thì
        # giữ như cũ — khách vẫn qua điều dưỡng trước (luồng chuẩn, không khoá).
        # Chưa có chỗ chờ nào (dịch vụ chưa trả, chưa xếp phòng) thì để nguyên:
        # `cap_nhat_vi_tri` sẽ hiểu "hết chỗ" là bước đóng lượt ở quầy — sai.
        if (flow["vitals_status"] == "recorded" or dich == rules.SERVICES) and (
            await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM queue_entry WHERE clinic_id = $1::uuid"
                " AND visit_id = $2::uuid AND status NOT IN"
                " ('done', 'left', 'cancelled'))",
                clinic_id,
                visit_id,
            )
        ):
            await cap_nhat_vi_tri(conn, clinic_id, visit_id)
        return dich

    @staticmethod
    async def _nhan_sinh_hieu_cua_buoi(
        conn: asyncpg.Connection,
        clinic_id: str,
        visit_id: str,
        vitals_status: str,
    ) -> bool:
        """Lượt chưa đo mà BUỔI đã đo (lượt khác cùng khách, cùng ngày) → coi
        như đã đo: ``vitals_status = 'recorded'`` + ghi lượt nguồn. KHÔNG chép
        số đo. Trả True khi vừa nhận.

        Khách đang có thai mà lần đo của buổi thiếu cân nặng/chiều cao → không
        nhận (lượt vẫn chờ đo, cùng luật lưu sinh hiệu). Chạy lại: đã
        ``recorded`` / ``in_progress`` thì thôi.
        """
        if vitals_status != "pending":
            return False
        do = await sinh_hieu_cua_buoi(conn, clinic_id, visit_id)
        if do is None or do["nguon_visit_id"] == str(visit_id):
            return False
        co_thai = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM pregnancy p JOIN visit v
                  ON v.clinic_id = p.clinic_id
                 AND v.clinic_patient_id = p.clinic_patient_id
               WHERE v.clinic_id = $1::uuid AND v.visit_id = $2::uuid
                 AND coalesce(p.outcome, 'ONGOING') = 'ONGOING')
            """,
            clinic_id,
            visit_id,
        )
        if not rules.sinh_hieu_buoi_dung_duoc(
            co_thai=bool(co_thai),
            can_nang=do["weight_kg"],
            chieu_cao=do["height_cm"],
        ):
            return False
        tag = await conn.execute(
            """
            UPDATE encounter_flow
               SET vitals_status = 'recorded', vitals_tu_visit_id = $3::uuid,
                   version = version + 1, updated_at = now()
             WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
               AND vitals_status = 'pending'
            """,
            clinic_id,
            visit_id,
            do["nguon_visit_id"],
        )
        return str(tag) != "UPDATE 0"

    @staticmethod
    async def mo_hang_tu_van(
        conn: asyncpg.Connection, *, clinic_id: str, visit_id: str
    ) -> bool:
        """`OpenIntakeQueue` — có sinh hiệu rồi: "chờ đo" → "chờ tư vấn".

        Khách đang ở phòng khác (serving) thì để nguyên — rời phòng sẽ tự mở.
        """
        tag = await conn.execute(
            """
            UPDATE queue_entry q
               SET status = 'waiting', eligible_at = now(),
                   version = version + 1, updated_at = now()
             WHERE q.clinic_id = $1::uuid AND q.visit_id = $2::uuid
               AND q.lane = 'TU_VAN' AND q.status = 'blocked'
               AND NOT EXISTS (
                   SELECT 1 FROM queue_entry s
                    WHERE s.clinic_id = $1::uuid AND s.visit_id = $2::uuid
                      AND s.status = 'serving')
            """,
            clinic_id,
            visit_id,
        )
        mo = str(tag) != "UPDATE 0"
        if mo:
            # Con trỏ rời quầy Đo chỉ số (27/09/2026): lệnh lưu sinh hiệu dời
            # con trỏ TRƯỚC khi chỗ chờ tư vấn mở (lúc ấy chỉ còn chỗ "chờ đo"
            # nên `cap_nhat_vi_tri` giữ nguyên) — trưởng ca thấy khách đã đo
            # xong vẫn "đang ở Đo chỉ số" tới khi tư vấn nhận.
            await cap_nhat_vi_tri(conn, clinic_id, visit_id)
        return mo

    async def doi_duong_tu_van(
        self, *, visit_id: str, bo_qua: bool, identity: StaffIdentity
    ) -> dict[str, Any]:
        """Ô tick "Bỏ qua bác sĩ tư vấn" ở màn đo sinh hiệu — ÁP NGAY vào vị trí
        của khách (Tuyền 25/09/2026: "là lựa chọn và áp luôn cho vị trí của
        khách"). Tick → hàng bác sĩ chính; bỏ tick → về lại hàng tư vấn.

        Chỉ đổi được khi bên nhận chưa bắt đầu: tư vấn chưa nhận khách (khi bỏ
        qua), bác sĩ chính chưa bắt đầu khám (khi đưa lại).
        """
        vid = _uuid(visit_id, "Mã lượt khám không hợp lệ.")
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(conn, identity, "vitals.measure")
            if bo_qua:
                doi = await self.bo_qua_tu_van(
                    conn, clinic_id=identity.clinic_id, visit_id=vid
                )
                loi = "Bác sĩ tư vấn đã nhận khách (hoặc lượt không qua tư vấn)."
            else:
                doi = await self.tra_ve_tu_van(
                    conn, clinic_id=identity.clinic_id, visit_id=vid
                )
                loi = "Bác sĩ chính đã bắt đầu khám — không đưa về tư vấn được."
            if not doi:
                trang_thai = await conn.fetchval(
                    "SELECT status FROM consultation WHERE clinic_id = $1::uuid"
                    " AND visit_id = $2::uuid AND kind = 'TU_VAN'",
                    identity.clinic_id,
                    vid,
                )
                # Đã đúng như tick rồi (bấm hai lần) → không phải lỗi.
                da_dung = (trang_thai == "cancelled") == bo_qua and trang_thai
                if not da_dung:
                    raise LuotKhamConflictError("TU_VAN_KHONG_DOI_DUOC", loi)
        return {"ok": True, "visit_id": vid, "bo_qua_tu_van": bo_qua}

    async def xep_lai_sau_doi_dich_vu(
        self,
        conn: asyncpg.Connection,
        *,
        clinic_id: str,
        visit_id: str,
        causation_id: str | None = None,
    ) -> str | None:
        """`RerouteAfterServiceSwitch` — đổi DỊCH VỤ KHÁM sau check-in (V5,
        30/09/2026) → tính lại hàng chờ ĐẦU TIÊN: qua tư vấn / thẳng bác sĩ
        chính / thẳng dịch vụ, bằng đúng luật H1 (`xep_sau_check_in`).

        Chỉ khi CHƯA phiên khám nào bắt đầu (mọi phiên `queued`/`cancelled`) —
        bác sĩ đã nhận khách thì để nguyên đường cũ. Lệnh đổi dịch vụ đã chặn
        trường hợp ấy; ở đây kiểm lại vì sự kiện được giao sau khi commit.

        Làm: huỷ chỗ chờ tư vấn / bác sĩ chính còn sống + các phiên đang chờ,
        xoá đường đi, rồi xếp lại. Chỗ chờ PHÒNG DỊCH VỤ (chỉ định) không đụng.
        """
        luot = await conn.fetchrow(
            "SELECT status, closed_at FROM visit WHERE clinic_id = $1::uuid"
            " AND visit_id = $2::uuid FOR UPDATE",
            clinic_id,
            visit_id,
        )
        # Đã check-out (chỉ `closed_at`, status vẫn IN_PROGRESS): khách đã về,
        # không đưa lại hàng tư vấn / bác sĩ (review 07/10/2026).
        if (
            luot is None
            or luot["status"] not in ("OPEN", "IN_PROGRESS")
            or luot["closed_at"] is not None
        ):
            return None
        if await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM consultation WHERE clinic_id = $1::uuid"
            " AND visit_id = $2::uuid AND status NOT IN ('queued', 'cancelled'))",
            clinic_id,
            visit_id,
        ):
            return None
        await conn.execute(
            """
            UPDATE queue_entry
               SET status = 'cancelled', version = version + 1, updated_at = now()
             WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
               AND reason IN ('TU_VAN', 'PRIMARY')
               AND status NOT IN ('done', 'left', 'cancelled')
            """,
            clinic_id,
            visit_id,
        )
        await conn.execute(
            "UPDATE consultation SET status = 'cancelled', version = version + 1,"
            " updated_at = now() WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
            " AND status = 'queued'",
            clinic_id,
            visit_id,
        )
        await conn.execute(
            """
            UPDATE encounter_flow
               SET route_decision = NULL, route_decided_at = NULL,
                   route_reason = NULL, version = version + 1, updated_at = now()
             WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
            """,
            clinic_id,
            visit_id,
        )
        return await self.xep_sau_check_in(
            conn, clinic_id=clinic_id, visit_id=visit_id, causation_id=causation_id
        )

    async def tra_ve_tu_van(
        self,
        conn: asyncpg.Connection,
        *,
        clinic_id: str,
        visit_id: str,
        causation_id: str | None = None,
    ) -> bool:
        """Đưa khách ĐÃ bỏ qua tư vấn về lại hàng tư vấn (bỏ tick). Chỉ khi bác
        sĩ chính CHƯA bắt đầu khám. Chạy lại được."""
        await conn.execute(
            "SELECT 1 FROM visit WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
            " FOR UPDATE",
            clinic_id,
            visit_id,
        )
        tu_van = await conn.fetchval(
            "SELECT id::text FROM consultation WHERE clinic_id = $1::uuid"
            " AND visit_id = $2::uuid AND kind = 'TU_VAN' AND status = 'cancelled'",
            clinic_id,
            visit_id,
        )
        if tu_van is None:
            return False
        if await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM consultation WHERE clinic_id = $1::uuid"
            " AND visit_id = $2::uuid AND kind = 'PRIMARY'"
            " AND status NOT IN ('queued', 'cancelled'))",
            clinic_id,
            visit_id,
        ):
            return False
        await conn.execute(
            "UPDATE consultation SET status = 'cancelled', version = version + 1,"
            " updated_at = now() WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
            " AND kind = 'PRIMARY' AND status = 'queued'",
            clinic_id,
            visit_id,
        )
        await conn.execute(
            """
            UPDATE queue_entry
               SET status = 'cancelled', version = version + 1, updated_at = now()
             WHERE clinic_id = $1::uuid AND visit_id = $2::uuid AND lane = 'DOCTOR'
               AND reason = 'PRIMARY' AND status NOT IN ('done', 'left', 'cancelled')
            """,
            clinic_id,
            visit_id,
        )
        await conn.execute(
            "UPDATE consultation SET status = 'queued', version = version + 1,"
            " updated_at = now() WHERE clinic_id = $1::uuid AND id = $2::uuid",
            clinic_id,
            tu_van,
        )
        flow = await self._lock_flow(conn, clinic_id, visit_id)
        da_do = flow["vitals_status"] == "recorded"
        await conn.execute(
            """
            INSERT INTO queue_entry
                (clinic_id, visit_id, lane, reason, ref_id, status, eligible_at)
            VALUES ($1::uuid, $2::uuid, 'TU_VAN', 'TU_VAN', $3::uuid, $4,
                    CASE WHEN $4 = 'waiting' THEN now() END)
            ON CONFLICT (visit_id, reason, ref_id)
                WHERE status NOT IN ('done', 'left', 'cancelled')
            DO NOTHING
            """,
            clinic_id,
            visit_id,
            tu_van,
            "waiting" if da_do else "blocked",
        )
        ly_do = "điều dưỡng đưa lại vào hàng tư vấn"
        await conn.execute(
            """
            UPDATE encounter_flow
               SET route_decision = 'TU_VAN', route_reason = $3,
                   version = version + 1, updated_at = now()
             WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
            """,
            clinic_id,
            visit_id,
            ly_do,
        )
        await self._phat_da_xep(
            conn,
            clinic_id=clinic_id,
            visit_id=visit_id,
            dich="TU_VAN",
            ly_do=ly_do,
            causation_id=causation_id,
        )
        return True

    async def bo_qua_tu_van(
        self,
        conn: asyncpg.Connection,
        *,
        clinic_id: str,
        visit_id: str,
        causation_id: str | None = None,
    ) -> bool:
        """`SkipIntake` — điều dưỡng tick "Bỏ qua bác sĩ tư vấn" lúc [Đo xong]
        (Tuyền 25/09/2026): khách rời hàng tư vấn, vào thẳng hàng bác sĩ chính.

        Chỉ khi phiên tư vấn CHƯA bắt đầu (`queued`). Bác sĩ tư vấn đã nhận
        khách thì để nguyên — xong tư vấn khách vẫn sang bác sĩ chính như cũ.
        Lượt không đi qua tư vấn thì không có gì để bỏ. Chạy lại được.
        """
        await conn.execute(
            "SELECT 1 FROM visit WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
            " FOR UPDATE",
            clinic_id,
            visit_id,
        )
        # Dây H1 (`visit.checked_in` → xếp đường) chạy NỀN. Check-in xong đo ngay
        # (vãng lai) thì lúc tick lượt có thể CHƯA được xếp đường — chưa có phiên
        # tư vấn nào để bỏ, tick bị từ chối và khách vẫn sang tư vấn (mô phỏng
        # 26/09/2026). Xếp ngay trong giao dịch này bằng đúng luật H1; H1 tới sau
        # thấy đã có đường thì thôi (chạy lại được).
        await self.xep_sau_check_in(
            conn, clinic_id=clinic_id, visit_id=visit_id, causation_id=causation_id
        )
        tu_van = await conn.fetchval(
            "SELECT id::text FROM consultation WHERE clinic_id = $1::uuid"
            " AND visit_id = $2::uuid AND kind = 'TU_VAN' AND status = 'queued'",
            clinic_id,
            visit_id,
        )
        if tu_van is None:
            return False
        await conn.execute(
            "UPDATE consultation SET status = 'cancelled', version = version + 1,"
            " updated_at = now() WHERE clinic_id = $1::uuid AND id = $2::uuid",
            clinic_id,
            tu_van,
        )
        await conn.execute(
            """
            UPDATE queue_entry
               SET status = 'cancelled', version = version + 1, updated_at = now()
             WHERE clinic_id = $1::uuid AND visit_id = $2::uuid AND lane = 'TU_VAN'
               AND status NOT IN ('done', 'left', 'cancelled')
            """,
            clinic_id,
            visit_id,
        )
        return await self.chuyen_bac_si_chinh(
            conn,
            clinic_id=clinic_id,
            visit_id=visit_id,
            causation_id=causation_id,
            ly_do="điều dưỡng cho bỏ qua tư vấn — vào thẳng bác sĩ chính",
        )

    async def chuyen_bac_si_chinh(
        self,
        conn: asyncpg.Connection,
        *,
        clinic_id: str,
        visit_id: str,
        causation_id: str | None = None,
        ly_do: str = "tư vấn xong — chuyển bác sĩ chính",
    ) -> bool:
        """`HandToPrimaryDoctor` — dây H3: tư vấn xong → hàng bác sĩ chính."""
        await conn.execute(
            "SELECT 1 FROM visit WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
            " FOR UPDATE",
            clinic_id,
            visit_id,
        )
        # Tin "tư vấn xong" tới SAU khi đã bấm Hoàn tác xong tư vấn (01/10/2026):
        # phiên tư vấn lại đang mở → khách còn ở bàn tư vấn, chưa sang bác sĩ.
        if await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM consultation WHERE clinic_id = $1::uuid"
            " AND visit_id = $2::uuid AND kind = 'TU_VAN'"
            " AND status IN ('queued', 'in_progress'))",
            clinic_id,
            visit_id,
        ):
            return False
        if await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM consultation WHERE clinic_id = $1::uuid"
            " AND visit_id = $2::uuid AND kind = 'PRIMARY' AND status <> 'cancelled')",
            clinic_id,
            visit_id,
        ):
            return False
        await self._mo_hang_bac_si_chinh(conn, clinic_id, visit_id)
        await conn.execute(
            """
            UPDATE encounter_flow
               SET route_decision = 'PRIMARY', route_reason = $3,
                   version = version + 1, updated_at = now()
             WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
            """,
            clinic_id,
            visit_id,
            ly_do,
        )
        await self._phat_da_xep(
            conn,
            clinic_id=clinic_id,
            visit_id=visit_id,
            dich=rules.PRIMARY,
            ly_do=ly_do,
            causation_id=causation_id,
        )
        return True

    @staticmethod
    async def _yeu_cau_cua_vong(
        conn: asyncpg.Connection, clinic_id: str, round_id: str
    ) -> list[asyncpg.Record]:
        """Yêu cầu của một vòng kèm trạng thái THỰC HIỆN và KẾT QUẢ của chỉ định.

        "Kết quả hợp lệ" (Blocker 1):
          - Đối với chỉ định làm bên ngoài (node_definition.lam_ben_ngoai = true):
            BẮT BUỘC phải có ít nhất một tệp kết quả ở trạng thái HOP_LE
            (xác nhận đúng người, đúng chỉ định bởi nhân sự có capability).
            Mốc ket_qua_luc chỉ là mốc tài liệu tới, không làm co_ket_qua = true.
          - Đối với chỉ định nội bộ: giữ nguyên quy tắc ket_qua_luc IS NOT NULL.
          - VIỆC ĐỐI TÁC ĐÃ NHẬN MẪU (Tuyền 29/09/2026): đạt luôn — kết quả về
            sau không giữ vòng. Điều kiện chung: `CO_KET_QUA_VONG_SQL`.
        """
        return list(
            await conn.fetch(
                """
                SELECT q.id::text AS id, q.service_order_id::text AS order_id,
                       q.need, q.status, o.exec_status, o.selection_status,
                       """
                + CO_KET_QUA_VONG_SQL
                + """ AS co_ket_qua,
                       coalesce((SELECT x.noi_lam = 'BAN_KHAM'
                                   FROM service_execution_attempt x
                                  WHERE x.clinic_id = o.clinic_id
                                    AND x.service_order_id = o.id
                                  ORDER BY x.attempt_no DESC LIMIT 1), false)
                         AS lam_tai_ban_kham
                  FROM round_requirement q
                  JOIN service_order o
                    ON o.id = q.service_order_id AND o.clinic_id = q.clinic_id
                  LEFT JOIN node_definition nd
                    ON nd.clinic_id = o.clinic_id AND nd.code = o.node_code
                 WHERE q.clinic_id = $1::uuid AND q.round_id = $2::uuid
                 ORDER BY q.created_at, q.id
                """,
                clinic_id,
                round_id,
            )
        )

    @staticmethod
    def _view(q: asyncpg.Record) -> rules.RequirementView:
        return rules.RequirementView(
            q["order_id"],
            q["need"],
            q["status"],
            q["exec_status"],
            q["co_ket_qua"],
            # Không phải câu đọc nào cũng mang cột này (vd /cho-quyet) — thiếu
            # thì coi như chưa biết, không làm sập cả màn.
            q.get("selection_status"),
            bool(q.get("lam_tai_ban_kham") or False),
        )

    async def _evaluate_rounds(
        self, conn: asyncpg.Connection, identity: StaffIdentity, visit_id: str
    ) -> None:
        """D2 — vòng đọc nào vừa đủ điều kiện thì mở phiên và chỗ chờ, đúng MỘT.

        Vòng mà mọi yêu cầu đều đã được bác sĩ miễn hoặc chuyển theo dõi thì
        KHÔNG cần đọc: đóng luôn, không gọi khách về bác sĩ (FOLLOW_UP không giữ
        lượt chờ). Vòng đang đọc (``in_review``) không bị đụng.
        """
        cid = identity.clinic_id
        rounds = await conn.fetch(
            """
            SELECT id::text AS id, round_no, status
              FROM review_round
             WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
               AND status IN ('collecting', 'ready')
             ORDER BY round_no
               FOR UPDATE
            """,
            cid,
            visit_id,
        )
        for rd in rounds:
            views = []
            for q in await self._yeu_cau_cua_vong(conn, cid, rd["id"]):
                view = self._view(q)
                if q["status"] in ("open", "satisfied"):
                    target = (
                        "satisfied"
                        if rules.requirement_state(view) == "satisfied"
                        else "open"
                    )
                    if target != q["status"]:
                        await conn.execute(
                            "UPDATE round_requirement SET status = $3, updated_at ="
                            " now()"
                            " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                            cid,
                            q["id"],
                            target,
                        )
                views.append(view)
            # VÒNG RỖNG (C18, I3, 02/10/2026): huỷ chỉ định cuối cùng sau "Khám
            # xong" xoá hết yêu cầu của vòng chưa đóng — vòng không còn gì để
            # đọc thì ĐÓNG, không treo "đang thu" mãi (tập rỗng vẫn không bao
            # giờ "sẵn sàng", I5: không tự sinh lần gọi bác sĩ không ai cần).
            vong_rong = not views
            if vong_rong or rules.vong_khong_can_doc(views):
                await conn.execute(
                    "UPDATE review_round SET status = 'closed', closed_at = now(),"
                    " version = version + 1, updated_at = now()"
                    " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                    cid,
                    rd["id"],
                )
                # Vòng đã "sẵn sàng" (khách đang chờ bác sĩ đọc) mà bác sĩ vừa
                # chuyển hết sang theo dõi: bỏ phiên đọc và chỗ chờ của nó.
                await conn.execute(
                    """
                    WITH c AS (
                        UPDATE consultation
                           SET status = 'cancelled', version = version + 1,
                               updated_at = now()
                         WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                           AND round_no = $3 AND status = 'queued'
                        RETURNING id
                    )
                    UPDATE queue_entry q
                       SET status = 'cancelled', updated_at = now(),
                           version = q.version + 1
                      FROM c
                     WHERE q.clinic_id = $1::uuid AND q.ref_id = c.id
                       AND q.reason = 'REVIEW'
                       AND q.status NOT IN ('done', 'left', 'cancelled')
                    """,
                    cid,
                    visit_id,
                    rd["round_no"],
                )
                await record_event(
                    conn,
                    event_type="review.skipped",
                    aggregate_type="visit",
                    aggregate_id=visit_id,
                    identity=identity,
                    origin=ORIGIN,
                    payload={
                        "visit_id": visit_id,
                        "round_no": rd["round_no"],
                        **({"ly_do": "vong_rong"} if vong_rong else {}),
                        # Bác sĩ tự làm tại bàn khám — không có gì để đọc lại.
                        **(
                            {"ly_do": "lam_tai_ban_kham"}
                            if any(v.lam_tai_ban_kham for v in views)
                            else {}
                        ),
                    },
                )
                continue
            ready = rules.round_ready(views)
            if ready and rd["status"] == "collecting":
                await conn.execute(
                    "UPDATE review_round SET status = 'ready', ready_at = now(),"
                    " version = version + 1, updated_at = now()"
                    " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                    cid,
                    rd["id"],
                )
                doctor = await conn.fetchval(
                    """
                    SELECT coalesce(
                        (SELECT c.doctor_staff_id FROM consultation c
                          WHERE c.clinic_id = $1::uuid AND c.visit_id = $2::uuid
                            AND c.round_no = 1),
                        (SELECT v.attending_doctor_id FROM visit v
                          WHERE v.clinic_id = $1::uuid AND v.visit_id = $2::uuid))::text
                    """,
                    cid,
                    visit_id,
                )
                consultation_id = await conn.fetchval(
                    """
                    INSERT INTO consultation
                        (clinic_id, visit_id, round_no, kind, status, doctor_staff_id)
                    VALUES ($1::uuid, $2::uuid, $3, 'REVIEW', 'queued', $4::uuid)
                    -- Phiên đọc đã HUỶ (hoàn tác khám xong 01/10/2026 bỏ vòng
                    -- đọc chưa ai nhận) thì mở lại — không để chỗ chờ trỏ vào
                    -- một phiên đã huỷ, bác sĩ bấm Bắt đầu sẽ bị từ chối.
                    ON CONFLICT (visit_id, round_no) DO UPDATE SET updated_at = now(),
                        status = CASE WHEN consultation.status = 'cancelled'
                                      THEN 'queued' ELSE consultation.status END
                    RETURNING id::text
                    """,
                    cid,
                    visit_id,
                    rd["round_no"],
                    doctor,
                )
                await self._enqueue(
                    conn,
                    clinic_id=cid,
                    visit_id=visit_id,
                    lane="DOCTOR",
                    reason="REVIEW",
                    ref_id=str(consultation_id),
                    doctor_id=doctor,
                )
                await record_event(
                    conn,
                    event_type="review.ready",
                    aggregate_type="visit",
                    aggregate_id=visit_id,
                    identity=identity,
                    origin=ORIGIN,
                    payload={"visit_id": visit_id, "round_no": rd["round_no"]},
                )
            elif not ready and rd["status"] == "ready":
                # Lùi trước khi bác sĩ bắt đầu: huỷ chỗ chờ (không để "blocked",
                # vì blocked nghĩa là "khách đang ở phòng khác" và sẽ tự mở).
                await conn.execute(
                    "UPDATE review_round SET status = 'collecting', ready_at = NULL,"
                    " version = version + 1, updated_at = now()"
                    " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                    cid,
                    rd["id"],
                )
                await conn.execute(
                    """
                    UPDATE queue_entry q
                       SET status = 'cancelled', updated_at = now(),
                          version = q.version + 1
                      FROM consultation c
                     WHERE q.clinic_id = $1::uuid AND q.visit_id = $2::uuid
                       AND c.clinic_id = $1::uuid AND c.visit_id = $2::uuid
                       AND c.round_no = $3 AND q.ref_id = c.id
                       AND q.reason = 'REVIEW'
                       AND q.status IN ('waiting', 'called', 'blocked')
                    """,
                    cid,
                    visit_id,
                    rd["round_no"],
                )
                await record_event(
                    conn,
                    event_type="review.not_ready",
                    aggregate_type="visit",
                    aggregate_id=visit_id,
                    identity=identity,
                    origin=ORIGIN,
                    payload={"visit_id": visit_id, "round_no": rd["round_no"]},
                )

    async def _ket_thuc_neu_xong(
        self,
        conn: asyncpg.Connection,
        identity: StaffIdentity,
        vid: str,
        *,
        causation_id: str | None = None,
    ) -> bool:
        """Khép phần khám của lượt khi rail mới nói không còn gì phải chờ.

        Một chỗ cho mọi lối khép (Slice 1). Trước đây chỉ bấm "khám xong" với
        kết quả NO_SERVICES/DONE mới khép, nên hai ca kẹt thật:
          * bác sĩ đọc xong (DONE) khi còn một chỉ định chưa làm — chỉ định ấy
            làm xong sau đó thì không ai khép lượt, quầy thu tiền chờ mãi;
          * mọi dịch vụ chuyển theo dõi (không mở vòng đọc) — không có phiên
            nào kết thúc bằng DONE nữa.

        Điều kiện: đã có ít nhất một phiên khám xong; không phiên nào đang chờ
        hay đang khám; không vòng đọc nào còn mở; không chỉ định đã duyệt nào
        còn chưa làm (việc của ĐỐI TÁC không tính — nút của họ chỉ ghi sự kiện,
        28/09/2026). Việc theo dõi (follow_up_case) KHÔNG giữ lượt lại.

        Khép = ``encounter_flow.finished_at`` + lịch hẹn COMPLETED +
        ``visit.exam_completed_at`` (quầy thu tiền và bước đóng lượt đợi mốc
        này). Gọi lại bao nhiêu lần cũng vậy.
        """
        cid = identity.clinic_id
        xong = await conn.fetchval(
            """
            SELECT EXISTS (SELECT 1 FROM consultation c
                            WHERE c.clinic_id = $1::uuid AND c.visit_id = $2::uuid
                              AND c.status = 'completed')
               AND NOT EXISTS (SELECT 1 FROM consultation c
                                WHERE c.clinic_id = $1::uuid AND c.visit_id = $2::uuid
                                  AND c.status IN ('queued', 'in_progress'))
               AND NOT EXISTS (SELECT 1 FROM review_round r
                                WHERE r.clinic_id = $1::uuid AND r.visit_id = $2::uuid
                                  AND r.status <> 'closed')
               AND NOT EXISTS (SELECT 1 FROM service_order o
                                WHERE o.clinic_id = $1::uuid AND o.visit_id = $2::uuid
                                  AND """
            + CHI_DINH_CON_VIEC_GIU_LUOT_SQL
            + """)
            """,
            cid,
            vid,
        )
        if not xong:
            return False
        await conn.execute(
            """
            UPDATE encounter_flow f
               SET finished_at = now(), version = f.version + 1, updated_at = now()
             WHERE f.clinic_id = $1::uuid AND f.visit_id = $2::uuid
               AND f.finished_at IS NULL
            """,
            cid,
            vid,
        )
        # BÁC SĨ KHÁM XONG HẲN = lịch hẹn COMPLETED (demo 17/09/2026). Quầy thu
        # tiền và bước đóng lượt đều đợi mốc này.
        hen = await conn.fetchval(
            """
            UPDATE appointment a
               SET status = 'COMPLETED', updated_at = now()
              FROM visit v
             WHERE v.clinic_id = $1::uuid AND v.visit_id = $2::uuid
               AND a.id = v.appointment_id AND a.clinic_id = v.clinic_id
               AND a.status = 'CHECKED_IN'
            RETURNING a.id::text
            """,
            cid,
            vid,
        )
        vua_khep = await conn.execute(
            "UPDATE visit SET exam_completed_at = coalesce("
            "exam_completed_at, now()), updated_at = now()"
            " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
            " AND exam_completed_at IS NULL",
            cid,
            vid,
        )
        if vua_khep == "UPDATE 1":
            # Mốc "khám xong hẳn" — phát ĐÚNG MỘT LẦN, lúc lượt thật sự khép.
            # Quầy / nhà thuốc / nhắc check-out cắm vào đây thay vì tự dò.
            await emit_event(
                conn,
                ten="visit.exam_completed",
                clinic_id=cid,
                aggregate_id=vid,
                payload=LuotDaKhamXong(visit_id=vid),
                boi=nguoi(identity),
                correlation_id=vid,
                causation_id=causation_id,
            )
        if hen:
            await record_event(
                conn,
                event_type="appointment.completed",
                aggregate_type="appointment",
                aggregate_id=hen,
                identity=identity,
                origin=ORIGIN,
                payload={"visit_id": vid, "boi": "luot_kham.kham_xong"},
            )
        return True

    async def _mo_theo_doi(
        self,
        conn: asyncpg.Connection,
        identity: StaffIdentity,
        *,
        vid: str,
        oid: str,
        cau_hinh: dict[str, Any],
        bac_si: str | None,
    ) -> str:
        """Mở (hoặc lấy lại) việc theo dõi ĐANG MỞ của một chỉ định.

        Người phụ trách mặc định là bác sĩ của phiên (người đọc kết quả); hạn
        mặc định theo luật CSKH ``CHO_KQ_XN`` (hiện 3 ngày). Mỗi chỉ định một
        việc đang mở — bấm lại trả về đúng việc cũ.
        """
        cid = identity.clinic_id
        co_san = await conn.fetchval(
            "SELECT id::text FROM follow_up_case WHERE clinic_id = $1::uuid"
            " AND service_order_id = $2::uuid AND status = 'OPEN'",
            cid,
            oid,
        )
        if co_san:
            return str(co_san)
        chu = cau_hinh.get("owner_id") or bac_si or identity.staff_id
        chu = _uuid(chu, "Người phụ trách theo dõi không hợp lệ.")
        la_nhan_vien = await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM clinic_membership WHERE clinic_id ="
            " $1::uuid AND staff_id = $2::uuid AND is_active)",
            cid,
            chu,
        )
        if not la_nhan_vien:
            raise ValidationError("Người phụ trách theo dõi không thuộc phòng khám.")
        han = rules.doc_han_theo_doi(cau_hinh.get("han"))
        ly_do_raw = cau_hinh.get("ly_do")
        ly_do = ly_do_raw.strip() if isinstance(ly_do_raw, str) else ""
        o = await conn.fetchrow(
            """
            SELECT o.service_name, v.clinic_patient_id::text AS patient_id
              FROM service_order o
              JOIN visit v ON v.visit_id = o.visit_id AND v.clinic_id = o.clinic_id
             WHERE o.clinic_id = $1::uuid AND o.id = $2::uuid
            """,
            cid,
            oid,
        )
        assert o is not None
        fid = await conn.fetchval(
            """
            INSERT INTO follow_up_case
                (clinic_id, clinic_patient_id, visit_id, service_order_id, reason,
                 owner_staff_id, owner_role, due_at, created_by)
            VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5, $6::uuid,
                    (SELECT m.role FROM clinic_membership m
                      WHERE m.clinic_id = $1::uuid AND m.staff_id = $6::uuid
                        AND m.is_active ORDER BY m.role LIMIT 1),
                    coalesce($7::date,
                             (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                             + coalesce((SELECT l.so_ngay FROM luat_cskh l
                                          WHERE l.clinic_id = $1::uuid
                                            AND l.loai_viec = 'CHO_KQ_XN'
                                          LIMIT 1), 3))
                        ::timestamp AT TIME ZONE 'Asia/Ho_Chi_Minh',
                    $8::uuid)
            RETURNING id::text
            """,
            cid,
            o["patient_id"],
            vid,
            oid,
            ly_do or f"Chờ kết quả {o['service_name']}",
            chu,
            han,
            identity.staff_id,
        )
        await record_event(
            conn,
            event_type="follow_up.opened",
            aggregate_type="visit",
            aggregate_id=vid,
            identity=identity,
            origin=ORIGIN,
            payload={
                "visit_id": vid,
                "order_id": oid,
                "follow_up_case_id": fid,
                "owner_staff_id": chu,
                # Lý do nằm ở follow_up_case.reason — nhật ký chỉ giữ mã,
                # không giữ chữ (audit.py: "never clinical text").
            },
        )
        return str(fid)

    async def _services(
        self,
        conn: asyncpg.Connection,
        clinic_id: str,
        codes: list[str],
        *,
        visit_id: str | None = None,
    ) -> list[asyncpg.Record]:
        """Dịch vụ để chỉ định. Có `visit_id` → chặn chỉ định lại dịch vụ đang
        tính ở "Dịch vụ khám" của lượt (tiền khám không tính hai lần, C21)."""
        from clinicai.services.phi_kham_service import chan_trung_dich_vu_kham

        wanted = [c.strip() for c in codes if isinstance(c, str) and c.strip()]
        if not wanted:
            raise ValidationError("Chưa chọn dịch vụ nào.")
        if visit_id is not None:
            await chan_trung_dich_vu_kham(conn, clinic_id, visit_id, ma_chi_dinh=wanted)
        rows = await conn.fetch(
            """
            SELECT DISTINCT ON (s.service_code)
                   s.service_code, s.name, s.node_code
              FROM service_price s
             WHERE s.clinic_id = $1::uuid AND s.active
               AND s.service_code = ANY($2::text[])
             ORDER BY s.service_code, (s."group" = 'dich_vu') DESC
            """,
            clinic_id,
            wanted,
        )
        found = {r["service_code"]: r for r in rows}
        missing = [c for c in wanted if c not in found]
        if missing:
            raise ValidationError("Không có dịch vụ: " + ", ".join(missing) + ".")
        unmapped = [found[c]["name"] for c in wanted if not found[c]["node_code"]]
        if unmapped:
            raise LuotKhamConflictError(
                "SERVICE_NOT_MAPPED",
                "Dịch vụ chưa gắn với bước thực hiện: " + ", ".join(unmapped) + ".",
            )
        return [found[c] for c in wanted]

    async def _cap_nhat_vi_tri(
        self, conn: asyncpg.Connection, cid: str, vid: str
    ) -> None:
        await cap_nhat_vi_tri(conn, cid, vid)

    async def _thu_ky_cua_bac_si(
        self,
        conn: asyncpg.Connection,
        identity: StaffIdentity,
        doctor_id: str | None,
    ) -> None:
        """Thư ký chỉ bấm được cho khách của bác sĩ mình đi kèm.

        Theo DỮ LIỆU phân công (`thu_ky_bac_si`), không theo vai (27/09 đợt 3)."""
        ds = await bac_si_cua_thu_ky(conn, identity)
        if ds is not None and (doctor_id is None or doctor_id not in ds):
            raise SafetyGateError(
                "Khách này của bác sĩ khác — thư ký chỉ làm cho bác sĩ mình đi kèm."
            )

    async def _bac_si_du_kien(
        self, conn: asyncpg.Connection, identity: StaffIdentity, con_id: str
    ) -> str | None:
        """Bác sĩ cho một phiên CHƯA ghi bác sĩ: người bấm là bác sĩ thật có
        quyền Hoàn tất khám → chính họ; không thì `bac_si_cua_phien`."""
        if await can(conn, identity, "clinical.consult.finalize") and (
            await bac_si_trong(conn, identity.clinic_id, [identity.staff_id])
        ):
            return identity.staff_id
        return await bac_si_cua_phien(
            conn,
            clinic_id=identity.clinic_id,
            consultation_id=con_id,
            nguoi_bam=identity.staff_id,
        )

    async def _gan_bac_si_phien(
        self,
        conn: asyncpg.Connection,
        cid: str,
        vid: str,
        con_id: str,
        kind: str,
        bac_si: str,
    ) -> None:
        """Ghi bác sĩ vào CHỖ CÒN TRỐNG: phiên, chỗ chờ của phiên, bác sĩ chính
        của lượt (trừ phiên tư vấn — bác sĩ tư vấn chưa chắc là bác sĩ chính).
        Không đè bác sĩ đã ghi (đổi bác sĩ là `doi_bac_si_service`)."""
        await conn.execute(
            "UPDATE consultation SET doctor_staff_id = $3::uuid,"
            " version = version + 1, updated_at = now()"
            " WHERE clinic_id = $1::uuid AND id = $2::uuid"
            " AND doctor_staff_id IS NULL",
            cid,
            con_id,
            bac_si,
        )
        await conn.execute(
            "UPDATE queue_entry SET doctor_staff_id = $3::uuid,"
            " version = version + 1, updated_at = now()"
            " WHERE clinic_id = $1::uuid AND ref_id = $2::uuid"
            " AND reason <> 'SERVICE' AND doctor_staff_id IS NULL"
            " AND status NOT IN ('done', 'left', 'cancelled')",
            cid,
            con_id,
            bac_si,
        )
        if kind != "TU_VAN":
            await conn.execute(
                "UPDATE visit SET attending_doctor_id = $3::uuid, updated_at = now()"
                " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
                " AND attending_doctor_id IS NULL",
                cid,
                vid,
                bac_si,
            )

    async def _cung_ekip(
        self,
        conn: asyncpg.Connection,
        identity: StaffIdentity,
        c: asyncpg.Record | dict[str, Any],
    ) -> bool:
        """Người gọi làm tiếp được phiên ĐANG MỞ này (người khác đã bấm Bắt đầu).

        Tuyền chốt 29/09/2026 — trợ lý TRỌN QUYỀN: ai có quyền Khám (lego Bàn
        khám hoặc lịch hôm nay) làm tiếp được phiên bác sĩ đang mở. Chỉ còn chặn:
          * thư ký ĐÃ được phân theo bác sĩ → đúng bác sĩ ấy (dữ liệu phân công);
          * HAI BÁC SĨ THẬT khác nhau giành một phiên (`bac_si_phu_trach`).
        Trước đây "bác sĩ" = có quyền Hoàn tất khám, nên thư ký / điều dưỡng có
        lego Bàn khám bấm tiếp phiên của bác sĩ bị báo CONSULTATION_TAKEN."""
        ds = await bac_si_cua_thu_ky(conn, identity)
        if ds is not None:
            return c["doctor_id"] in ds
        if not await can(conn, identity, "clinical.consult.perform"):
            return False
        return not await la_bac_si_khac(
            conn, identity.clinic_id, identity.staff_id, c["doctor_id"]
        )

    async def _consultation_in_progress(
        self, conn: asyncpg.Connection, clinic_id: str, consultation_id: str
    ) -> asyncpg.Record:
        c = await conn.fetchrow(
            """
            SELECT id::text AS id, visit_id::text AS visit_id, round_no, kind,
                   status, started_by::text AS started_by,
                   doctor_staff_id::text AS doctor_id
              FROM consultation
             WHERE clinic_id = $1::uuid AND id = $2::uuid
               FOR UPDATE
            """,
            clinic_id,
            consultation_id,
        )
        if c is None:
            raise NotFoundError("Không tìm thấy phiên khám này.")
        if c["status"] != "in_progress":
            raise LuotKhamConflictError(
                "CONSULTATION_NOT_IN_PROGRESS",
                "Phiên khám chưa bắt đầu hoặc đã kết thúc.",
            )
        return c

    # ------------------------------------------------------------------
    # Bảng làm việc
    # ------------------------------------------------------------------

    async def bang(self, *args: Any, **kwargs: Any) -> Any:
        """Nay ở `luot_kham_doc.BangLuotKham` (bóc 24/09/2026)."""
        return await BangLuotKham(self._pool).bang(*args, **kwargs)

    # ------------------------------------------------------------------
    # C0 — check-in: dùng lại đúng máy trạng thái đang chạy
    # ------------------------------------------------------------------

    async def phong_hom_nay(self, *args: Any, **kwargs: Any) -> Any:
        """Nay ở `luot_kham_doc.BangLuotKham` (bóc 24/09/2026)."""
        return await BangLuotKham(self._pool).phong_hom_nay(*args, **kwargs)

    async def hang_cho(self, *args: Any, **kwargs: Any) -> Any:
        """Nay ở `luot_kham_doc.BangLuotKham` (bóc 24/09/2026)."""
        return await BangLuotKham(self._pool).hang_cho(*args, **kwargs)

    async def goi_khach(
        self, *, queue_entry_id: str, identity: StaffIdentity
    ) -> dict[str, Any]:
        """GỌI khách vào phòng (Tuyền 16/09/2026: *"gọi khách vào khám rồi ấn bắt
        đầu khám"*). Chờ → Đã gọi; gọi lại thì cập nhật giờ gọi.

        Ai gọi được: lượt khám chính — bác sĩ hoặc thư ký đi kèm bác sĩ ấy; chỉ
        định trong phòng — vai thực hiện bước ấy (thủ thuật: bác sĩ; siêu âm: bác
        sĩ/điều dưỡng siêu âm; lấy mẫu: điều dưỡng), tính cả vai vị trí hôm nay.
        """
        cid = identity.clinic_id
        qid = _uuid(queue_entry_id, "Mã chỗ chờ không hợp lệ.")
        async with self._pool.acquire() as conn, conn.transaction():
            q = await conn.fetchrow(
                """
                SELECT q.id::text AS id, q.visit_id::text AS visit_id, q.reason,
                       q.status, q.ref_id::text AS ref_id,
                       coalesce(q.doctor_staff_id, c.doctor_staff_id)::text
                           AS doctor_id,
                       n.actor_roles
                  FROM queue_entry q
                  LEFT JOIN consultation c
                    ON c.id = q.ref_id AND q.reason <> 'SERVICE'
                   AND c.clinic_id = q.clinic_id
                  LEFT JOIN service_order o
                    ON o.id = q.ref_id AND q.reason = 'SERVICE'
                   AND o.clinic_id = q.clinic_id
                  LEFT JOIN node_definition n
                    ON n.clinic_id = o.clinic_id AND n.code = o.node_code
                 WHERE q.clinic_id = $1::uuid AND q.id = $2::uuid
                """,
                cid,
                qid,
            )
            if q is None:
                raise NotFoundError("Không tìm thấy khách trong hàng chờ.")
            await self._lock_visit(conn, cid, q["visit_id"])
            if q["reason"] == "SERVICE":
                if not set(identity.ds_vai()) & (
                    set(q["actor_roles"] or []) | {v.value for v in HO_TRO_PHONG}
                ):
                    raise SafetyGateError("Vai của bạn không làm bước này.")
            else:
                await doi_quyen(
                    conn,
                    identity,
                    "clinical.consult.perform",
                    cau="Bạn không có quyền gọi khách vào khám.",
                )
                await self._thu_ky_cua_bac_si(conn, identity, q["doctor_id"])
                await kiem_dung_ca(
                    conn,
                    identity,
                    q["doctor_id"],
                    visit_id=q["visit_id"],
                )
            trang_thai = await conn.fetchval(
                "SELECT status FROM queue_entry WHERE clinic_id = $1::uuid"
                " AND id = $2::uuid FOR UPDATE",
                cid,
                qid,
            )
            if trang_thai not in ("waiting", "called"):
                raise LuotKhamConflictError(
                    "NOT_WAITING",
                    "Khách không còn trong hàng chờ (đang làm bước khác hoặc đã xong).",
                )
            await conn.execute(
                "UPDATE queue_entry SET status = 'called', called_at = now(),"
                " version = version + 1, updated_at = now()"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                cid,
                qid,
            )
            await self._cap_nhat_vi_tri(conn, identity.clinic_id, q["visit_id"])
            await record_event(
                conn,
                event_type="queue.called",
                aggregate_type="visit",
                aggregate_id=q["visit_id"],
                identity=identity,
                origin=ORIGIN,
                payload={"visit_id": q["visit_id"], "queue_entry_id": qid},
            )
        return {
            "ok": True,
            "queue_entry_id": qid,
            "lan_goi_lai": trang_thai == "called",
        }

    async def kham_xong(
        self,
        *,
        consultation_id: str,
        identity: StaffIdentity,
        idempotency_key: str | None = None,
        ke_hoach: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Nút "Đã khám xong" — hệ thống tự chọn kết quả phiên, người bấm không phải.

        Còn chỉ định đã duyệt chưa làm → "cần dịch vụ", khách quay lại khi các
        dịch vụ ấy làm xong. Không còn → "không cần dịch vụ", lượt khám chính
        khép lại. Bắt bác sĩ chọn giữa hai mã kỹ thuật ấy là đẩy luật vận hành
        lên đầu người đang khám.

        Mức cần của từng dịch vụ (Slice 1) mặc định theo loại dịch vụ
        (``rules.need_mac_dinh``): lấy mẫu gửi ngoài cần KẾT QUẢ, thủ thuật/siêu
        âm làm xong là đủ. ``ke_hoach`` = {mã chỉ định: PERFORMED|VALID_RESULT|
        FOLLOW_UP} để bác sĩ đổi từng dịch vụ (FOLLOW_UP chỉ bác sĩ).
        """
        cid = identity.clinic_id
        con_id = _uuid(consultation_id, "Mã phiên khám không hợp lệ.")
        async with self._pool.acquire() as conn:
            await doi_quyen(
                conn,
                identity,
                "clinical.consult.perform",
                cau="Bạn không có quyền kết thúc phiên khám.",
            )
            c = await conn.fetchrow(
                "SELECT kind, visit_id::text AS visit_id FROM consultation"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                cid,
                con_id,
            )
            if c is None:
                raise NotFoundError("Không tìm thấy phiên khám này.")
            con_lai = await conn.fetch(
                """
                SELECT o.id::text AS id, n.lam_ben_ngoai, n.flow_group
                  FROM service_order o
                  LEFT JOIN node_definition n
                    ON n.clinic_id = o.clinic_id AND n.code = o.node_code
                 WHERE o.clinic_id = $1::uuid AND o.visit_id = $2::uuid
                   AND o.hold_until_round IS NULL
                   -- Dịch vụ quầy đi độc lập; không biến thành quyết định hay
                   -- vòng đọc của bác sĩ khi bấm “Đã khám xong”.
                   AND o.nguon_lam_them IS NULL
                   AND """
                + CHI_DINH_CON_VIEC_SQL
                + """
                 ORDER BY o.created_at, o.id
                """,
                cid,
                c["visit_id"],
            )
        doi = ke_hoach if isinstance(ke_hoach, dict) else {}
        if con_lai:
            outcome = "SERVICES" if c["kind"] == "PRIMARY" else "MORE_SERVICES"
            reqs = []
            for r in con_lai:
                chon = doi.get(r["id"])
                item: dict[str, Any] = (
                    dict(chon) if isinstance(chon, dict) else {"need": chon}
                )
                if item.get("need") not in rules.PLAN_NEEDS:
                    item["need"] = rules.need_mac_dinh(
                        lam_ben_ngoai=r["lam_ben_ngoai"], flow_group=r["flow_group"]
                    )
                item["order_id"] = r["id"]
                reqs.append(item)
        else:
            outcome = "NO_SERVICES" if c["kind"] == "PRIMARY" else "DONE"
            reqs = []
        return await self.complete_consultation(
            consultation_id=con_id,
            outcome=outcome,
            requirements=reqs,
            identity=identity,
            idempotency_key=idempotency_key,
        )

    async def check_in(
        self,
        *,
        appointment_id: str,
        identity: StaffIdentity,
        xac_minh_cach: str | None = None,
    ) -> dict[str, Any]:
        # Quyền check-in (`reception.checkin.perform`) do BookingService hỏi
        # trong chính giao dịch chuyển trạng thái lịch hẹn.
        from clinicai.services.booking_service import BookingService

        result = await BookingService(self._pool).apply_action(
            appointment_id=_uuid(appointment_id, "Mã lịch hẹn không hợp lệ."),
            action="checkin",
            identity=identity,
            xac_minh_cach=xac_minh_cach,
        )
        return {"ok": True, **result}

    # ------------------------------------------------------------------
    # C2 — ghi sinh hiệu
    # ------------------------------------------------------------------

    async def goi_do_sinh_hieu(self, *args: Any, **kwargs: Any) -> Any:
        """Nay ở `sinh_hieu_service.SinhHieuService` (bóc 24/09/2026)."""
        return await SinhHieuService(self._pool).goi_do_sinh_hieu(*args, **kwargs)

    async def bat_dau_do_sinh_hieu(self, *args: Any, **kwargs: Any) -> Any:
        """Nay ở `sinh_hieu_service.SinhHieuService` (bóc 24/09/2026)."""
        return await SinhHieuService(self._pool).bat_dau_do_sinh_hieu(*args, **kwargs)

    async def dong_bo_sinh_hieu_tu_ho_so(self, *args: Any, **kwargs: Any) -> Any:
        """Nay ở `sinh_hieu_service.SinhHieuService` (bóc 24/09/2026)."""
        return await SinhHieuService(self._pool).dong_bo_sinh_hieu_tu_ho_so(
            *args, **kwargs
        )

    async def record_vitals(self, *args: Any, **kwargs: Any) -> Any:
        """Nay ở `sinh_hieu_service.SinhHieuService` (bóc 24/09/2026)."""
        return await SinhHieuService(self._pool).record_vitals(*args, **kwargs)

    # ------------------------------------------------------------------
    # C3 — bác sĩ nhận khách vào phiên khám
    # ------------------------------------------------------------------

    async def start_consultation(
        self, *, consultation_id: str, identity: StaffIdentity
    ) -> dict[str, Any]:
        cid = identity.clinic_id
        con_id = _uuid(consultation_id, "Mã phiên khám không hợp lệ.")
        async with self._pool.acquire() as conn, conn.transaction():
            # Quyền theo LOẠI phiên: tư vấn hỏi khối "Khám tư vấn", khám chính /
            # đọc kết quả hỏi khối "Khám bệnh". Vẫn hỏi TRƯỚC khi đụng dữ liệu.
            loai = await conn.fetchval(
                "SELECT kind FROM consultation WHERE clinic_id = $1::uuid"
                " AND id = $2::uuid",
                cid,
                con_id,
            )
            if loai == "TU_VAN":
                await doi_quyen(
                    conn,
                    identity,
                    "clinical.intake.perform",
                    cau="Bạn không có quyền khám tư vấn.",
                )
            else:
                await doi_quyen(
                    conn,
                    identity,
                    "clinical.consult.perform",
                    cau="Bạn không có quyền nhận khách vào khám.",
                )
            vid = await self._visit_of(conn, "consultation", cid, con_id)
            await self._lock_visit(conn, cid, vid)
            c = await conn.fetchrow(
                """
                SELECT id::text AS id, kind, status, started_by::text AS started_by,
                       doctor_staff_id::text AS doctor_id
                  FROM consultation
                 WHERE clinic_id = $1::uuid AND id = $2::uuid
                   FOR UPDATE
                """,
                cid,
                con_id,
            )
            assert c is not None
            # BÁC SĨ CỦA PHIÊN (Tuyền 29/09/2026 — "mọi chỗ hiển thị bác sĩ phải
            # ra TÊN BÁC SĨ"): phiên chưa ghi bác sĩ thì người bấm là bác sĩ thật
            # → chính họ; trợ lý bấm → `bac_si_cua_phien` (hàng chờ, lượt, lịch
            # hẹn, bác sĩ duy nhất đang trong ca ở phòng người bấm). Người bấm
            # chỉ nằm ở `started_by` + sự kiện.
            bac_si_phien = c["doctor_id"] or await self._bac_si_du_kien(
                conn, identity, con_id
            )
            await self._thu_ky_cua_bac_si(conn, identity, bac_si_phien)
            await kiem_dung_ca(conn, identity, bac_si_phien, visit_id=vid)
            if c["status"] == "in_progress":
                # Thư ký bấm rồi bác sĩ bấm lại (hay ngược lại) là CÙNG một phiên
                # đang khám, không phải bị người khác giành.
                if c["started_by"] == identity.staff_id or await self._cung_ekip(
                    conn, identity, {"doctor_id": bac_si_phien}
                ):
                    if c["doctor_id"] is None and bac_si_phien is not None:
                        # Trợ lý mở phiên chưa có bác sĩ, bác sĩ thật (hoặc trợ
                        # lý khi đã tìm ra bác sĩ) bấm tiếp → phiên ghi đúng bác
                        # sĩ ấy (như khi bác sĩ tự bấm trước).
                        await self._gan_bac_si_phien(
                            conn, cid, vid, con_id, c["kind"], bac_si_phien
                        )
                    # KHÁCH ĐÃ QUAY LẠI sau dịch vụ (phiên vẫn mở — "đợi quay
                    # lại", Tuyền 23/09): bấm Bắt đầu lần nữa = tiếp tục khám.
                    # `serving_at` là giờ HIỆN TẠI; mốc lần trước + giờ quay về
                    # hàng đi vào `consultation.resumed` (07/10/2026) — không
                    # cái gì sau đè mất cái trước.
                    quay_lai = await conn.fetchrow(
                        """
                        UPDATE queue_entry q
                           SET status = 'serving', serving_at = now(),
                               eligible_at = coalesce(q.eligible_at, now()),
                               version = q.version + 1, updated_at = now()
                          FROM queue_entry cu
                         WHERE cu.id = q.id
                           AND q.clinic_id = $1::uuid AND q.visit_id = $2::uuid
                           AND q.ref_id = $3::uuid AND q.reason = $4
                           AND q.status IN ('waiting', 'called')
                           AND NOT EXISTS (
                               SELECT 1 FROM queue_entry s
                                WHERE s.clinic_id = $1::uuid
                                  AND s.visit_id = $2::uuid
                                  AND s.status = 'serving')
                        RETURNING q.id::text AS id, cu.serving_at AS truoc,
                                  cu.eligible_at AS ve_hang
                        """,
                        cid,
                        vid,
                        con_id,
                        c["kind"],
                    )
                    if quay_lai is not None:
                        await self._block_others(conn, cid, vid, quay_lai["id"])
                        await self._cap_nhat_vi_tri(conn, identity.clinic_id, vid)
                        lan = 2 + int(
                            await conn.fetchval(
                                "SELECT count(*) FROM domain_event"
                                " WHERE clinic_id = $1::uuid"
                                "   AND aggregate_type = 'consultation'"
                                "   AND aggregate_id = $2::uuid"
                                "   AND event_type = 'consultation.resumed'",
                                cid,
                                con_id,
                            )
                        )
                        await emit_event(
                            conn,
                            ten="consultation.resumed",
                            clinic_id=cid,
                            aggregate_id=con_id,
                            payload=PhienKhamTiepTuc(
                                visit_id=vid,
                                consultation_id=con_id,
                                loai=c["kind"],
                                lan=lan,
                                quay_ve_hang_luc=quay_lai["ve_hang"]
                                and quay_lai["ve_hang"].isoformat(),
                                bat_dau_lan_truoc_luc=quay_lai["truoc"]
                                and quay_lai["truoc"].isoformat(),
                            ),
                            boi=nguoi_lam_thay(identity, bac_si_phien),
                            correlation_id=vid,
                        )
                    return {"ok": True, "consultation_id": con_id, "already": True}
                raise LuotKhamConflictError(
                    "CONSULTATION_TAKEN", "Phiên khám này bác sĩ khác đang khám."
                )
            if c["status"] != "queued":
                raise LuotKhamConflictError(
                    "CONSULTATION_NOT_QUEUED", "Phiên khám này không còn chờ khám."
                )
            entry = await conn.fetchrow(
                """
                SELECT id::text AS id, status
                  FROM queue_entry
                 WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                   AND ref_id = $3::uuid AND reason = $4
                   AND status NOT IN ('done', 'left', 'cancelled')
                   FOR UPDATE
                """,
                cid,
                vid,
                con_id,
                c["kind"],
            )
            # Tư vấn nhận được cả khách còn "chờ đo sinh hiệu" (blocked) — đo
            # trước là đường chuẩn, nhưng KHÔNG khoá (Tuyền 23–24/09).
            cho_phep = ["waiting", "called"]
            if c["kind"] == "TU_VAN":
                cho_phep.append("blocked")
            if (
                entry is None
                or entry["status"] not in cho_phep
                or await self._visit_busy(conn, cid, vid)
            ):
                raise LuotKhamConflictError(
                    "PATIENT_BUSY",
                    "Khách đang ở một bước khác, chưa gọi vào khám được.",
                )
            await conn.execute(
                """
                UPDATE consultation
                   SET status = 'in_progress', started_by = $3::uuid,
                      started_at = now(),
                       version = version + 1, updated_at = now()
                 WHERE clinic_id = $1::uuid AND id = $2::uuid
                """,
                cid,
                con_id,
                identity.staff_id,
            )
            if bac_si_phien is not None:
                # Thư ký / điều dưỡng bấm thì KHÔNG thành bác sĩ của phiên (Tuyền
                # 29/09: trọn quyền nhưng bác sĩ vẫn là bác sĩ) — phiên, chỗ chờ
                # và lượt ghi BÁC SĨ tìm được, để khách rời hàng chờ các phòng
                # khác và con trỏ vị trí về đúng phòng bác sĩ.
                await self._gan_bac_si_phien(
                    conn, cid, vid, con_id, c["kind"], bac_si_phien
                )
            await conn.execute(
                # Tư vấn nhận khách còn "chờ đo" (blocked, chưa có giờ vào hàng):
                # giờ vào hàng = lúc được nhận.
                "UPDATE queue_entry SET status = 'serving', serving_at = now(),"
                " eligible_at = coalesce(eligible_at, now()),"
                " version = version + 1, updated_at = now()"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                cid,
                entry["id"],
            )
            if c["kind"] == "REVIEW":
                # Bác sĩ đã bắt đầu đọc: vòng không còn tự lùi về "đang thu".
                await conn.execute(
                    "UPDATE review_round r SET status = 'in_review',"
                    " version = r.version + 1, updated_at = now()"
                    " FROM consultation c WHERE c.clinic_id = $1::uuid"
                    " AND c.id = $2::uuid AND r.clinic_id = c.clinic_id"
                    " AND r.visit_id = c.visit_id AND r.round_no = c.round_no"
                    " AND r.status = 'ready'",
                    cid,
                    con_id,
                )
            await self._block_others(conn, cid, vid, entry["id"])
            await self._cap_nhat_vi_tri(conn, identity.clinic_id, vid)
            await record_event(
                conn,
                event_type="consult.started",
                aggregate_type="visit",
                aggregate_id=vid,
                identity=identity,
                origin=ORIGIN,
                payload={
                    "visit_id": vid,
                    "consultation_id": con_id,
                    "kind": c["kind"],
                    "bac_si_id": bac_si_phien,
                },
            )
            await emit_event(
                conn,
                ten="consultation.started",
                clinic_id=cid,
                aggregate_id=con_id,
                payload=PhienKhamBatDau(
                    visit_id=vid, consultation_id=con_id, loai=c["kind"]
                ),
                boi=nguoi_lam_thay(identity, bac_si_phien),
                correlation_id=vid,
            )
        return {"ok": True, "consultation_id": con_id}

    async def luu_noi_dung_tu_van(
        self, *, consultation_id: str, noi_dung: object, identity: StaffIdentity
    ) -> dict[str, Any]:
        """Bác sĩ tư vấn ghi MỘT ô chữ tự do (Tuyền 24/09/2026).

        "Chỗ bác sĩ tư vấn chỉ cần 1 ô vuông to để điền tự do — để còn đồng bộ
        sang Dữ liệu mang sang từ phần khám/tư vấn ban đầu của bác sĩ chính".
        Mỗi lần lưu THÊM một dòng ``consultation_note`` (giữ lịch sử, không sửa
        dòng cũ); phiếu bác sĩ chính đọc bản MỚI NHẤT (``mang_sang``). Sửa được
        cả sau khi đã chuyển bác sĩ chính, tới khi lượt đóng.

        AI GHI ĐƯỢC (27/09/2026, bản giao diện mẫu mục 12 — "bác sĩ chính sửa
        tiếp được"): người có khối Tư vấn (``clinical.intake.perform``) HOẶC
        người ghi được phiếu khám (``clinical.record.write``). Cùng một cặp quyền
        với ghi phiếu khám (``phieu_kham_service.kiem_quyen_core``). Lịch sử sửa
        = chính các dòng ``consultation_note`` (ai, lúc nào, nội dung) + sự kiện
        ``consult.note_saved`` ghi rõ quyền nào đã cho phép.
        """
        text = noi_dung if isinstance(noi_dung, str) else ""
        text = text.strip()
        if len(text) > 20000:
            raise ValidationError("Nội dung tư vấn quá dài.")
        cid = identity.clinic_id
        con_id = _uuid(consultation_id, "Mã phiên khám không hợp lệ.")
        async with self._pool.acquire() as conn, conn.transaction():
            if await can(conn, identity, "clinical.intake.perform"):
                nguon = "tu_van"
            elif await can(conn, identity, "clinical.record.write"):
                nguon = "phieu_kham"
            else:
                raise SafetyGateError(
                    "Bạn không có quyền khám tư vấn hoặc ghi phiếu khám."
                )
            vid = await self._visit_of(conn, "consultation", cid, con_id)
            await self._lock_visit(conn, cid, vid)
            c = await conn.fetchrow(
                "SELECT c.kind, c.status, v.status AS luot"
                "  FROM consultation c JOIN visit v"
                "    ON v.clinic_id = c.clinic_id AND v.visit_id = c.visit_id"
                " WHERE c.clinic_id = $1::uuid AND c.id = $2::uuid",
                cid,
                con_id,
            )
            assert c is not None
            if c["kind"] != "TU_VAN":
                raise LuotKhamConflictError(
                    "NOT_INTAKE", "Đây không phải phiên tư vấn."
                )
            if c["luot"] not in ("OPEN", "IN_PROGRESS") or c["status"] == "cancelled":
                raise LuotKhamConflictError(
                    "CONSULTATION_NOT_OPEN", "Lượt khám đã đóng — không sửa được."
                )
            cu = await conn.fetchval(
                "SELECT body FROM consultation_note"
                " WHERE clinic_id = $1::uuid AND consultation_id = $2::uuid"
                " ORDER BY created_at DESC, id DESC LIMIT 1",
                cid,
                con_id,
            )
            if (cu or "") == text:
                return {"ok": True, "consultation_id": con_id, "doi": False}
            await conn.execute(
                "INSERT INTO consultation_note (clinic_id, consultation_id, body,"
                " recorded_by) VALUES ($1::uuid, $2::uuid, $3, $4::uuid)",
                cid,
                con_id,
                text,
                identity.staff_id,
            )
            await record_event(
                conn,
                event_type="consult.note_saved",
                aggregate_type="visit",
                aggregate_id=vid,
                identity=identity,
                origin="api:tu-van",
                payload={
                    "consultation_id": con_id,
                    "do_dai": len(text),
                    # Quyền đã cho ghi: bàn tư vấn hay phiếu bác sĩ chính.
                    "nguon": nguon,
                },
            )
        return {"ok": True, "consultation_id": con_id, "doi": True}

    async def xong_tu_van(
        self, *, consultation_id: str, identity: StaffIdentity
    ) -> dict[str, Any]:
        """`CompleteIntake` — bác sĩ tư vấn bấm Xong: chuyển bác sĩ chính (H3).

        Không bắt phải bấm Bắt đầu trước (không khoá): chưa bắt đầu thì mốc bắt
        đầu = lúc bấm Xong. Chuyện xếp khách sang bác sĩ chính KHÔNG làm ở đây —
        khối Hành trình nghe `consultation.handed_over` rồi gửi lệnh (chuẩn lego).
        """
        cid = identity.clinic_id
        con_id = _uuid(consultation_id, "Mã phiên khám không hợp lệ.")
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(
                conn,
                identity,
                "clinical.intake.perform",
                cau="Bạn không có quyền khám tư vấn.",
            )
            vid = await self._visit_of(conn, "consultation", cid, con_id)
            await self._lock_visit(conn, cid, vid)
            c = await conn.fetchrow(
                "SELECT kind, status FROM consultation"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid FOR UPDATE",
                cid,
                con_id,
            )
            assert c is not None
            if c["kind"] != "TU_VAN":
                raise LuotKhamConflictError(
                    "NOT_INTAKE", "Đây không phải phiên tư vấn."
                )
            if c["status"] == "completed":
                return {"ok": True, "consultation_id": con_id, "already": True}
            if c["status"] not in ("queued", "in_progress"):
                raise LuotKhamConflictError(
                    "CONSULTATION_NOT_OPEN", "Phiên tư vấn này đã đóng."
                )
            # Bác sĩ tư vấn đứng tên (Tuyền 29/09): ĐD/TKYK bấm hộ KHÔNG thành
            # bác sĩ của phiên. Người bấm là bác sĩ → chính họ; không thì bác
            # sĩ DUY NHẤT xếp cùng phòng với người bấm hôm nay; không ai → để
            # trống (người bấm vẫn ở `completed_by`).
            if await bac_si_trong(conn, cid, [identity.staff_id]):
                bs_tu_van: str | None = identity.staff_id
            else:
                cung = await bac_si_cung_phong_hom_nay(conn, cid, identity.staff_id)
                bs_tu_van = cung[0] if len(cung) == 1 else None
            await conn.execute(
                """
                UPDATE consultation
                   SET status = 'completed', outcome = 'HANDED_OVER',
                       started_by = coalesce(started_by, $3::uuid),
                       started_at = coalesce(started_at, now()),
                       doctor_staff_id = CASE
                           WHEN doctor_staff_id IS NULL
                             OR doctor_staff_id NOT IN (
                                 SELECT m.staff_id FROM clinic_membership m
                                  WHERE m.clinic_id = $1::uuid AND m.is_active
                                    AND m.role IN ('DOCTOR', 'ULTRASOUND_DOCTOR'))
                           THEN $4::uuid ELSE doctor_staff_id END,
                       completed_by = $3::uuid, completed_at = now(),
                       version = version + 1, updated_at = now()
                 WHERE clinic_id = $1::uuid AND id = $2::uuid
                """,
                cid,
                con_id,
                identity.staff_id,
                bs_tu_van,
            )
            await conn.execute(
                """
                UPDATE queue_entry
                   SET status = 'done', done_at = now(),
                       version = version + 1, updated_at = now()
                 WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                   AND ref_id = $3::uuid
                   AND status NOT IN ('done', 'left', 'cancelled')
                """,
                cid,
                vid,
                con_id,
            )
            await self._release_blocked(conn, cid, vid)
            await emit_event(
                conn,
                ten="consultation.handed_over",
                clinic_id=cid,
                aggregate_id=con_id,
                payload=TuVanXong(visit_id=vid, consultation_id=con_id),
                boi=nguoi(identity),
                correlation_id=vid,
            )
        return {"ok": True, "consultation_id": con_id}

    # ------------------------------------------------------------------
    # C4 — ghi chú khám (bác sĩ hoặc thư ký gõ hộ)
    # ------------------------------------------------------------------

    async def save_note(
        self, *, consultation_id: str, body: str, identity: StaffIdentity
    ) -> dict[str, Any]:
        text = (body or "").strip() if isinstance(body, str) else ""
        if not text:
            raise ValidationError("Ghi chú đang trống.")
        if len(text) > 20000:
            raise ValidationError("Ghi chú quá dài.")
        cid = identity.clinic_id
        con_id = _uuid(consultation_id, "Mã phiên khám không hợp lệ.")
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(conn, identity, "clinical.record.write")
            vid = await self._visit_of(conn, "consultation", cid, con_id)
            await self._lock_visit(conn, cid, vid)
            consultation = await self._consultation_in_progress(conn, cid, con_id)
            await kiem_dung_ca(
                conn,
                identity,
                consultation["doctor_id"],
                visit_id=vid,
            )
            await self._lock_flow(conn, cid, vid)
            await conn.execute(
                "INSERT INTO consultation_note (clinic_id, consultation_id, body,"
                " recorded_by)"
                " VALUES ($1::uuid, $2::uuid, $3, $4::uuid)",
                cid,
                con_id,
                text,
                identity.staff_id,
            )
            await conn.execute(
                "UPDATE encounter_flow SET content_revision = content_revision + 1,"
                " updated_at = now() WHERE clinic_id = $1::uuid AND visit_id ="
                " $2::uuid",
                cid,
                vid,
            )
            await record_event(
                conn,
                event_type="consult.note_saved",
                aggregate_type="visit",
                aggregate_id=vid,
                identity=identity,
                origin=ORIGIN,
                payload={"visit_id": vid, "consultation_id": con_id},
            )
        return {"ok": True}

    # ------------------------------------------------------------------
    # C5 / C6 — nháp chỉ định (thư ký) và duyệt chỉ định (chỉ bác sĩ)
    # ------------------------------------------------------------------

    async def propose_orders(
        self,
        *,
        consultation_id: str,
        service_codes: list[str],
        identity: StaffIdentity,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        # Lego Bàn khám — quyền Chỉ định (27/09 đợt 3, thay vai Thư ký).
        async with self._pool.acquire() as conn:
            await doi_quyen(conn, identity, "clinical.order.place")
        cid = identity.clinic_id
        con_id = _uuid(consultation_id, "Mã phiên khám không hợp lệ.")
        payload = {"consultation_id": con_id, "codes": list(service_codes or [])}
        async with self._pool.acquire() as conn, conn.transaction():
            vid = await self._visit_of(conn, "consultation", cid, con_id)
            await self._lock_visit(conn, cid, vid)
            cached = await self._receipt_get(
                conn, identity, "orders.draft", idempotency_key, payload
            )
            if cached is not None:
                return cached
            consultation = await self._consultation_in_progress(conn, cid, con_id)
            await kiem_dung_ca(
                conn,
                identity,
                consultation["doctor_id"],
                visit_id=vid,
            )
            services = await self._services(
                conn, cid, list(service_codes or []), visit_id=vid
            )
            ids = []
            for s in services:
                ids.append(
                    await conn.fetchval(
                        """
                        INSERT INTO service_order
                            (clinic_id, visit_id, consultation_id, service_code,
                             service_name, node_code, exec_status, recorded_by)
                        VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6, 'draft',
                           $7::uuid)
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
                )
            await record_event(
                conn,
                event_type="orders.drafted",
                aggregate_type="visit",
                aggregate_id=vid,
                identity=identity,
                origin=ORIGIN,
                payload={"visit_id": vid, "order_ids": ids},
            )
            result = {"ok": True, "order_ids": ids, "versions": {oid: 1 for oid in ids}}
            await self._receipt_put(
                conn, identity, "orders.draft", idempotency_key, payload, con_id, result
            )
        return result

    async def authorize_orders(
        self,
        *,
        consultation_id: str,
        service_codes: list[str] | None,
        draft_order_ids: list[str] | None,
        identity: StaffIdentity,
        expected_versions: dict[str, int] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        # QUYỀN, không vai (28/09/2026): ai có "Chỉ định dịch vụ" — bác sĩ hay thư
        # ký cùng phòng — duyệt được. Thư ký vẫn chỉ cho khách bác sĩ mình đi kèm.
        async with self._pool.acquire() as c0:
            await doi_quyen(
                c0, identity, "clinical.order.place", cau="Bạn không có quyền chỉ định."
            )
        cid = identity.clinic_id
        con_id = _uuid(consultation_id, "Mã phiên khám không hợp lệ.")
        codes = list(service_codes or [])
        drafts = [
            _uuid(d, "Mã chỉ định nháp không hợp lệ.") for d in (draft_order_ids or [])
        ]
        if not codes and not drafts:
            raise ValidationError("Chưa chọn dịch vụ nào để duyệt.")
        versions = dict(expected_versions or {})
        if drafts and (
            set(versions) != set(drafts)
            or any(type(v) is not int or v < 1 for v in versions.values())
        ):
            raise LuotKhamConflictError(
                "DRAFT_VERSION_REQUIRED",
                "Cần phiên bản hiện tại của từng chỉ định nháp.",
            )
        payload = {
            "consultation_id": con_id,
            "codes": codes,
            "drafts": sorted(drafts),
            "expected_versions": versions,
        }
        async with self._pool.acquire() as conn, conn.transaction():
            vid = await self._visit_of(conn, "consultation", cid, con_id)
            await self._lock_visit(conn, cid, vid)
            cached = await self._receipt_get(
                conn, identity, "orders.authorize", idempotency_key, payload
            )
            if cached is not None:
                return cached
            consultation = await self._consultation_in_progress(conn, cid, con_id)
            await kiem_dung_ca(
                conn,
                identity,
                consultation["doctor_id"],
                visit_id=vid,
            )
            # Ê-KÍP của phiên duyệt được (Tuyền 29/09/2026 — trợ lý trọn quyền):
            # người bấm "Bắt đầu", bác sĩ của phiên, hoặc thư ký / điều dưỡng có
            # quyền Khám làm cho bác sĩ ấy. Trước đây đòi tài khoản DOCTOR — thư
            # ký có lego Bàn khám đã có quyền Chỉ định vẫn bị chặn ở đây. Chỉ còn
            # chặn: thư ký đã phân theo bác sĩ khác, hai bác sĩ thật giành phiên.
            if not await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM staff s JOIN clinic_membership m"
                " ON m.staff_id = s.id WHERE s.id = $1::uuid AND s.is_active"
                " AND m.clinic_id = $2::uuid AND m.is_active)",
                identity.staff_id,
                cid,
            ):
                raise SafetyGateError("Tài khoản này đã ngừng hoạt động.")
            await self._thu_ky_cua_bac_si(conn, identity, consultation["doctor_id"])
            tu_bam = consultation["started_by"] == identity.staff_id
            if not tu_bam and not await self._cung_ekip(conn, identity, consultation):
                raise SafetyGateError(
                    "Chỉ bác sĩ đang phụ trách phiên khám (hoặc người làm cho bác"
                    " sĩ ấy) được duyệt chỉ định."
                )
            ids: list[str] = []
            if drafts:
                selected = await conn.fetch(
                    "SELECT id::text AS id, version, exec_status FROM service_order"
                    " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
                    " AND consultation_id = $3::uuid AND id = ANY($4::uuid[])"
                    " ORDER BY id FOR UPDATE",
                    cid,
                    vid,
                    con_id,
                    drafts,
                )
                if len(selected) != len(set(drafts)) or any(
                    row["exec_status"] != "draft" for row in selected
                ):
                    raise LuotKhamConflictError(
                        "DRAFT_NOT_FOUND",
                        "Chỉ định nháp không thuộc phiên khám này hoặc đã xử lý.",
                    )
                if any(row["version"] != versions[row["id"]] for row in selected):
                    raise LuotKhamConflictError(
                        "VERSION_CONFLICT",
                        "Chỉ định nháp đã thay đổi — tải lại trước khi duyệt.",
                    )
                flipped = await conn.fetch(
                    """
                    UPDATE service_order
                       SET exec_status = 'authorized', authorized_by = $4::uuid,
                           authorized_at = now(), version = version + 1,
                              updated_at = now(),
                           -- Lifecycle v1: chỉ định chính thức chờ khách chọn,
                           -- chưa có phòng chính thức (routing_revision = 0).
                           selection_status = 'PENDING',
                           routing_status = 'UNASSIGNED'
                     WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                       AND id = ANY($3::uuid[]) AND exec_status = 'draft'
                       AND consultation_id = $5::uuid
                    RETURNING id::text
                    """,
                    cid,
                    vid,
                    drafts,
                    identity.staff_id,
                    con_id,
                )
                if len(flipped) != len(set(drafts)):
                    raise LuotKhamConflictError(
                        "DRAFT_NOT_FOUND",
                        "Có chỉ định nháp không thuộc lượt khám này hoặc đã được xử"
                        " lý.",
                    )
                ids.extend(r["id"] for r in flipped)
            if codes:
                for s in await self._services(conn, cid, codes, visit_id=vid):
                    ids.append(
                        await conn.fetchval(
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
                    )
            await self._tu_xep_phong(conn, identity, vid)
            await record_event(
                conn,
                event_type="orders.authorized",
                aggregate_type="visit",
                aggregate_id=vid,
                identity=identity,
                origin=ORIGIN,
                payload={"visit_id": vid, "consultation_id": con_id, "order_ids": ids},
            )
            result = {"ok": True, "order_ids": ids}
            await self._receipt_put(
                conn,
                identity,
                "orders.authorize",
                idempotency_key,
                payload,
                con_id,
                result,
            )
        return result

    # ------------------------------------------------------------------
    # C11 / C12 — kết thúc phiên khám
    # ------------------------------------------------------------------

    async def _kiem_ho_so_truoc_khi_khep(
        self,
        conn: asyncpg.Connection,
        *,
        clinic_id: str,
        visit_id: str,
    ) -> None:
        row = await conn.fetchrow(
            """
            SELECT prescription_draft
              FROM clinical_record
             WHERE clinic_id = $1::uuid
               AND visit_id = $2::uuid
             FOR UPDATE
            """,
            clinic_id,
            visit_id,
        )

        if row is not None and row["prescription_draft"] is not None:
            raise LuotKhamConflictError(
                "PRESCRIPTION_DRAFT_PENDING",
                "Còn đơn thuốc thư ký nhập chờ bác sĩ duyệt.",
            )

    async def complete_consultation(
        self,
        *,
        consultation_id: str,
        outcome: str,
        requirements: list[dict[str, Any]] | None,
        identity: StaffIdentity,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        cid = identity.clinic_id
        con_id = _uuid(consultation_id, "Mã phiên khám không hợp lệ.")
        plan: list[tuple[str, str]] = []
        theo_doi_cau_hinh: dict[str, dict[str, Any]] = {}
        seen: set[str] = set()
        for item in requirements or []:
            if not isinstance(item, dict):
                raise ValidationError("Danh sách yêu cầu không đúng dạng.")
            oid = _uuid(item.get("order_id"), "Mã chỉ định trong yêu cầu không hợp lệ.")
            need = str(item.get("need") or "")
            if need not in rules.PLAN_NEEDS:
                raise ValidationError(
                    "Mỗi dịch vụ phải chọn: đã làm, có kết quả, hoặc theo dõi sau."
                )
            if oid not in seen:
                seen.add(oid)
                plan.append((oid, need))
                if need == rules.FOLLOW_UP:
                    han = item.get("han")
                    if han not in (None, "") and rules.doc_han_theo_doi(han) is None:
                        raise ValidationError(
                            "Hạn theo dõi phải là ngày dạng YYYY-MM-DD."
                        )
                    theo_doi_cau_hinh[oid] = item
        reqs, theo_doi = rules.tach_ke_hoach(plan)
        payload = {
            "consultation_id": con_id,
            "outcome": outcome,
            "reqs": sorted(plan),
            "theo_doi": {
                k: {
                    "owner_id": v.get("owner_id"),
                    "han": v.get("han"),
                    "ly_do": v.get("ly_do"),
                }
                for k, v in sorted(theo_doi_cau_hinh.items())
            },
        }
        async with self._pool.acquire() as conn, conn.transaction():
            vid = await self._visit_of(conn, "consultation", cid, con_id)
            await self._lock_visit(conn, cid, vid, cho_phep_da_ky=True)
            cached = await self._receipt_get(
                conn, identity, "consult.complete", idempotency_key, payload
            )
            if cached is not None:
                return cached
            await doi_quyen(
                conn,
                identity,
                "clinical.consult.perform",
                cau="Bạn không có quyền kết thúc phiên khám.",
            )
            if theo_doi:
                # Cho khách về trước khi có kết quả là quyết định chuyên môn —
                # cùng quyền với Hoàn tất khám.
                await doi_quyen(
                    conn,
                    identity,
                    "clinical.consult.finalize",
                    cau="Chỉ bác sĩ quyết cho khách về trước và theo dõi kết quả sau.",
                )
            c = await self._consultation_in_progress(conn, cid, con_id)
            if c["doctor_id"] is None:
                # Phiên mở trước bản 29/09 (trợ lý bấm, không ghi bác sĩ): khép
                # phiên thì ghi bác sĩ — hàng "Khám với bác sĩ" không còn "—".
                bac_si_phien = await self._bac_si_du_kien(conn, identity, con_id)
                if bac_si_phien is not None:
                    await self._gan_bac_si_phien(
                        conn, cid, vid, con_id, c["kind"], bac_si_phien
                    )
                    c = await self._consultation_in_progress(conn, cid, con_id)
            await self._thu_ky_cua_bac_si(conn, identity, c["doctor_id"])
            await kiem_dung_ca(conn, identity, c["doctor_id"], visit_id=vid)
            if not rules.outcome_allowed(c["kind"], outcome):
                raise LuotKhamConflictError(
                    "WRONG_CONSULTATION_KIND",
                    "Kết quả này không dùng cho loại phiên khám hiện tại.",
                )
            next_round: int | None = None
            if outcome == "NO_SERVICES":
                live = await conn.fetchval(
                    """
                    SELECT count(*) FROM service_order
                     WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                       AND exec_status IN ('authorized', 'assigned', 'in_progress')
                       -- Khách đã BỎ ở quầy thì không còn là việc (24/09/2026:
                       -- "Đo mật độ xương" khách không làm chặn Hoàn tất). Cùng
                       -- luật với danh sách "còn việc" nút Hoàn tất dùng.
                       AND selection_status IS DISTINCT FROM 'NOT_SELECTED'
                       -- Làm thêm tại quầy (01/10/2026) không do bác sĩ chỉ
                       -- định — bác sĩ kết thúc "không cần dịch vụ" vẫn được,
                       -- việc ấy đi tiếp theo luồng của nó.
                       AND nguon_lam_them IS NULL
                    """,
                    cid,
                    vid,
                )
                if live:
                    raise LuotKhamConflictError(
                        "ORDERS_PENDING",
                        "Còn chỉ định đã duyệt chưa làm — không kết thúc 'không cần"
                        " dịch vụ' được.",
                    )
                nhap_huy = await conn.fetch(
                    """
                    UPDATE service_order
                       SET exec_status = 'cancelled', cancelled_by = $3::uuid,
                           cancel_reason = $4,
                           version = version + 1, updated_at = now()
                     WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                       AND exec_status = 'draft'
                    RETURNING id::text AS id, service_code, service_name
                    """,
                    cid,
                    vid,
                    identity.staff_id,
                    LY_DO_HUY_NHAP_KHI_KHAM_XONG,
                )
                # I4 (C18, 02/10/2026): tự huỷ nào cũng phải để lại vết — nháp của
                # điều dưỡng / thư ký không được biến mất không dấu. Mỗi nháp một
                # sự kiện (ai bấm Khám xong, vì sao) → lên Hành trình khách.
                for nh in nhap_huy:
                    await emit_event(
                        conn,
                        ten="service_order.cancelled",
                        clinic_id=cid,
                        aggregate_id=nh["id"],
                        so_ke_tiep=True,
                        payload=ChiDinhDaHuy(
                            visit_id=vid,
                            service_order_id=nh["id"],
                            service_code=nh["service_code"],
                            service_name=nh["service_name"],
                            ly_do=LY_DO_HUY_NHAP_KHI_KHAM_XONG,
                        ),
                        boi=nguoi(identity),
                        correlation_id=vid,
                    )
            elif outcome in rules.OUTCOMES_OPENING_ROUND:
                if not plan:
                    raise LuotKhamConflictError(
                        "REQUIREMENTS_REQUIRED",
                        "Chọn ít nhất một dịch vụ phải xong trước lần đọc kết quả.",
                    )
                rows = await conn.fetch(
                    """
                    SELECT id::text AS id, exec_status, hold_until_round
                      FROM service_order
                     WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                       AND id = ANY($3::uuid[])
                    """,
                    cid,
                    vid,
                    [oid for oid, _ in plan],
                )
                found = {r["id"]: r for r in rows}
                bad = [
                    oid
                    for oid, _ in plan
                    if oid not in found
                    or found[oid]["exec_status"] in ("draft", "cancelled")
                ]
                if bad:
                    raise LuotKhamConflictError(
                        "REQUIREMENT_ORDER_INVALID",
                        "Yêu cầu trỏ tới chỉ định chưa duyệt, đã huỷ hoặc không"
                        " thuộc lượt này.",
                    )
                cyclic = rules.cyclic_orders(
                    int(c["round_no"]) + 1,
                    [(oid, found[oid]["hold_until_round"]) for oid, _ in reqs],
                )
                if cyclic:
                    raise LuotKhamValidationError(
                        "CYCLIC_REQUIREMENT",
                        "Có dịch vụ vừa bắt buộc trước lần đọc kết quả vừa được dặn"
                        " làm sau lần đọc ấy.",
                    )
                # FOLLOW_UP không thành yêu cầu của vòng đọc: chỉ còn dịch vụ
                # theo dõi thì KHÔNG mở vòng, khách làm xong là về.
                next_round = int(c["round_no"]) + 1 if reqs else None
                for oid in theo_doi:
                    await self._mo_theo_doi(
                        conn,
                        identity,
                        vid=vid,
                        oid=oid,
                        cau_hinh=theo_doi_cau_hinh[oid],
                        bac_si=c["doctor_id"],
                    )
            if c["kind"] == "REVIEW":
                vong = await conn.fetchval(
                    "SELECT id::text FROM review_round WHERE clinic_id = $1::uuid"
                    " AND visit_id = $2::uuid AND round_no = $3",
                    cid,
                    vid,
                    c["round_no"],
                )
                if vong is not None:
                    con_quyet = rules.can_quyet(
                        [
                            self._view(q)
                            for q in await self._yeu_cau_cua_vong(conn, cid, vong)
                        ]
                    )
                    if con_quyet:
                        # NOT_PERFORMED không tự coi là đạt: đóng vòng đọc khi
                        # bác sĩ chưa quyết là để lọt một dịch vụ không làm.
                        raise LuotKhamConflictError(
                            "REQUIREMENT_DECISION_REQUIRED",
                            f"Còn {len(con_quyet)} dịch vụ không thực hiện được —"
                            " bác sĩ miễn (ghi lý do) hoặc chuyển theo dõi trước.",
                        )
            if outcome in ("NO_SERVICES", "DONE"):
                # HOÀN TẤT KHÁM (CORE-A, 23/09/2026): phiên khám cuối. Cần quyền
                # `clinical.consult.finalize` (29/09: không còn đòi đúng bác sĩ).
                # KHÔNG khoá hồ sơ — Tuyền chốt 23/09: "không khoá, sửa thoải
                # mái"; bệnh án vẫn sửa trực tiếp sau khi hoàn tất.
                # Hai lý do, hai câu (24/09/2026): câu gộp cũ nói "chỉ bác sĩ phụ
                # trách" cả khi người bấm CHÍNH LÀ bác sĩ phụ trách mà thiếu khối
                # Hoàn tất khám — người đọc đi tìm sai chỗ.
                if not await can(conn, identity, "clinical.consult.finalize"):
                    raise SafetyGateError(
                        "Bạn không có quyền Hoàn tất khám — nhờ quản lý cấp"
                        " trên màn Phân quyền."
                    )
                # Tuyền chốt 29/09/2026: thư ký / điều dưỡng có quyền Hoàn tất
                # khám hoàn tất THAY bác sĩ — không còn đòi người bấm = bác sĩ
                # của phiên. Phiên vẫn ghi bác sĩ của phiên (`doctor_staff_id`
                # không đổi), người bấm vào `completed_by` + sự kiện. Chỉ chặn
                # một BÁC SĨ THẬT khép phiên của bác sĩ thật khác.
                if await la_bac_si_khac(conn, cid, identity.staff_id, c["doctor_id"]):
                    raise SafetyGateError(
                        "Chỉ bác sĩ phụ trách mới được kết thúc phần khám lâm sàng."
                    )
                await self._kiem_ho_so_truoc_khi_khep(
                    conn,
                    clinic_id=cid,
                    visit_id=vid,
                )
            await conn.execute(
                """
                UPDATE consultation
                   SET status = 'completed', outcome = $3, completed_by = $4::uuid,
                       completed_at = now(), version = version + 1, updated_at = now()
                 WHERE clinic_id = $1::uuid AND id = $2::uuid
                """,
                cid,
                con_id,
                outcome,
                identity.staff_id,
            )
            # Mốc "khám xong" = mốc DUY NHẤT phát sự kiện của bệnh án (Tuyền chốt
            # 24/09): lưu liên tục thì không phát, bấm Hoàn tất/Khám xong mới phát.
            await emit_event(
                conn,
                ten="consultation.completed",
                clinic_id=cid,
                aggregate_id=con_id,
                payload=KhamXong(
                    visit_id=vid,
                    consultation_id=con_id,
                    loai=c["kind"],
                    ket_qua=outcome,
                ),
                boi=nguoi_lam_thay(identity, c["doctor_id"]),
                correlation_id=vid,
            )
            # Bác sĩ hẹn tái khám — sự thật chốt lúc Khám xong. Phiếu v5 (mục G
            # "Ngày tái khám", ô `*_follow_date`) trước, bệnh án cũ sau: trước
            # 26/09 ngày hẹn trên phiếu v5 KHÔNG ai đọc, nên hẹn không sinh nhắc.
            ngay_tai_kham = await conn.fetchval(
                """
                SELECT coalesce(
                  (SELECT max(nullif(btrim(o.value ->> 'gia_tri'), ''))
                     FROM phieu_kham_luot p,
                          jsonb_each(p.du_lieu) AS o
                    WHERE p.clinic_id = $1::uuid AND p.visit_id = $2::uuid
                      AND right(o.key, 12) = '_follow_date'
                      AND nullif(btrim(o.value ->> 'gia_tri'), '')
                          ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'),
                  (SELECT nullif(btrim(soap_plan #>> '{tai_kham,ngay}'), '')
                     FROM clinical_record WHERE clinic_id = $1::uuid
                      AND visit_id = $2::uuid))
                """,
                cid,
                vid,
            )
            if ngay_tai_kham and not await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM domain_event WHERE clinic_id = $1::uuid"
                " AND event_type = 'followup.scheduled' AND aggregate_id = $2::uuid"
                " AND payload->>'ngay' = $3)",
                cid,
                vid,
                str(ngay_tai_kham),
            ):
                await emit_event(
                    conn,
                    ten="followup.scheduled",
                    clinic_id=cid,
                    aggregate_id=vid,
                    payload=DaHenTaiKham(visit_id=vid, ngay=str(ngay_tai_kham)),
                    boi=nguoi_lam_thay(identity, c["doctor_id"]),
                    correlation_id=vid,
                )
            await conn.execute(
                """
                UPDATE queue_entry
                   SET status = 'done', done_at = now(), version = version + 1,
                      updated_at = now()
                 WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                    AND ref_id = $3::uuid
                   AND status NOT IN ('done', 'left', 'cancelled')
                """,
                cid,
                vid,
                con_id,
            )
            if c["kind"] == "REVIEW":
                await conn.execute(
                    "UPDATE review_round SET status = 'closed', closed_at = now(),"
                    " version = version + 1, updated_at = now()"
                    " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid AND"
                    " round_no = $3",
                    cid,
                    vid,
                    c["round_no"],
                )
            if next_round is not None:
                round_id = await conn.fetchval(
                    """
                    INSERT INTO review_round (clinic_id, visit_id, round_no, status,
                       locked_by)
                    VALUES ($1::uuid, $2::uuid, $3, 'collecting', $4::uuid)
                    RETURNING id::text
                    """,
                    cid,
                    vid,
                    next_round,
                    identity.staff_id,
                )
                await conn.executemany(
                    """
                    INSERT INTO round_requirement (clinic_id, round_id,
                       service_order_id, need)
                    VALUES ($1::uuid, $2::uuid, $3::uuid, $4)
                    """,
                    [(cid, round_id, oid, need) for oid, need in reqs],
                )
            await self._release_blocked(conn, cid, vid)
            await self._evaluate_rounds(conn, identity, vid)
            await self._ket_thuc_neu_xong(conn, identity, vid)
            await self._cap_nhat_vi_tri(conn, identity.clinic_id, vid)
            await record_event(
                conn,
                event_type="consult.completed",
                aggregate_type="visit",
                aggregate_id=vid,
                identity=identity,
                origin=ORIGIN,
                payload={
                    "visit_id": vid,
                    "consultation_id": con_id,
                    "outcome": outcome,
                    "next_round": next_round,
                },
            )
            result = {
                "ok": True,
                "consultation_id": con_id,
                "next_round": next_round,
            }
            await self._receipt_put(
                conn,
                identity,
                "consult.complete",
                idempotency_key,
                payload,
                con_id,
                result,
            )
        return result

    # ------------------------------------------------------------------
    # Slice 1 — bác sĩ quyết một yêu cầu: miễn hoặc chuyển theo dõi
    # ------------------------------------------------------------------

    async def quyet_yeu_cau(
        self,
        *,
        requirement_id: str,
        hanh_dong: str,
        ly_do: str | None,
        identity: StaffIdentity,
        owner_id: str | None = None,
        han: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Bác sĩ quyết một yêu cầu của vòng đọc chưa đạt.

        ``WAIVE``: không cần nữa (đổi kế hoạch: miễn ở đây rồi chỉ định thêm
        trong phiên đọc kết quả). ``FOLLOW_UP``: khách không phải chờ — mở việc
        theo dõi có người phụ trách và hạn. Cả hai bắt buộc lý do và ghi nhật
        ký. Người có quyền Hoàn tất khám quyết được — kể cả thư ký / điều dưỡng
        làm cho bác sĩ của lượt (Tuyền 29/09/2026); bác sĩ khác thì không.
        """
        # Hỏi QUYỀN "Hoàn tất khám" (24/09/2026 — cùng người với DOCTOR_ROLES
        # cũ: chỉ bác sĩ; thư ký không quyết).
        async with self._pool.acquire() as conn:
            await doi_quyen(
                conn,
                identity,
                "clinical.consult.finalize",
                cau="Chỉ bác sĩ quyết miễn hoặc theo dõi.",
            )
        cid = identity.clinic_id
        rid = _uuid(requirement_id, "Mã yêu cầu không hợp lệ.")
        if hanh_dong not in ("WAIVE", "FOLLOW_UP"):
            raise ValidationError("Chọn miễn hoặc chuyển theo dõi.")
        ghi = ly_do.strip() if isinstance(ly_do, str) else ""
        if not ghi:
            raise ValidationError("Ghi lý do bác sĩ quyết như vậy.")
        if len(ghi) > 2000:
            raise ValidationError("Lý do quá dài.")
        if han not in (None, "") and rules.doc_han_theo_doi(han) is None:
            raise ValidationError("Hạn theo dõi phải là ngày dạng YYYY-MM-DD.")
        payload = {
            "requirement_id": rid,
            "hanh_dong": hanh_dong,
            "ly_do": ghi,
            "owner_id": owner_id,
            "han": han,
        }
        async with self._pool.acquire() as conn, conn.transaction():
            vid = await conn.fetchval(
                "SELECT r.visit_id::text FROM round_requirement q"
                " JOIN review_round r ON r.id = q.round_id AND r.clinic_id ="
                " q.clinic_id WHERE q.clinic_id = $1::uuid AND q.id = $2::uuid",
                cid,
                rid,
            )
            if vid is None:
                raise NotFoundError("Không tìm thấy yêu cầu này.")
            visit = await self._lock_visit(conn, cid, vid)
            await kiem_dung_ca(conn, identity, visit["doctor_id"], visit_id=vid)
            cached = await self._receipt_get(
                conn, identity, "requirement.decide", idempotency_key, payload
            )
            if cached is not None:
                return cached
            q = await conn.fetchrow(
                """
                SELECT q.status, q.service_order_id::text AS order_id,
                       q.round_id::text AS round_id, o.exec_status,
                       r.status AS vong_status, r.round_no
                  FROM round_requirement q
                  JOIN review_round r ON r.id = q.round_id AND r.clinic_id = q.clinic_id
                  JOIN service_order o
                    ON o.id = q.service_order_id AND o.clinic_id = q.clinic_id
                 WHERE q.clinic_id = $1::uuid AND q.id = $2::uuid
                   FOR UPDATE OF q
                """,
                cid,
                rid,
            )
            assert q is not None
            phu_trach = {
                visit["doctor_id"],
                *[
                    r["d"]
                    for r in await conn.fetch(
                        "SELECT doctor_staff_id::text AS d FROM consultation"
                        " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid",
                        cid,
                        vid,
                    )
                ],
            }
            phu_trach.discard(None)
            # Tuyền 29/09/2026 — trợ lý trọn quyền: ai có quyền Hoàn tất khám
            # quyết thay bác sĩ của lượt. Chỉ chặn: thư ký đã phân theo bác sĩ
            # khác, và một BÁC SĨ THẬT quyết trên lượt của bác sĩ thật khác.
            bac_si = await bac_si_trong(conn, cid, (identity.staff_id, *phu_trach))
            if identity.staff_id not in phu_trach:
                await self._thu_ky_cua_bac_si(conn, identity, visit["doctor_id"])
                if identity.staff_id in bac_si and bac_si - {identity.staff_id}:
                    raise SafetyGateError(
                        "Chỉ bác sĩ phụ trách lượt khám này quyết được yêu cầu."
                    )
            # Việc theo dõi mặc định giao BÁC SĨ của lượt, không phải trợ lý bấm.
            bac_si_theo_doi = (
                identity.staff_id
                if identity.staff_id in bac_si or not visit["doctor_id"]
                else visit["doctor_id"]
            )
            if q["vong_status"] == "closed":
                raise LuotKhamConflictError(
                    "ROUND_CLOSED", "Lần đọc kết quả này đã đóng."
                )
            if q["status"] in ("waived", "follow_up"):
                raise LuotKhamConflictError(
                    "REQUIREMENT_DECIDED", "Yêu cầu này bác sĩ đã quyết rồi."
                )
            trang_thai = rules.requirement_state(
                self._view(
                    next(
                        r
                        for r in await self._yeu_cau_cua_vong(conn, cid, q["round_id"])
                        if r["id"] == rid
                    )
                )
            )
            if trang_thai == "satisfied":
                raise LuotKhamConflictError(
                    "REQUIREMENT_SATISFIED",
                    "Yêu cầu này đã đạt — không cần miễn hay theo dõi nữa.",
                )
            if hanh_dong == "FOLLOW_UP" and q["exec_status"] != "performed":
                # Việc theo dõi đóng khi bác sĩ DUYỆT KẾT QUẢ. Dịch vụ không làm
                # được thì không bao giờ có kết quả → việc mồ côi. Hẹn làm lại
                # là tái khám: miễn ở đây (ghi lý do) + hẹn trong bệnh án.
                raise LuotKhamConflictError(
                    "FOLLOW_UP_NEEDS_RESULT",
                    "Chỉ chuyển theo dõi khi đang chờ kết quả. Dịch vụ không làm"
                    " được: miễn (ghi lý do) và hẹn tái khám trong bệnh án.",
                )
            fid: str | None = None
            mien = hanh_dong == "WAIVE"
            if mien:
                await conn.execute(
                    """
                    UPDATE round_requirement
                       SET status = 'waived', waived_by = $3::uuid,
                           waived_reason = $4, updated_at = now()
                     WHERE clinic_id = $1::uuid AND id = $2::uuid
                    """,
                    cid,
                    rid,
                    identity.staff_id,
                    ghi,
                )
            else:
                fid = await self._mo_theo_doi(
                    conn,
                    identity,
                    vid=vid,
                    oid=q["order_id"],
                    cau_hinh={"owner_id": owner_id, "han": han, "ly_do": ghi},
                    bac_si=bac_si_theo_doi,
                )
                await conn.execute(
                    """
                    UPDATE round_requirement q
                       SET status = 'follow_up', waived_by = $3::uuid,
                           waived_reason = $4, follow_up_case_id = $5::uuid,
                           followup_owner = f.owner_staff_id,
                           followup_due = (f.due_at AT TIME ZONE
                                           'Asia/Ho_Chi_Minh')::date,
                           updated_at = now()
                      FROM follow_up_case f
                     WHERE q.clinic_id = $1::uuid AND q.id = $2::uuid
                       AND f.id = $5::uuid
                    """,
                    cid,
                    rid,
                    identity.staff_id,
                    ghi,
                    fid,
                )
            await record_event(
                conn,
                # f-string có chủ ý: bài canh nhãn (test_audit_labels_drift)
                # đọc được cả hai nhánh mã.
                event_type=f"requirement.{'waived' if mien else 'follow_up'}",
                aggregate_type="visit",
                aggregate_id=vid,
                identity=identity,
                origin=ORIGIN,
                payload={
                    "visit_id": vid,
                    "requirement_id": rid,
                    "order_id": q["order_id"],
                    "round_no": q["round_no"],
                    # Lý do ở round_requirement.waived_reason, không ở nhật ký.
                    "follow_up_case_id": fid,
                },
            )
            await self._evaluate_rounds(conn, identity, vid)
            await self._ket_thuc_neu_xong(conn, identity, vid)
            await self._cap_nhat_vi_tri(conn, cid, vid)
            result = {
                "ok": True,
                "requirement_id": rid,
                "trang_thai": "waived" if hanh_dong == "WAIVE" else "follow_up",
                "follow_up_case_id": fid,
            }
            await self._receipt_put(
                conn,
                identity,
                "requirement.decide",
                idempotency_key,
                payload,
                rid,
                result,
            )
        return result

    async def cho_quyet(self, *, identity: StaffIdentity) -> dict[str, Any]:
        """Yêu cầu của vòng đọc đang CHỜ bác sĩ: kết quả chưa về, hoặc dịch vụ
        không làm được cần bác sĩ quyết.

        Khách đang chờ kết quả không nằm trong hàng chờ khám nào (vòng đọc chưa
        sẵn sàng), nên trước Slice 1 bác sĩ không thấy họ ở đâu cả — và không có
        chỗ nào để nói "cho khách về, báo kết quả sau". Bác sĩ thấy khách của
        mình; thư ký thấy khách của bác sĩ mình đi kèm (chỉ xem — quyết là việc
        của bác sĩ).
        """
        cid = identity.clinic_id
        async with self._pool.acquire() as conn:
            # Hỏi QUYỀN "Khám bệnh" (24/09/2026 — cùng người với CONSULT_ROLES).
            await doi_quyen(
                conn,
                identity,
                "clinical.consult.perform",
                cau="Chỉ bác sĩ hoặc thư ký xem việc chờ quyết.",
            )
            duoc_quyet = await can(conn, identity, "clinical.consult.finalize")
            # Theo lego (27/09 đợt 3): thư ký đã phân → bác sĩ của mình; người
            # Hoàn tất được → việc của mình; còn lại (thư ký chưa phân) → tất cả.
            bac_si: list[str] | None = await bac_si_cua_thu_ky(conn, identity)
            if bac_si is None and duoc_quyet:
                bac_si = [identity.staff_id]
            rows = await conn.fetch(
                """
                SELECT q.id::text AS id, q.need, q.status,
                       q.service_order_id::text AS order_id,
                       o.exec_status,
                       """
                + CO_KET_QUA_VONG_SQL
                + """ AS co_ket_qua,
                       o.service_name, o.not_performed_reason,
                       r.round_no, r.status AS vong_status,
                       v.visit_id::text AS visit_id, p.full_name, p.patient_code
                  FROM round_requirement q
                  JOIN review_round r
                    ON r.id = q.round_id AND r.clinic_id = q.clinic_id
                  JOIN service_order o
                    ON o.id = q.service_order_id AND o.clinic_id = q.clinic_id
                  LEFT JOIN node_definition nd
                    ON nd.clinic_id = o.clinic_id AND nd.code = o.node_code
                  JOIN visit v ON v.visit_id = r.visit_id AND v.clinic_id = r.clinic_id
                  JOIN patient p
                    ON p.clinic_patient_id = v.clinic_patient_id
                   AND p.clinic_id = v.clinic_id
                 WHERE q.clinic_id = $1::uuid
                   AND r.status <> 'closed' AND q.status = 'open'
                   AND v.status IN ('OPEN', 'IN_PROGRESS')
                   -- Chỉ việc của BÁC SĨ: đang chờ kết quả (đã làm, chưa có kết
                   -- quả) hoặc không làm được. Lọc ở SQL để LIMIT không cắt mất.
                   AND ((q.need = 'VALID_RESULT' AND o.exec_status = 'performed'
                         AND NOT """
                + CO_KET_QUA_VONG_SQL
                + """)
                        OR o.exec_status IN ('not_performed', 'cancelled'))
                   AND ($2::text[] IS NULL
                        OR v.attending_doctor_id::text = ANY($2::text[])
                        OR EXISTS (SELECT 1 FROM consultation c
                                    WHERE c.clinic_id = v.clinic_id
                                      AND c.visit_id = v.visit_id
                                      AND c.doctor_staff_id::text = ANY($2::text[])))
                 ORDER BY r.created_at, q.created_at
                 LIMIT 200
                """,
                cid,
                bac_si,
            )
        # Hàng "chờ bác sĩ quyết": cắt im lặng là một yêu cầu chờ mãi.
        canh_bao_neu_day("bac_si.cho_quyet", len(rows), 200, clinic_id=cid)
        viec = []
        for q in rows:
            trang_thai = rules.requirement_state(self._view(q))
            # Đã đạt rồi (chờ vòng tự cập nhật) hay chỉ cần "đã làm" mà chưa
            # làm tới — đó là việc của phòng dịch vụ, không phải của bác sĩ.
            if trang_thai == "satisfied":
                continue
            if trang_thai == "open" and (
                q["need"] != "VALID_RESULT" or q["exec_status"] != "performed"
            ):
                continue
            viec.append(
                {
                    "id": q["id"],
                    "visit_id": q["visit_id"],
                    "ten": q["full_name"],
                    "ma_bn": q["patient_code"],
                    "dich_vu": q["service_name"],
                    "can": q["need"],
                    "trang_thai": (
                        "can_quyet" if trang_thai == "needs_decision" else "cho_ket_qua"
                    ),
                    "ly_do_khong_lam": q["not_performed_reason"],
                    "vong": q["round_no"],
                }
            )
        return {"viec": viec, "duoc_quyet": duoc_quyet}

    async def chi_dinh_hom_nay(self, *args: Any, **kwargs: Any) -> Any:
        """Nay ở `luot_kham_doc.BangLuotKham` (bóc 24/09/2026)."""
        return await BangLuotKham(self._pool).chi_dinh_hom_nay(*args, **kwargs)

    async def sau_khi_co_ket_qua(
        self, *, order_id: str, identity: StaffIdentity
    ) -> None:
        """Kết quả vừa gắn vào một chỉ định (tệp tải lên): chạy lại vòng đọc.

        Tệp kết quả đi đường riêng (``tep_ket_qua_service``) nên phải gọi lại
        D2 ở đây — không thì yêu cầu "cần kết quả" đứng im dù kết quả đã về.
        Lượt đã đóng thì thôi: kết quả muộn lúc ấy thuộc việc theo dõi.
        """
        cid = identity.clinic_id
        oid = _uuid(order_id, "Mã chỉ định không hợp lệ.")
        async with self._pool.acquire() as conn, conn.transaction():
            try:
                vid = await self._visit_of(conn, "service_order", cid, oid)
                await self._lock_visit(conn, cid, vid)
            except (NotFoundError, LuotKhamConflictError):
                return
            await self._evaluate_rounds(conn, identity, vid)
            await self._ket_thuc_neu_xong(conn, identity, vid)
            await self._cap_nhat_vi_tri(conn, cid, vid)

    # ------------------------------------------------------------------
    # C7 — điều phối chỉ định vào phòng
    # ------------------------------------------------------------------

    async def dispatch_order(
        self,
        *,
        order_id: str,
        room_id: str,
        expected_version: int | None,
        identity: StaffIdentity,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        # Lego 9 Điều phối khách (27/09 đợt 3, thay vai Trưởng ca / Quản lý).
        async with self._pool.acquire() as conn:
            await doi_quyen(
                conn,
                identity,
                "dispatch.manage",
                cau="Bạn không có quyền điều phối khách.",
            )
        cid = identity.clinic_id
        oid = _uuid(order_id, "Mã chỉ định không hợp lệ.")
        rid = _uuid(room_id, "Mã phòng không hợp lệ.")
        payload = {
            "order_id": oid,
            "room_id": rid,
            "expected_version": expected_version,
        }
        async with self._pool.acquire() as conn, conn.transaction():
            vid = await self._visit_of(conn, "service_order", cid, oid)
            await self._lock_visit(conn, cid, vid)
            cached = await self._receipt_get(
                conn, identity, "dispatch.assign", idempotency_key, payload
            )
            if cached is not None:
                return cached
            o = await conn.fetchrow(
                """
                SELECT exec_status, source, authorized_by::text AS authorized_by,
                       hold_until_round, node_code, service_code, service_name,
                       version, selection_status
                  FROM service_order
                 WHERE clinic_id = $1::uuid AND id = $2::uuid
                   FOR UPDATE
                """,
                cid,
                oid,
            )
            assert o is not None
            if o["selection_status"] is not None:
                # Lifecycle v1 (Slice 4 §D): chỉ định mới chỉ xếp phòng qua
                # AssignServiceRoom — sau khi khách chọn, đủ tài chính, đúng
                # routing_revision. Đường cũ không có revision để đối chiếu, nên
                # từ chối thay vì đoán (không lấy `version` thay revision).
                raise LuotKhamConflictError(
                    "LIFECYCLE_ROUTING_REQUIRED",
                    "Chỉ định này điều phối bằng lệnh xếp phòng mới"
                    " (AssignServiceRoom).",
                )
            if expected_version is not None and o["version"] != expected_version:
                raise LuotKhamConflictError(
                    "STALE_VERSION",
                    "Chỉ định vừa được người khác cập nhật — tải lại màn hình.",
                )
            flow = await self._lock_flow(conn, cid, vid)
            closed = {
                int(r["round_no"])
                for r in await conn.fetch(
                    "SELECT round_no FROM review_round"
                    " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid AND status"
                    " = 'closed'",
                    cid,
                    vid,
                )
            }
            code = rules.dispatch_block(
                exec_status=o["exec_status"],
                source=o["source"],
                authorized_by=o["authorized_by"],
                plan_applied=False,
                route_decision=flow["route_decision"],
                vitals_recorded=flow["vitals_status"] == "recorded",
                hold_until_round=o["hold_until_round"],
                closed_rounds=closed,
            )
            if code:
                raise LuotKhamConflictError(code, _CAU_CHAN_DIEU_PHOI[code])
            version = await self._gan_phong(
                conn, identity, vid=vid, oid=oid, rid=rid, o=o
            )
            result = {"ok": True, "order_id": oid, "version": version}
            await self._receipt_put(
                conn, identity, "dispatch.assign", idempotency_key, payload, oid, result
            )
        return result

    async def _gan_phong(
        self,
        conn: asyncpg.Connection,
        identity: StaffIdentity,
        *,
        vid: str,
        oid: str,
        rid: str,
        o: asyncpg.Record,
    ) -> int:
        """Đặt một chỉ định (đã qua luật chặn) vào hàng chờ của một phòng."""
        from clinicai.services.service_routing_service import (
            cau_phong_khong_lam,
            phong_gan_dich_vu,
        )

        cid = identity.clinic_id
        # Cùng luật `phong_lam_duoc` với Routing v1 (30/09/2026): dịch vụ gắn
        # phòng riêng thì chỉ các phòng ấy.
        serves = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM clinic_room r
                 WHERE r.clinic_id = $1::uuid AND r.id = $2::uuid
                   AND phong_lam_duoc(r.clinic_id, r.id, $3, $4)
                   AND r.is_active AND r.accepting)
            """,
            cid,
            rid,
            o["node_code"],
            o["service_code"],
        )
        if not serves:
            raise LuotKhamConflictError(
                "ROOM_NOT_SERVING",
                cau_phong_khong_lam(
                    o["service_name"],
                    await phong_gan_dich_vu(conn, cid, o["service_code"]),
                ),
            )
        if o["exec_status"] == "assigned":
            dang_goi = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1 FROM queue_entry
                     WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                       AND ref_id = $3::uuid AND reason = 'SERVICE'
                       AND status IN ('called', 'serving'))
                """,
                cid,
                vid,
                oid,
            )
            if dang_goi:
                # Phòng cũ đã gọi/đang làm: đổi phòng lúc này là khách đứng
                # giữa hai phòng cùng gọi tên mình.
                raise LuotKhamConflictError(
                    "ROOM_ALREADY_CALLED",
                    "Phòng hiện tại đã gọi khách vào — không chuyển phòng được nữa.",
                )
            await conn.execute(
                """
                UPDATE queue_entry
                   SET room_id = $4::uuid, version = version + 1, updated_at = now()
                 WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                    AND ref_id = $3::uuid
                   AND reason = 'SERVICE' AND status NOT IN ('done', 'left',
                      'cancelled')
                """,
                cid,
                vid,
                oid,
                rid,
            )
        else:
            await self._enqueue(
                conn,
                clinic_id=cid,
                visit_id=vid,
                lane="ROOM",
                reason="SERVICE",
                ref_id=oid,
                room_id=rid,
            )
        version = await conn.fetchval(
            """
            UPDATE service_order
               SET exec_status = 'assigned', room_id = $3::uuid,
                  assigned_by = $4::uuid,
                   assigned_at = now(), version = version + 1, updated_at = now()
             WHERE clinic_id = $1::uuid AND id = $2::uuid
            RETURNING version
            """,
            cid,
            oid,
            rid,
            identity.staff_id,
        )
        await self._cap_nhat_vi_tri(conn, identity.clinic_id, vid)
        await record_event(
            conn,
            event_type="dispatch.assigned",
            aggregate_type="visit",
            aggregate_id=vid,
            identity=identity,
            origin=ORIGIN,
            payload={"visit_id": vid, "order_id": oid, "room_id": rid},
        )
        return int(version)

    async def _tu_xep_phong(
        self, conn: asyncpg.Connection, identity: StaffIdentity, vid: str
    ) -> list[str]:
        """Chỉ định vừa duyệt TỰ vào hàng chờ phòng làm được việc ấy.

        Notion "Kế hoạch v1.0.0", vai Trưởng ca: *"Ngay khi chỉ định, hệ thống sẽ
        tự phân bổ người bệnh về các phòng dựa trên tình trạng thực tế"*.

        Chọn phòng: có người đứng trong lịch HÔM NAY trước, rồi phòng ít người
        chờ nhất. Chỉ định nào luật chặn (chưa đo huyết áp, dặn làm sau khi đọc
        kết quả…) hoặc không phòng nào làm được thì ĐỂ NGUYÊN "đã duyệt" — trưởng
        ca thấy và xếp tay. Không bao giờ ném lỗi làm hỏng lệnh duyệt.
        """
        from clinicai.services.service_routing_service import (
            co_so_cua_luot,
            eligible_rooms,
            rank_rooms,
        )

        cid = identity.clinic_id
        flow = await self._lock_flow(conn, cid, vid)
        closed = {
            int(r["round_no"])
            for r in await conn.fetch(
                "SELECT round_no FROM review_round"
                " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid AND status"
                " = 'closed'",
                cid,
                vid,
            )
        }
        orders = await conn.fetch(
            """
            SELECT id::text AS id, exec_status, source,
                   authorized_by::text AS authorized_by, hold_until_round,
                   node_code, service_code, service_name, version
              FROM service_order o
             WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
               AND exec_status = 'authorized'
               -- Lifecycle v1 (CHECKPOINT §1): chỉ định có selection_status chỉ
               -- được xếp phòng SAU khi khách chọn và đủ điều kiện tài chính —
               -- qua lệnh Routing (Slice 4), không tự xếp lúc duyệt. Dòng cũ
               -- (NULL) giữ hành vi cũ.
               AND o.selection_status IS NULL
               -- Đối tác tự lấy mẫu thì khách không xếp hàng ở phòng nào của
               -- phòng khám — việc ấy nằm trên bàn đối tác.
               AND NOT EXISTS (
                   SELECT 1 FROM service_price sp
                    WHERE sp.clinic_id = o.clinic_id
                      AND sp.service_code = o.service_code
                      AND sp.doi_tac_lay_mau)
             ORDER BY created_at, id
               FOR UPDATE
            """,
            cid,
            vid,
        )
        da_xep: list[str] = []
        for o in orders:
            if rules.dispatch_block(
                exec_status=o["exec_status"],
                source=o["source"],
                authorized_by=o["authorized_by"],
                plan_applied=False,
                route_decision=flow["route_decision"],
                vitals_recorded=flow["vitals_status"] == "recorded",
                hold_until_round=o["hold_until_round"],
                closed_rounds=closed,
            ):
                continue
            # Cùng luật gợi ý với Routing v1 (EligibleRoomQuery + advisor theo
            # luật): chỉ dòng CŨ (selection_status NULL) mới tự xếp ở đây.
            xep = rank_rooms(
                await eligible_rooms(
                    conn,
                    cid,
                    o["node_code"],
                    await co_so_cua_luot(conn, cid, visit_id=vid),
                    tru_luot=vid,
                    service_code=o["service_code"],
                    dung_chuc_nang=True,
                )
            )
            rid = xep[0]["room_id"] if xep else None
            if rid is None:
                continue
            await self._gan_phong(conn, identity, vid=vid, oid=o["id"], rid=rid, o=o)
            da_xep.append(o["id"])
        return da_xep

    # ------------------------------------------------------------------
    # Kết quả: bác sĩ duyệt theo TỪNG chỉ định
    # ------------------------------------------------------------------

    async def ket_qua_cho_duyet(self, *args: Any, **kwargs: Any) -> Any:
        """Nay ở `luot_kham_doc.BangLuotKham` (bóc 24/09/2026)."""
        return await BangLuotKham(self._pool).ket_qua_cho_duyet(*args, **kwargs)

    async def duyet_ket_qua(
        self,
        *,
        order_id: str,
        danh_gia: str | None,
        identity: StaffIdentity,
    ) -> dict[str, Any]:
        """Bác sĩ đánh giá + PHÊ DUYỆT CHO GỬI kết quả của một chỉ định.

        Notion v1.0.0: *"Dưới kết quả xét nghiệm sẽ có nút Phê duyệt cho gửi và
        chỗ ghi Đánh giá của bác sĩ"*. Duyệt xong thì mọi tệp của chỉ định ấy
        được phép gửi — CSKH thấy "Đã có kết quả".
        """
        cid = identity.clinic_id
        oid = _uuid(order_id, "Mã chỉ định không hợp lệ.")
        ghi = (danh_gia or "").strip() if isinstance(danh_gia, str) else ""
        if len(ghi) > 5000:
            raise ValidationError("Đánh giá quá dài.")
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(conn, identity, "result.review.approve")
            vid = await self._visit_of(conn, "service_order", cid, oid)
            bac_si_phien = await bac_si_cua_phien(
                conn,
                clinic_id=cid,
                visit_id=vid,
                nguoi_bam=identity.staff_id,
            )
            await kiem_dung_ca(conn, identity, bac_si_phien, visit_id=vid)
            # KẾT QUẢ MUỘN về sau khi bác sĩ đã ký bệnh án (FINALIZED) hay quầy
            # đã đóng lượt vẫn phải duyệt được — đó chính là việc theo dõi.
            # Nên chỉ khoá dòng visit để tuần tự hoá, không đòi lượt còn mở.
            await conn.execute(
                "SELECT 1 FROM visit WHERE clinic_id = $1::uuid AND visit_id ="
                " $2::uuid FOR UPDATE",
                cid,
                vid,
            )
            o = await conn.fetchrow(
                """
                SELECT o.exec_status, o.ket_qua_luc, o.duyet_luc,
                       coalesce(nd.lam_ben_ngoai, false) AS lam_ben_ngoai
                  FROM service_order o
                  LEFT JOIN node_definition nd
                    ON nd.clinic_id = o.clinic_id AND nd.code = o.node_code
                 WHERE o.clinic_id = $1::uuid AND o.id = $2::uuid FOR UPDATE OF o
                """,
                cid,
                oid,
            )
            assert o is not None
            if o["lam_ben_ngoai"]:
                has_hop_le = await conn.fetchval(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM v_tep_ket_qua_hieu_luc t
                         WHERE t.clinic_id = $1::uuid
                           AND t.service_order_id = $2::uuid
                           AND t.xac_nhan_trang_thai = 'HOP_LE'
                    )
                    """,
                    cid,
                    oid,
                )
                if not has_hop_le:
                    raise LuotKhamConflictError(
                        "NO_VALID_RESULT",
                        "Chỉ định ngoài chưa có tệp kết quả được xác nhận "
                        "hợp lệ để duyệt.",
                    )
            if o["duyet_luc"] is not None:
                # Đã duyệt trước đó. Tệp mới gửi SAU lần duyệt không thừa hưởng
                # quyền gửi — bác sĩ bấm duyệt lần nữa thì chỉ mở các tệp ấy,
                # giữ nguyên đánh giá cũ trừ khi ghi đánh giá mới.
                moi = await conn.fetch(
                    """
                    UPDATE tep_ket_qua
                       SET cho_phep_gui_luc = now(),
                           cho_phep_gui_boi_staff_id = $3::uuid
                     WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid
                       AND cho_phep_gui_luc IS NULL AND da_xoa_luc IS NULL
                       AND xac_nhan_trang_thai = 'HOP_LE'
                    RETURNING id::text
                    """,
                    cid,
                    oid,
                    identity.staff_id,
                )
                if not moi:
                    return {"ok": True, "order_id": oid, "already": True}
                if ghi:
                    await conn.execute(
                        """
                        UPDATE service_order
                           SET bac_si_danh_gia = $3,
                               version = version + 1, updated_at = now()
                         WHERE clinic_id = $1::uuid AND id = $2::uuid
                        """,
                        cid,
                        oid,
                        ghi,
                    )
                await record_event(
                    conn,
                    event_type="result.approved",
                    aggregate_type="visit",
                    aggregate_id=vid,
                    identity=identity,
                    origin=ORIGIN,
                    payload={
                        "visit_id": vid,
                        "order_id": oid,
                        "tep_moi": [r["id"] for r in moi],
                    },
                )
                await self._phat_da_duyet(conn, identity, vid, oid, bac_si_phien)
                return {"ok": True, "order_id": oid, "tep_moi": len(moi)}
            if o["ket_qua_luc"] is None and not o["lam_ben_ngoai"]:
                raise LuotKhamConflictError(
                    "NO_RESULT_YET", "Chỉ định này chưa có kết quả để duyệt."
                )
            await conn.execute(
                """
                UPDATE service_order
                   SET duyet_luc = now(), duyet_boi = $3::uuid,
                       bac_si_danh_gia = nullif($4, ''),
                       version = version + 1, updated_at = now()
                 WHERE clinic_id = $1::uuid AND id = $2::uuid
                """,
                cid,
                oid,
                identity.staff_id,
                ghi,
            )
            await conn.execute(
                """
                UPDATE tep_ket_qua
                   SET cho_phep_gui_luc = now(), cho_phep_gui_boi_staff_id = $3::uuid
                 WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid
                   AND cho_phep_gui_luc IS NULL AND da_xoa_luc IS NULL
                   AND xac_nhan_trang_thai = 'HOP_LE'
                """,
                cid,
                oid,
                identity.staff_id,
            )
            # Việc theo dõi "chờ kết quả" của chỉ định này xong khi bác sĩ duyệt.
            await conn.execute(
                """
                UPDATE follow_up_case
                   SET status = 'DONE', closed_at = now(), updated_at = now()
                 WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid
                   AND status = 'OPEN'
                """,
                cid,
                oid,
            )
            await record_event(
                conn,
                event_type="result.approved",
                aggregate_type="visit",
                aggregate_id=vid,
                identity=identity,
                origin=ORIGIN,
                payload={"visit_id": vid, "order_id": oid},
            )
            await self._phat_da_duyet(conn, identity, vid, oid, bac_si_phien)
        return {"ok": True, "order_id": oid}

    @staticmethod
    async def _phat_da_duyet(
        conn: asyncpg.Connection,
        identity: StaffIdentity,
        vid: str,
        oid: str,
        bac_si_id: str | None,
    ) -> None:
        """Duyệt (không bắt buộc — Tuyền 24/09) = đã xem mọi tệp của chỉ định,
        và một dòng `result.reviewed` trên dòng thời gian."""
        await conn.execute(
            "UPDATE tep_ket_qua SET da_xem_luc = now(), da_xem_boi_staff_id = $3::uuid"
            " WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid"
            "   AND da_xem_luc IS NULL AND da_xoa_luc IS NULL",
            identity.clinic_id,
            oid,
            identity.staff_id,
        )
        await conn.execute(
            "UPDATE service_order SET da_xem_ket_qua_luc = now(),"
            "       da_xem_ket_qua_boi = $3::uuid"
            " WHERE clinic_id = $1::uuid AND id = $2::uuid"
            "   AND da_xem_ket_qua_luc IS NULL",
            identity.clinic_id,
            oid,
            identity.staff_id,
        )
        await emit_event(
            conn,
            ten="result.reviewed",
            clinic_id=identity.clinic_id,
            aggregate_id=oid,
            so_ke_tiep=True,
            payload=KetQuaDaDuyet(service_order_id=oid, visit_id=vid),
            boi=nguoi_lam_thay(identity, bac_si_id),
            correlation_id=vid,
        )

    # ------------------------------------------------------------------
    # Đối tác: hai trạng thái "Chờ lấy mẫu" → "Đã lấy mẫu" → (tải kết quả)
    # ------------------------------------------------------------------

    async def viec_doi_tac(self, *args: Any, **kwargs: Any) -> Any:
        """Nay ở `doi_tac_service.DoiTacService` (bóc 24/09/2026)."""
        return await DoiTacService(self._pool).viec_doi_tac(*args, **kwargs)

    async def doi_tac_cho_tai_lieu(self, *args: Any, **kwargs: Any) -> Any:
        """Nay ở `doi_tac_service.DoiTacService` (bóc 24/09/2026)."""
        return await DoiTacService(self._pool).doi_tac_cho_tai_lieu(*args, **kwargs)

    async def doi_tac_da_lay_mau(self, *args: Any, **kwargs: Any) -> Any:
        """Nay ở `doi_tac_service.DoiTacService` (bóc 24/09/2026)."""
        return await DoiTacService(self._pool).doi_tac_da_lay_mau(*args, **kwargs)

    # ------------------------------------------------------------------
    # C8 / C9 — người thực hiện bắt đầu và kết thúc dịch vụ
    # ------------------------------------------------------------------

    async def _order_for_performer(
        self, conn: asyncpg.Connection, identity: StaffIdentity, oid: str
    ) -> asyncpg.Record:
        o = await conn.fetchrow(
            """
            SELECT o.exec_status, o.node_code, o.performed_by::text AS performed_by,
                   n.actor_roles
              FROM service_order o
              JOIN node_definition n
                ON n.clinic_id = o.clinic_id AND n.code = o.node_code
             WHERE o.clinic_id = $1::uuid AND o.id = $2::uuid
               FOR UPDATE OF o
            """,
            identity.clinic_id,
            oid,
        )
        assert o is not None
        duoc = set(o["actor_roles"] or []) | {v.value for v in HO_TRO_PHONG}
        if not set(identity.ds_vai()) & duoc:
            raise SafetyGateError("Vai của bạn không thực hiện được dịch vụ này.")
        return o

    async def start_service(
        self, *, order_id: str, identity: StaffIdentity
    ) -> dict[str, Any]:
        _require(identity, PERFORMER_ROLES, "Vai của bạn không thực hiện dịch vụ.")
        cid = identity.clinic_id
        oid = _uuid(order_id, "Mã chỉ định không hợp lệ.")
        async with self._pool.acquire() as conn, conn.transaction():
            vid = await self._visit_of(conn, "service_order", cid, oid)
            await self._lock_visit(conn, cid, vid)
            o = await self._order_for_performer(conn, identity, oid)
            if (
                o["exec_status"] == "in_progress"
                and o["performed_by"] == identity.staff_id
            ):
                return {"ok": True, "order_id": oid, "already": True}
            if o["exec_status"] != "assigned":
                raise LuotKhamConflictError(
                    "ORDER_NOT_ASSIGNED", "Dịch vụ này chưa được điều phối vào phòng."
                )
            entry = await conn.fetchrow(
                """
                SELECT id::text AS id, status FROM queue_entry
                 WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                    AND ref_id = $3::uuid
                   AND reason = 'SERVICE' AND status NOT IN ('done', 'left',
                      'cancelled')
                   FOR UPDATE
                """,
                cid,
                vid,
                oid,
            )
            if (
                entry is None
                or entry["status"] not in ("waiting", "called")
                or await self._visit_busy(conn, cid, vid)
            ):
                raise LuotKhamConflictError(
                    "PATIENT_BUSY",
                    "Khách đang ở một bước khác, chưa làm dịch vụ này được.",
                )
            await conn.execute(
                """
                UPDATE service_order
                   SET exec_status = 'in_progress', performed_by = $3::uuid,
                      started_at = now(),
                       version = version + 1, updated_at = now()
                 WHERE clinic_id = $1::uuid AND id = $2::uuid
                """,
                cid,
                oid,
                identity.staff_id,
            )
            await conn.execute(
                "UPDATE queue_entry SET status = 'serving', serving_at = now(),"
                " version = version + 1, updated_at = now()"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                cid,
                entry["id"],
            )
            await self._block_others(conn, cid, vid, entry["id"])
            await self._cap_nhat_vi_tri(conn, identity.clinic_id, vid)
            await record_event(
                conn,
                event_type="service.started",
                aggregate_type="visit",
                aggregate_id=vid,
                identity=identity,
                origin=ORIGIN,
                payload={"visit_id": vid, "order_id": oid},
            )
        return {"ok": True, "order_id": oid}

    async def complete_service(
        self,
        *,
        order_id: str,
        performed: bool,
        reason: str | None,
        result_note: str | None,
        identity: StaffIdentity,
    ) -> dict[str, Any]:
        _require(identity, PERFORMER_ROLES, "Vai của bạn không thực hiện dịch vụ.")
        cid = identity.clinic_id
        oid = _uuid(order_id, "Mã chỉ định không hợp lệ.")
        ly_do = (reason or "").strip() if isinstance(reason, str) else ""
        ghi = (result_note or "").strip() if isinstance(result_note, str) else ""
        if not performed and not ly_do:
            raise ValidationError("Ghi lý do không thực hiện được dịch vụ.")
        if len(ghi) > 20000 or len(ly_do) > 2000:
            raise ValidationError("Nội dung quá dài.")
        async with self._pool.acquire() as conn, conn.transaction():
            vid = await self._visit_of(conn, "service_order", cid, oid)
            await self._lock_visit(conn, cid, vid)
            o = await self._order_for_performer(conn, identity, oid)
            if o["exec_status"] != "in_progress":
                raise LuotKhamConflictError(
                    "ORDER_NOT_IN_PROGRESS", "Dịch vụ này chưa bắt đầu hoặc đã xong."
                )
            await conn.execute(
                """
                UPDATE service_order
                   SET exec_status = $3, finished_at = now(),
                       -- Bác sĩ bấm Xong ⇒ bác sĩ là người thực hiện, kể cả khi
                       -- điều dưỡng đi kèm đã bấm Bắt đầu.
                       performed_by = CASE WHEN $6 THEN $7::uuid
                                           ELSE performed_by END,
                       result_note = nullif($4, ''),
                       ket_qua_luc = CASE WHEN nullif($4, '') IS NOT NULL
                                          THEN coalesce(ket_qua_luc, now())
                                          ELSE ket_qua_luc END,
                          not_performed_reason = nullif($5, ''),
                       version = version + 1, updated_at = now()
                 WHERE clinic_id = $1::uuid AND id = $2::uuid
                """,
                cid,
                oid,
                "performed" if performed else "not_performed",
                ghi,
                ly_do,
                bool(set(identity.ds_vai()) & set(o["actor_roles"] or [])),
                identity.staff_id,
            )
            if not performed:
                # Không làm được thì sẽ không có kết quả: việc theo dõi "chờ kết
                # quả" của chỉ định này huỷ (lý do nằm ở not_performed_reason),
                # không để mồ côi. Bác sĩ quyết tiếp qua vòng đọc / tái khám.
                await conn.execute(
                    """
                    UPDATE follow_up_case
                       SET status = 'CANCELLED', closed_at = now(),
                           updated_at = now()
                     WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid
                       AND status = 'OPEN'
                    """,
                    cid,
                    oid,
                )
            await conn.execute(
                """
                UPDATE queue_entry
                   SET status = 'done', done_at = now(), version = version + 1,
                      updated_at = now()
                 WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                    AND ref_id = $3::uuid
                   AND reason = 'SERVICE' AND status NOT IN ('done', 'left',
                      'cancelled')
                """,
                cid,
                vid,
                oid,
            )
            await self._release_blocked(conn, cid, vid)
            await self._evaluate_rounds(conn, identity, vid)
            await self._ket_thuc_neu_xong(conn, identity, vid)
            await self._cap_nhat_vi_tri(conn, identity.clinic_id, vid)
            await record_event(
                conn,
                event_type="service.performed"
                if performed
                else "service.not_performed",
                aggregate_type="visit",
                aggregate_id=vid,
                identity=identity,
                origin=ORIGIN,
                payload={"visit_id": vid, "order_id": oid},
            )
        return {"ok": True, "order_id": oid}
