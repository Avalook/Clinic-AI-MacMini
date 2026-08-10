"""Tệp kết quả khám — CSKH tải lên, và đánh dấu đã gửi cho khách.

DoD: *"Cần có chỗ upload kết quả siêu âm & xét nghiệm. Hình ảnh siêu âm gồm ảnh
+ video. Cần gửi được cả video cho bệnh nhân."*

BA ĐIỀU THI HÀNH Ở ĐÂY, KHÔNG PHẢI Ở GIAO DIỆN — cùng lý do với media_service:

  1. TÊN TỆP DO HỆ THỐNG ĐẶT. Tên client gửi có thể là "../../../etc/passwd";
     nó chỉ được giữ lại làm nhãn hiển thị.
  2. KIỂU KIỂM BẰNG NỘI DUNG, không bằng đuôi. Một tệp "kq.mp4" chứa HTML sẽ
     được trình duyệt chạy nếu phục vụ sai kiểu.
  3. ĐỌC LẠI PHẢI CHỨNG MINH QUYỀN. Đoán một UUID không được phép đủ để mở tệp
     của bệnh nhân khác.

VÀ MỘT ĐIỀU VỀ TRÍ NHỚ. Video đọc theo LUỒNG, không nạp cả tệp vào RAM: container
API giới hạn 1GB, và ba người cùng xem một video 80MB theo kiểu `read_bytes()`
là 240MB tức thời — đủ để tiến trình bị giết giữa giờ khám.
"""

from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path
from typing import Any

import asyncpg
import structlog

from clinicai.api.exceptions import NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.services.media_service import (
    KET_QUA_VIDEO_UPLOAD_ENABLED,
    MAX_BYTES_THEO_LOAI,
    MEDIA_ROOT,
    duong_dan_ket_qua,
    ket_qua_patient_lock_key,
    sniff_ket_qua,
)

logger = structlog.get_logger()

# Trần tích luỹ theo clinic và khoảng trống phải giữ lại cho database/host.
# Có thể nâng có chủ đích bằng env sau khi kiểm tra backup và dung lượng thật.
MEDIA_CLINIC_QUOTA_BYTES = int(
    os.environ.get("MEDIA_CLINIC_QUOTA_BYTES", 5 * 1024 * 1024 * 1024)
)
MEDIA_MIN_FREE_BYTES = int(
    os.environ.get("MEDIA_MIN_FREE_BYTES", 5 * 1024 * 1024 * 1024)
)

KENH_GUI_HOP_LE = frozenset({"ZALO", "SMS", "TRUC_TIEP", "EMAIL"})


class TepKetQuaService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def tai_len(
        self,
        *,
        identity: StaffIdentity,
        clinic_patient_id: str,
        data: bytes,
        ten_hien_thi: str | None = None,
        appointment_id: str | None = None,
    ) -> dict[str, Any]:
        """Nhận một tệp kết quả và cất nó lên đĩa."""
        if not data:
            raise ValidationError("Tệp rỗng.")
        mime, ext, loai = sniff_ket_qua(data)
        if loai == "VIDEO" and not KET_QUA_VIDEO_UPLOAD_ENABLED:
            raise ValidationError(
                "Video kết quả chưa được bật. Hiện chỉ nhận ảnh hoặc phiếu PDF."
            )
        tran = MAX_BYTES_THEO_LOAI[loai]
        if len(data) > tran:
            raise ValidationError(
                f"Tệp quá lớn ({len(data) // 1024 // 1024}MB). "
                f"Tối đa {tran // 1024 // 1024}MB cho loại này."
            )

        async with self._pool.acquire() as conn, conn.transaction():
            ok = await conn.fetchval(
                "SELECT 1 FROM public.patient "
                " WHERE clinic_patient_id = $1::uuid AND clinic_id = $2::uuid",
                clinic_patient_id,
                identity.clinic_id,
            )
            if not ok:
                raise NotFoundError("Không tìm thấy khách hàng này.")
            if appointment_id:
                thuoc_ve = await conn.fetchval(
                    "SELECT 1 FROM public.appointment"
                    " WHERE id = $1::uuid AND clinic_id = $2::uuid"
                    "   AND clinic_patient_id = $3::uuid",
                    appointment_id,
                    identity.clinic_id,
                    clinic_patient_id,
                )
                if not thuoc_ve:
                    raise ValidationError("Lịch hẹn không phải của khách này.")

            # Serialize against TRA_KQ's evidence-check + insert. Otherwise an
            # upload can slip in immediately after the user closes the task and
            # remain pending forever because the current view only sees TRA_KQ.
            await conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended($1, 0))",
                ket_qua_patient_lock_key(
                    clinic_id=identity.clinic_id,
                    clinic_patient_id=clinic_patient_id,
                ),
            )
            da_xac_nhan_tra = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1
                      FROM public.tuong_tac_cskh i
                     WHERE i.clinic_id = $1::uuid
                       AND i.clinic_patient_id = $2::uuid
                       AND i.loai = 'TRA_KQ'
                       AND i.huy_luc IS NULL
                       AND i.xay_ra_luc >= COALESCE((
                           SELECT max(COALESCE(
                               r.reviewed_at, r.result_received_at, r.created_at
                           ))
                             FROM public.lab_result r
                            WHERE r.clinic_id = $1::uuid
                              AND r.clinic_patient_id = $2::uuid
                              AND r.result_value IS NOT NULL
                              AND (NOT r.requires_doctor_review
                                   OR r.reviewed_at IS NOT NULL)
                       ), '-infinity'::timestamptz)
                )
                """,
                identity.clinic_id,
                clinic_patient_id,
            )
            if da_xac_nhan_tra:
                raise ValidationError(
                    "Việc này đã xác nhận trả kết quả. Hoàn tác mốc trả kết quả "
                    "trước khi tải thêm tệp, hoặc ghi nhận kết quả mới trước."
                )

            # Serialize quota checks for the same clinic. Without this lock,
            # several concurrent uploads can all observe the same old total and
            # collectively jump far past the cap.
            await conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended($1, 0))",
                f"tep-ket-qua:{identity.clinic_id}",
            )
            da_dung = int(
                await conn.fetchval(
                    "SELECT coalesce(sum(so_byte), 0)::bigint "
                    "FROM public.tep_ket_qua WHERE clinic_id = $1::uuid",
                    identity.clinic_id,
                )
                or 0
            )
            if da_dung + len(data) > MEDIA_CLINIC_QUOTA_BYTES:
                raise ValidationError(
                    "Phòng khám đã chạm hạn mức lưu trữ kết quả. "
                    "Báo kỹ thuật kiểm tra và mở rộng dung lượng trước khi tải thêm."
                )

            path, key = duong_dan_ket_qua(
                clinic_id=identity.clinic_id,
                clinic_patient_id=clinic_patient_id,
                ext=ext,
            )
            path.parent.mkdir(parents=True, exist_ok=True)
            if shutil.disk_usage(MEDIA_ROOT).free - len(data) < MEDIA_MIN_FREE_BYTES:
                raise ValidationError(
                    "Máy chủ không còn đủ dung lượng trống an toàn để lưu tệp. "
                    "Báo kỹ thuật dọn hoặc mở rộng ổ đĩa."
                )
            # Ghi tệp tạm rồi đổi tên: một lần ghi bị cắt giữa chừng (hết đĩa,
            # mất điện) để lại tệp tạm, không để lại một tệp hỏng mà database
            # vẫn khai là có. Đuôi `.tmp` cũng là thứ bản sao lưu bỏ qua.
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_bytes(data)
            tmp.replace(path)
            path.chmod(0o600)

            row_id = await conn.fetchval(
                """
                INSERT INTO public.tep_ket_qua
                    (clinic_id, clinic_patient_id, appointment_id, khoa,
                     ten_hien_thi, loai_tep, mime, so_byte, sha256,
                     tai_len_boi_staff_id)
                VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6, $7, $8, $9,
                        $10::uuid)
                RETURNING id::text
                """,
                identity.clinic_id,
                clinic_patient_id,
                appointment_id,
                key,
                (ten_hien_thi or "").strip()[:200] or None,
                loai,
                mime,
                len(data),
                hashlib.sha256(data).hexdigest(),
                identity.staff_id,
            )

        logger.info(
            "tep_ket_qua_tai_len",
            loai=loai,
            mime=mime,
            bytes=len(data),
            by_staff_id=identity.staff_id,
        )
        return {"ok": True, "id": row_id, "loai_tep": loai, "so_byte": len(data)}

    async def danh_sach(
        self, *, identity: StaffIdentity, clinic_patient_id: str
    ) -> list[dict[str, Any]]:
        """Tệp kết quả của một khách, mới nhất trước."""
        rows = await self._pool.fetch(
            """
            SELECT t.id::text, t.ten_hien_thi, t.loai_tep, t.mime, t.so_byte,
                   t.tai_len_luc, t.gui_luc, t.gui_kenh,
                   s.full_name AS tai_len_boi,
                   g.full_name AS gui_boi
              FROM public.tep_ket_qua t
              LEFT JOIN public.staff s ON s.id = t.tai_len_boi_staff_id
              LEFT JOIN public.staff g ON g.id = t.gui_boi_staff_id
             WHERE t.clinic_id = $1::uuid AND t.clinic_patient_id = $2::uuid
             ORDER BY t.tai_len_luc DESC
             LIMIT 200
            """,
            identity.clinic_id,
            clinic_patient_id,
        )
        return [dict(r) for r in rows]

    async def duong_dan_de_doc(
        self, *, identity: StaffIdentity, tep_id: str
    ) -> tuple[Path, str, int, str]:
        """(đường dẫn, mime, số byte, tên hiển thị) — sau khi chứng minh quyền.

        Trả về ĐƯỜNG DẪN chứ không phải nội dung: video phải đi theo luồng, và
        một hàm trả `bytes` là một hàm buộc mọi lời gọi phải nạp cả tệp vào RAM.
        """
        row = await self._pool.fetchrow(
            "SELECT khoa, mime, so_byte, ten_hien_thi FROM public.tep_ket_qua"
            " WHERE id = $1::uuid AND clinic_id = $2::uuid",
            tep_id,
            identity.clinic_id,
        )
        if row is None:
            raise NotFoundError("Không tìm thấy tệp này.")

        khoa = row["khoa"]
        # Hai chốt, giữ cả hai. Câu truy vấn trên đã lọc theo clinic_id, nhưng
        # backend chạy bằng service role và BỎ QUA RLS — nên một lần sửa sau
        # này làm hỏng bộ lọc sẽ biến đây thành lỗ thật.
        if not khoa.startswith(f"{identity.clinic_id}/"):
            raise ValidationError("Tệp không thuộc phòng khám này.")
        path = (MEDIA_ROOT / khoa).resolve()
        if not path.is_relative_to(MEDIA_ROOT.resolve()):
            raise ValidationError("Đường dẫn tệp không hợp lệ.")
        if not path.exists():
            raise NotFoundError("Tệp không còn trên máy chủ — báo kỹ thuật.")
        return path, row["mime"], row["so_byte"], row["ten_hien_thi"] or ""

    async def danh_dau_da_gui(
        self, *, identity: StaffIdentity, tep_id: str, kenh: str
    ) -> dict[str, Any]:
        """CSKH xác nhận ĐÃ GỬI tệp này cho khách.

        Tên hàm và nhãn nút đều nói "xác nhận đã gửi", không phải "gửi":
        send_zalo.py luôn trả delivered=False — chưa có kênh nào được nối. Gọi
        nó là "gửi" thì sáu tháng sau sẽ có người tin rằng hệ thống tự gửi và
        không ai gọi cho khách nữa.
        """
        if kenh not in KENH_GUI_HOP_LE:
            raise ValidationError(f"Kênh gửi không hợp lệ: {kenh!r}.")
        row = await self._pool.fetchrow(
            """
            UPDATE public.tep_ket_qua
               SET gui_luc = now(), gui_boi_staff_id = $1::uuid, gui_kenh = $2
             WHERE id = $3::uuid AND clinic_id = $4::uuid AND gui_luc IS NULL
            RETURNING id::text
            """,
            identity.staff_id,
            kenh,
            tep_id,
            identity.clinic_id,
        )
        if row is None:
            raise NotFoundError("Không tìm thấy tệp này, hoặc nó đã được gửi rồi.")
        return {"ok": True}
