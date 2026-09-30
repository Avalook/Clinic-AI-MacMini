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

import asyncio
import errno
import hashlib
import io
import os
import shutil
import zipfile
from pathlib import Path
from typing import IO, Any

import asyncpg
import structlog

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.services.audit import record_event
from clinicai.services.bao_ket_qua_ve import bao_ket_qua_ve
from clinicai.services.media_service import (
    KET_QUA_VIDEO_UPLOAD_ENABLED,
    MEDIA_ROOT,
    duong_dan_ket_qua,
    ket_qua_patient_lock_key,
    kiem_kho_da_gan,
    sniff_ket_qua,
    vuot_tran,
)
from clinicai.services.nhan_tep_luong import TepDaNhan

logger = structlog.get_logger()

# Trần tích luỹ theo clinic và khoảng trống phải giữ lại cho database/host.
# Có thể nâng có chủ đích bằng env sau khi kiểm tra backup và dung lượng thật.
#: 0 = KHÔNG giới hạn tổng dung lượng (Tuyền 16/09/2026). Đặt số dương qua env
#: nếu sau này cần hạn mức.
MEDIA_CLINIC_QUOTA_BYTES = int(os.environ.get("MEDIA_CLINIC_QUOTA_BYTES", "0") or 0)

_KHUC_GHI = 4 * 1024 * 1024
_MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _chep_luong(nguon: IO[bytes], dich: Path) -> tuple[int, str]:
    """Chép luồng → tệp theo từng khúc, trả (số byte, sha256). Chạy trong thread."""
    h = hashlib.sha256()
    so_byte = 0
    with dich.open("wb") as ra:
        while True:
            khuc = nguon.read(_KHUC_GHI)
            if not khuc:
                break
            ra.write(khuc)
            h.update(khuc)
            so_byte += len(khuc)
    return so_byte, h.hexdigest()


def _loai_tai_lieu(duong: Path) -> str | None:
    """DOCX/XLSX thật (mở ZIP xem thư mục bên trong); None = không phải."""
    try:
        with zipfile.ZipFile(duong) as z:
            ten = z.namelist()
    except zipfile.BadZipFile:
        return None
    if any(t.startswith("word/") for t in ten):
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if any(t.startswith("xl/") for t in ten):
        return _MIME_XLSX
    return None


MEDIA_MIN_FREE_BYTES = int(
    os.environ.get("MEDIA_MIN_FREE_BYTES", 5 * 1024 * 1024 * 1024)
)

KENH_GUI_HOP_LE = frozenset({"ZALO", "SMS", "TRUC_TIEP", "EMAIL"})

#: Ai được cho phép gửi tệp kết quả cho khách (Tuyền chốt 15/09/2026).
BAC_SI_CHO_PHEP_GUI = frozenset({ClinicRole.DOCTOR, ClinicRole.ULTRASOUND_DOCTOR})


#: Vai mà tệp họ tải lên ĐƯỢC PHÉP GỬI NGAY, không chờ ai duyệt lại.
#:
#: Luật "bác sĩ cho phép gửi" (15/09/2026) sinh ra cho đường CSKH: người không
#: đọc được kết quả tải một tệp lên, nên phải có bác sĩ xem trước khi nó tới tay
#: khách. Khi chính bác sĩ là người tải lên thì bước ấy đã xong rồi — bắt bác sĩ
#: tự duyệt tệp của mình chỉ tạo ra một hàng chờ giả và dạy người ta bấm cho
#: xong. Thư ký, điều dưỡng, CSKH, lễ tân tải lên thì VẪN chờ bác sĩ.
TU_CHO_PHEP_GUI: frozenset[ClinicRole] = BAC_SI_CHO_PHEP_GUI


NORMAL_READ_ROLES: frozenset[ClinicRole] = frozenset(
    {
        ClinicRole.CSKH,
        ClinicRole.RECEPTION,
        ClinicRole.MANAGEMENT,
        ClinicRole.TRUONG_CA,
        ClinicRole.DOCTOR,
        ClinicRole.ULTRASOUND_DOCTOR,
        ClinicRole.TKYK,
        ClinicRole.NURSE_ULTRASOUND,
    }
)


async def co_quyen_xac_nhan(
    conn: asyncpg.Connection | asyncpg.Pool,
    identity: StaffIdentity,
) -> bool:
    """Kiểm tra xem identity có capability ket_qua.xac_nhan hợp lệ hay không.

    Quy tắc an toàn:
    1. PARTNER không bao giờ có quyền xác nhận -> False.
    2. staff_id phải có active clinic_membership tại đúng identity.clinic_id.
    3. staff_id KHÔNG ĐƯỢC có active membership tại bất kỳ clinic nào
       khác (fail-closed).
    4. staff_id phải có capability 'ket_qua.xac_nhan' trong staff_capability.
    """
    if identity.co_vai([ClinicRole.PARTNER]):
        return False

    row = await conn.fetchrow(
        """
        SELECT
            EXISTS (
                SELECT 1 FROM public.staff_capability sc
                 WHERE sc.staff_id = $1::uuid
                   AND sc.capability = 'ket_qua.xac_nhan'
            ) AS co_capability,
            EXISTS (
                SELECT 1 FROM public.clinic_membership cm
                 WHERE cm.staff_id = $1::uuid
                   AND cm.clinic_id = $2::uuid
                   AND cm.is_active = true
            ) AS co_membership_hien_tai,
            (
                SELECT count(DISTINCT cm.clinic_id)::int
                  FROM public.clinic_membership cm
                 WHERE cm.staff_id = $1::uuid
                   AND cm.is_active = true
            ) AS so_clinic_active
        """,
        identity.staff_id,
        identity.clinic_id,
    )
    if not row:
        return False
    return bool(
        row["co_capability"]
        and row["co_membership_hien_tai"]
        and row["so_clinic_active"] == 1
    )


async def kiem_tra_quyen_xac_nhan(
    conn: asyncpg.Connection | asyncpg.Pool,
    *,
    identity: StaffIdentity,
) -> None:
    """Kiểm tra quyền xác nhận kết quả (Blocker 1 - Capability ket_qua.xac_nhan).

    Quy tắc an toàn:
    1. PARTNER không bao giờ có quyền xác nhận.
    2. staff_id phải có capability 'ket_qua.xac_nhan' trong staff_capability.
    3. staff_id phải có active clinic_membership tại đúng identity.clinic_id.
    4. staff_id KHÔNG ĐƯỢC có active membership tại bất kỳ clinic nào khác.
       Nếu nhân sự thuộc nhiều clinic -> FAIL-CLOSED (vì staff_capability là bảng
       toàn cục không có clinic_id, chưa đủ dữ liệu phân quyền theo từng clinic).
    """
    if identity.co_vai([ClinicRole.PARTNER]):
        raise SafetyGateError("Đối tác không có quyền xác nhận kết quả.")

    row = await conn.fetchrow(
        """
        SELECT
            EXISTS (
                SELECT 1 FROM public.staff_capability sc
                 WHERE sc.staff_id = $1::uuid
                   AND sc.capability = 'ket_qua.xac_nhan'
            ) AS co_capability,
            EXISTS (
                SELECT 1 FROM public.clinic_membership cm
                 WHERE cm.staff_id = $1::uuid
                   AND cm.clinic_id = $2::uuid
                   AND cm.is_active = true
            ) AS co_membership_hien_tai,
            (
                SELECT count(DISTINCT cm.clinic_id)::int
                  FROM public.clinic_membership cm
                 WHERE cm.staff_id = $1::uuid
                   AND cm.is_active = true
            ) AS so_clinic_active
        """,
        identity.staff_id,
        identity.clinic_id,
    )
    if not row or not row["co_capability"]:
        raise SafetyGateError(
            "Nhân sự chưa được cấp quyền xác nhận kết quả (ket_qua.xac_nhan)."
        )
    if not row["co_membership_hien_tai"]:
        raise SafetyGateError("Nhân sự không có active membership tại phòng khám này.")
    if row["so_clinic_active"] > 1:
        raise SafetyGateError(
            "Nhân sự thuộc nhiều phòng khám — tạm khóa quyền xác nhận kết quả "
            "để đảm bảo an toàn phân quyền (fail-closed)."
        )


class TepKetQuaService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def tai_len(
        self,
        *,
        identity: StaffIdentity,
        clinic_patient_id: str,
        data: bytes | None = None,
        nguon: IO[bytes] | None = None,
        tep_da_nhan: TepDaNhan | None = None,
        ten_hien_thi: str | None = None,
        appointment_id: str | None = None,
        service_order_id: str | None = None,
    ) -> dict[str, Any]:
        """Nhận một tệp kết quả và cất nó lên đĩa.

        `service_order_id`: tệp là kết quả của CHỈ ĐỊNH nào (siêu âm, xét
        nghiệm…). Có nó thì kết quả đi đúng đường duyệt của chỉ định ấy; thiếu
        nó thì tệp chỉ gắn với khách + lượt khám như trước.
        """
        if tep_da_nhan is not None:
            so_byte_khai = tep_da_nhan.so_byte
            dau = tep_da_nhan.dau
        else:
            if nguon is None:
                nguon = io.BytesIO(data or b"")
            nguon.seek(0, 2)
            so_byte_khai = nguon.tell()
            nguon.seek(0)
            dau = nguon.read(8192)
            nguon.seek(0)
        if so_byte_khai == 0:
            raise ValidationError("Tệp rỗng.")
        mime, ext, loai = sniff_ket_qua(dau)
        if loai == "VIDEO" and not KET_QUA_VIDEO_UPLOAD_ENABLED:
            raise ValidationError(
                "Video kết quả chưa được bật. Hiện chỉ nhận ảnh hoặc phiếu PDF."
            )
        tran = vuot_tran(loai, so_byte_khai)
        if tran is not None:
            raise ValidationError(
                f"Tệp quá lớn. Tối đa {tran // 1024 // 1024}MB cho loại này."
            )
        is_external = False
        async with self._pool.acquire() as conn:
            ok = await conn.fetchval(
                "SELECT 1 FROM public.patient "
                " WHERE clinic_patient_id = $1::uuid AND clinic_id = $2::uuid",
                clinic_patient_id,
                identity.clinic_id,
            )
            if not ok:
                raise NotFoundError("Không tìm thấy khách hàng này.")
            if service_order_id:
                cua_chi_dinh = await conn.fetchrow(
                    "SELECT v.clinic_patient_id::text AS clinic_patient_id,"
                    "       v.appointment_id::text AS appointment_id,"
                    "       coalesce(nd.lam_ben_ngoai, false) AS lam_ben_ngoai,"
                    "       o.node_code"
                    "  FROM public.service_order o"
                    "  JOIN public.visit v"
                    "    ON v.visit_id = o.visit_id AND v.clinic_id = o.clinic_id"
                    "  LEFT JOIN public.node_definition nd"
                    "    ON nd.clinic_id = o.clinic_id AND nd.code = o.node_code"
                    " WHERE o.id = $1::uuid AND o.clinic_id = $2::uuid"
                    "   AND o.exec_status NOT IN ('draft', 'cancelled')",
                    service_order_id,
                    identity.clinic_id,
                )
                if (
                    cua_chi_dinh is None
                    or cua_chi_dinh["clinic_patient_id"] != clinic_patient_id
                ):
                    raise ValidationError("Chỉ định này không phải của khách này.")
                # Bác sĩ không upload kết quả thủ thuật (điều dưỡng thao tác).
                from clinicai.services.luot_kham_service import (
                    PROCEDURE_NODES,
                )

                if (
                    cua_chi_dinh["node_code"] in PROCEDURE_NODES
                    and identity.co_vai({ClinicRole.DOCTOR})
                    and not identity.co_vai(
                        {ClinicRole.NURSE_ULTRASOUND, ClinicRole.MANAGEMENT}
                    )
                ):
                    raise SafetyGateError(
                        "Bác sĩ chỉ xem tại phòng thủ thuật. "
                        "Điều dưỡng thực hiện thao tác vận hành."
                    )
                if identity.co_vai(
                    {ClinicRole.NURSE_ULTRASOUND}
                ) and not identity.co_vai({ClinicRole.MANAGEMENT}):
                    has_node = await conn.fetchval(
                        """
                        SELECT 1 FROM public.staff_node
                         WHERE clinic_id = $1::uuid
                           AND staff_id = $2::uuid
                           AND node_code = $3
                        """,
                        identity.clinic_id,
                        identity.staff_id,
                        cua_chi_dinh["node_code"],
                    )
                    if not has_node:
                        raise SafetyGateError(
                            "Bạn chưa được phân công vận hành bước này. "
                            "Vui lòng liên hệ quản lý để cấu hình."
                        )
                appointment_id = appointment_id or cua_chi_dinh["appointment_id"]
                is_external = bool(cua_chi_dinh["lam_ben_ngoai"])
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

        kiem_kho_da_gan()
        path, key = duong_dan_ket_qua(
            clinic_id=identity.clinic_id,
            clinic_patient_id=clinic_patient_id,
            ext=ext,
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        if shutil.disk_usage(MEDIA_ROOT).free - so_byte_khai < MEDIA_MIN_FREE_BYTES:
            raise ValidationError(
                "Máy chủ không còn đủ dung lượng trống an toàn để lưu tệp. "
                "Báo kỹ thuật dọn hoặc mở rộng ổ đĩa."
            )
        tmp = path.with_suffix(path.suffix + ".tmp")
        try:
            if tep_da_nhan is not None:
                await asyncio.to_thread(os.replace, tep_da_nhan.duong, tmp)
                so_byte, sha = tep_da_nhan.so_byte, tep_da_nhan.sha256
            else:
                assert nguon is not None
                so_byte, sha = await asyncio.to_thread(_chep_luong, nguon, tmp)
        except OSError as loi:
            tmp.unlink(missing_ok=True)
            if loi.errno == errno.ENOSPC:
                raise ValidationError(
                    "Kho lưu trữ đã đầy giữa chừng — tệp CHƯA được lưu. "
                    "Báo kỹ thuật mở rộng dung lượng."
                ) from loi
            raise
        if loai == "TAI_LIEU":
            that = await asyncio.to_thread(_loai_tai_lieu, tmp)
            if that is None:
                tmp.unlink(missing_ok=True)
                raise ValidationError(
                    "Tệp nén không phải tài liệu Word (.docx) hay Excel (.xlsx)."
                )
            mime = that
            if that == _MIME_XLSX:
                ext = ".xlsx"
                path = path.with_suffix(".xlsx")
                key = key.rsplit(".", 1)[0] + ".xlsx"

        try:
            async with self._pool.acquire() as conn, conn.transaction():
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

                if MEDIA_CLINIC_QUOTA_BYTES > 0:
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
                    if da_dung + so_byte_khai > MEDIA_CLINIC_QUOTA_BYTES:
                        raise ValidationError(
                            "Phòng khám đã chạm hạn mức lưu trữ kết quả. "
                            "Báo kỹ thuật kiểm tra và mở rộng dung lượng trước khi tải "
                            "thêm."
                        )

                tmp.replace(path)
                path.chmod(0o600)

                # External files: CHO_XAC_NHAN, không auto-approve.
                # Internal / non-order: NULL (không áp dụng).
                # Giữ behavior trước #174: uploader BAC_SI thì
                # tự cho phép gửi ngay.
                xac_nhan_state = "CHO_XAC_NHAN" if is_external else None
                # Internal files: giữ auto cho_phep_gui nếu bác sĩ tải lên.
                auto_gui = not is_external and identity.co_vai(TU_CHO_PHEP_GUI)
                row_id = await conn.fetchval(
                    """
                    INSERT INTO public.tep_ket_qua
                        (clinic_id, clinic_patient_id, appointment_id, khoa,
                         ten_hien_thi, loai_tep, mime, so_byte, sha256,
                         tai_len_boi_staff_id,
                         cho_phep_gui_luc, cho_phep_gui_boi_staff_id,
                         service_order_id, xac_nhan_trang_thai)
                    VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6, $7, $8, $9,
                            $10::uuid,
                            CASE WHEN $12 THEN now() ELSE NULL END,
                            CASE WHEN $12 THEN $10::uuid ELSE NULL END,
                            $11::uuid, $13)
                    RETURNING id::text
                    """,
                    identity.clinic_id,
                    clinic_patient_id,
                    appointment_id,
                    key,
                    (ten_hien_thi or "").strip()[:200] or None,
                    loai,
                    mime,
                    so_byte,
                    sha,
                    identity.staff_id,
                    service_order_id,
                    auto_gui,
                    xac_nhan_state,
                )
                if service_order_id:
                    # Mốc "tài liệu đã tới" (để tương thích dữ liệu cũ/hiển thị).
                    # Không dùng để quyết định VALID_RESULT cho external order.
                    await conn.execute(
                        "UPDATE public.service_order"
                        "   SET ket_qua_luc = coalesce(ket_qua_luc, now()),"
                        "       updated_at = now()"
                        " WHERE id = $1::uuid AND clinic_id = $2::uuid",
                        service_order_id,
                        identity.clinic_id,
                    )
        except BaseException:
            tmp.unlink(missing_ok=True)
            path.unlink(missing_ok=True)
            raise

        logger.info(
            "tep_ket_qua_tai_len",
            loai=loai,
            mime=mime,
            bytes=so_byte,
            by_staff_id=identity.staff_id,
        )
        if service_order_id and not is_external:
            # Chỉ tự động chạy lại vòng đọc cho nội bộ (lam_ben_ngoai = false).
            # Đối với đối tác ngoài, tệp tải lên bắt đầu ở CHO_XAC_NHAN,
            # KHÔNG phải VALID_RESULT nên KHÔNG được mở REVIEW.
            from clinicai.services.luot_kham_service import LuotKhamService

            try:
                await LuotKhamService(self._pool).sau_khi_co_ket_qua(
                    order_id=service_order_id, identity=identity
                )
            except Exception:
                logger.exception(
                    "tep_ket_qua_danh_gia_lai_vong_doc_loi",
                    service_order_id=service_order_id,
                )
        await bao_ket_qua_ve(
            self._pool,
            identity=identity,
            loai="tep",
            ref_id=str(row_id),
            clinic_patient_id=clinic_patient_id,
            appointment_id=appointment_id,
            visit_id=None,
        )
        return {"ok": True, "id": row_id, "loai_tep": loai, "so_byte": so_byte}

    async def xac_nhan_tep(
        self,
        *,
        identity: StaffIdentity,
        tep_id: str,
        trang_thai: str,
        ly_do: str | None = None,
    ) -> dict[str, Any]:
        """Xác nhận tệp kết quả: HOP_LE hoặc TU_CHOI.

        Yêu cầu capability 'ket_qua.xac_nhan' và nhân sự chỉ có đúng một active
        clinic_membership tại identity.clinic_id.
        """
        if trang_thai not in ("HOP_LE", "TU_CHOI"):
            raise ValidationError(
                "Trạng thái xác nhận chỉ được là HOP_LE hoặc TU_CHOI."
            )
        if trang_thai == "TU_CHOI" and not (ly_do and ly_do.strip()):
            raise ValidationError("Từ chối tệp kết quả bắt buộc phải có lý do.")

        cid = identity.clinic_id
        async with self._pool.acquire() as conn, conn.transaction():
            await kiem_tra_quyen_xac_nhan(conn, identity=identity)

            tep = await conn.fetchrow(
                """
                SELECT id, clinic_id, service_order_id, tai_len_boi_staff_id,
                       xac_nhan_trang_thai, xac_nhan_luc, xac_nhan_boi_staff_id
                  FROM public.tep_ket_qua
                 WHERE id = $1::uuid AND clinic_id = $2::uuid
                   FOR UPDATE
                """,
                tep_id,
                cid,
            )
            if tep is None:
                raise NotFoundError("Không tìm thấy tệp này.")

            # Chặn tự xác nhận tệp do chính mình tải lên
            if str(tep["tai_len_boi_staff_id"]) == str(identity.staff_id):
                raise SafetyGateError(
                    "Người tải lên không được tự xác nhận tệp kết quả của chính mình."
                )

            # Idempotent retry: nếu đã ở đúng trạng thái đích thì không lỗi
            if tep["xac_nhan_trang_thai"] == trang_thai:
                return {
                    "ok": True,
                    "id": str(tep["id"]),
                    "trang_thai": trang_thai,
                    "already": True,
                }

            # State machine duy nhất: chỉ cho phép chuyển từ CHO_XAC_NHAN
            if tep["xac_nhan_trang_thai"] != "CHO_XAC_NHAN":
                curr = tep["xac_nhan_trang_thai"]
                raise ConflictError(
                    f"Không thể chuyển trạng thái từ {curr} sang {trang_thai}."
                )

            await conn.execute(
                """
                UPDATE public.tep_ket_qua
                   SET xac_nhan_trang_thai = $1,
                       xac_nhan_luc = now(),
                       xac_nhan_boi_staff_id = $2::uuid,
                       xac_nhan_ly_do = $3
                 WHERE id = $4::uuid AND clinic_id = $5::uuid
                """,
                trang_thai,
                identity.staff_id,
                ly_do.strip() if ly_do else None,
                tep_id,
                cid,
            )

            await record_event(
                conn,
                event_type="tep_ket_qua.xac_nhan",
                aggregate_type="tep_ket_qua",
                aggregate_id=str(tep["id"]),
                identity=identity,
                origin="api:tep-ket-qua:xac-nhan",
                payload={
                    "trang_thai": trang_thai,
                    "ly_do": ly_do,
                    "service_order_id": str(tep["service_order_id"])
                    if tep["service_order_id"]
                    else None,
                },
            )

        # Nếu HOP_LE và có service_order VÀ KHÔNG PHẢI external -> đánh giá lại vòng đọc
        if trang_thai == "HOP_LE" and tep["service_order_id"]:
            # Kiểm tra external: nếu order thuộc node lam_ben_ngoai thì KHÔNG
            # gọi sau_khi_co_ket_qua — kết quả external không kéo bệnh nhân
            # quay lại hàng khám.
            async with self._pool.acquire() as conn:
                la_ngoai = await conn.fetchval(
                    "SELECT coalesce(nd.lam_ben_ngoai, false)"
                    "  FROM public.service_order o"
                    "  LEFT JOIN public.node_definition nd"
                    "    ON nd.clinic_id = o.clinic_id AND nd.code = o.node_code"
                    " WHERE o.id = $1::uuid AND o.clinic_id = $2::uuid",
                    str(tep["service_order_id"]),
                    cid,
                )
            if not la_ngoai:
                from clinicai.services.luot_kham_service import LuotKhamService

                await LuotKhamService(self._pool).sau_khi_co_ket_qua(
                    order_id=str(tep["service_order_id"]), identity=identity
                )

        return {"ok": True, "id": str(tep["id"]), "trang_thai": trang_thai}

    async def thu_hoi_tep(
        self,
        *,
        identity: StaffIdentity,
        tep_id: str,
        ly_do: str,
    ) -> dict[str, Any]:
        """Thu hồi tệp đã từng HOP_LE (chuyển sang THU_HOI).

        Chỉ cho phép chuyển từ HOP_LE -> THU_HOI.
        Bắt buộc có lý do thu hồi và quyền 'ket_qua.xac_nhan'.
        Nếu REVIEW đã bắt đầu hoặc đã đóng -> dừng và báo design case (không hồi tố).
        """
        if not (ly_do and ly_do.strip()):
            raise ValidationError("Thu hồi tệp kết quả bắt buộc phải có lý do.")

        cid = identity.clinic_id
        async with self._pool.acquire() as conn, conn.transaction():
            await kiem_tra_quyen_xac_nhan(conn, identity=identity)

            tep = await conn.fetchrow(
                """
                SELECT id, clinic_id, service_order_id, xac_nhan_trang_thai,
                       xac_nhan_luc, xac_nhan_boi_staff_id
                  FROM public.tep_ket_qua
                 WHERE id = $1::uuid AND clinic_id = $2::uuid
                   FOR UPDATE
                """,
                tep_id,
                cid,
            )
            if tep is None:
                raise NotFoundError("Không tìm thấy tệp này.")

            if tep["xac_nhan_trang_thai"] == "THU_HOI":
                return {
                    "ok": True,
                    "id": str(tep["id"]),
                    "trang_thai": "THU_HOI",
                    "already": True,
                }

            if tep["xac_nhan_trang_thai"] != "HOP_LE":
                curr = tep["xac_nhan_trang_thai"]
                raise ConflictError(
                    f"Chỉ có thể thu hồi tệp đang ở trạng thái HOP_LE "
                    f"(hiện tại: {curr})."
                )

            if tep["service_order_id"]:
                # Kiểm tra xem phiên đọc kết quả đã bắt đầu hay kết thúc chưa
                review_state = await conn.fetchrow(
                    """
                    SELECT r.status AS round_status, c.status AS cons_status
                      FROM round_requirement q
                      JOIN review_round r
                        ON r.id = q.round_id AND r.clinic_id = q.clinic_id
                      LEFT JOIN consultation c
                        ON c.clinic_id = r.clinic_id
                       AND c.visit_id = r.visit_id
                       AND c.round_no = r.round_no
                     WHERE q.clinic_id = $1::uuid
                       AND q.service_order_id = $2::uuid
                    """,
                    cid,
                    tep["service_order_id"],
                )
                if review_state:
                    if review_state["round_status"] in (
                        "in_review",
                        "closed",
                    ) or review_state["cons_status"] in ("in_progress", "done"):
                        raise ConflictError(
                            "Phiên đọc kết quả đã bắt đầu hoặc đã kết thúc — "
                            "không thể tự động thu hồi tệp. Vui lòng báo case "
                            "hội chẩn/chuyên môn để xử lý theo quy trình hồi tố."
                        )

            await conn.execute(
                """
                UPDATE public.tep_ket_qua
                   SET xac_nhan_trang_thai = 'THU_HOI',
                       thu_hoi_luc = now(),
                       thu_hoi_boi_staff_id = $1::uuid,
                       thu_hoi_ly_do = $2
                 WHERE id = $3::uuid AND clinic_id = $4::uuid
                """,
                identity.staff_id,
                ly_do.strip(),
                tep_id,
                cid,
            )

            await record_event(
                conn,
                event_type="tep_ket_qua.thu_hoi",
                aggregate_type="tep_ket_qua",
                aggregate_id=str(tep["id"]),
                identity=identity,
                origin="api:tep-ket-qua:thu-hoi",
                payload={
                    "ly_do": ly_do,
                    "service_order_id": str(tep["service_order_id"])
                    if tep["service_order_id"]
                    else None,
                },
            )

        # Đánh giá lại vòng đọc: nếu requirement không còn valid thì rút lại hàng chờ
        if tep["service_order_id"]:
            from clinicai.services.luot_kham_service import LuotKhamService

            await LuotKhamService(self._pool).sau_khi_co_ket_qua(
                order_id=str(tep["service_order_id"]), identity=identity
            )

        return {"ok": True, "id": str(tep["id"]), "trang_thai": "THU_HOI"}

    async def danh_sach(
        self, *, identity: StaffIdentity, clinic_patient_id: str
    ) -> list[dict[str, Any]]:
        """Tệp kết quả của một khách, mới nhất trước."""
        rows = await self._pool.fetch(
            """
            SELECT t.id::text, t.ten_hien_thi, t.loai_tep, t.mime, t.so_byte,
                   t.tai_len_luc, t.gui_luc, t.gui_kenh,
                   t.cho_phep_gui_luc, t.appointment_id::text,
                   t.service_order_id::text,
                   t.xac_nhan_trang_thai, t.xac_nhan_luc, t.xac_nhan_ly_do,
                   t.thu_hoi_luc, t.thu_hoi_ly_do,
                   s.full_name AS tai_len_boi,
                   g.full_name AS gui_boi,
                   b.full_name AS cho_phep_gui_boi,
                   xn.full_name AS xac_nhan_boi,
                   th.full_name AS thu_hoi_boi
              FROM public.tep_ket_qua t
              LEFT JOIN public.staff s ON s.id = t.tai_len_boi_staff_id
              LEFT JOIN public.staff g ON g.id = t.gui_boi_staff_id
              LEFT JOIN public.staff b ON b.id = t.cho_phep_gui_boi_staff_id
              LEFT JOIN public.staff xn ON xn.id = t.xac_nhan_boi_staff_id
              LEFT JOIN public.staff th ON th.id = t.thu_hoi_boi_staff_id
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

        Quyền đọc:
        A. caller thuộc nhóm NORMAL_READ_ROLES (_KET_QUA_DOC_GUARD semantics cũ)
        OR
        B. caller có capability 'ket_qua.xac_nhan'
           AND file cùng clinic
           AND xac_nhan_trang_thai = 'CHO_XAC_NHAN'
           AND service_order_id IS NOT NULL
           AND order join node_definition.lam_ben_ngoai = true.
        """
        row = await self._pool.fetchrow(
            """
            SELECT t.khoa, t.mime, t.so_byte, t.ten_hien_thi,
                   t.clinic_id::text, t.xac_nhan_trang_thai,
                   t.service_order_id::text,
                   n.lam_ben_ngoai
              FROM public.tep_ket_qua t
              LEFT JOIN public.service_order o
                ON o.id = t.service_order_id AND o.clinic_id = t.clinic_id
              LEFT JOIN public.node_definition n
                ON n.code = o.node_code AND n.clinic_id = t.clinic_id
             WHERE t.id = $1::uuid AND t.clinic_id = $2::uuid
            """,
            tep_id,
            identity.clinic_id,
        )
        if row is None:
            raise NotFoundError("Không tìm thấy tệp này.")

        duoc_doc = False
        if identity.co_vai(NORMAL_READ_ROLES):
            duoc_doc = True
        elif await co_quyen_xac_nhan(self._pool, identity):
            if (
                row["xac_nhan_trang_thai"] == "CHO_XAC_NHAN"
                and row["service_order_id"] is not None
                and row["lam_ben_ngoai"] is True
            ):
                duoc_doc = True

        if not duoc_doc:
            raise SafetyGateError("Không có quyền xem tệp này.")

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
        hien = await self._pool.fetchrow(
            "SELECT gui_luc, cho_phep_gui_luc, xac_nhan_trang_thai "
            "FROM public.tep_ket_qua "
            "WHERE id = $1::uuid AND clinic_id = $2::uuid",
            tep_id,
            identity.clinic_id,
        )
        if hien is None:
            raise NotFoundError("Không tìm thấy tệp này.")
        # BÁC SĨ CHO PHÉP TRƯỚC (15/09/2026). Trigger
        # `tep_ket_qua_gui_phai_duoc_cho_phep` cũng chặn — câu ở đây nói bằng
        # tiếng người trước khi chạm ràng buộc.
        if hien.get("cho_phep_gui_luc") is None:
            raise ConflictError(
                "Bác sĩ chưa cho phép gửi tệp này — chờ bác sĩ xem và cho phép."
            )
        # External files: phải ở HOP_LE. Internal (NULL): không yêu cầu.
        xn_state = hien.get("xac_nhan_trang_thai")
        if xn_state is not None and xn_state != "HOP_LE":
            raise ConflictError(
                "Tệp kết quả chưa ở trạng thái hợp lệ để gửi cho khách."
            )
        # External: yêu cầu HOP_LE + cho_phep_gui. Internal: chỉ cho_phep_gui.
        where_extra = (
            "AND xac_nhan_trang_thai = 'HOP_LE'" if xn_state is not None else ""
        )
        row = await self._pool.fetchrow(
            f"""
            UPDATE public.tep_ket_qua
               SET gui_luc = now(), gui_boi_staff_id = $1::uuid, gui_kenh = $2
             WHERE id = $3::uuid AND clinic_id = $4::uuid AND gui_luc IS NULL
               AND cho_phep_gui_luc IS NOT NULL
               {where_extra}
            RETURNING id::text
            """,
            identity.staff_id,
            kenh,
            tep_id,
            identity.clinic_id,
        )
        if row is None:
            raise NotFoundError("Tệp này đã được gửi rồi.")
        return {"ok": True}

    async def cho_phep_gui(
        self, *, identity: StaffIdentity, tep_id: str
    ) -> dict[str, Any]:
        """Bác sĩ đã xem tệp và cho phép CSKH gửi cho khách."""
        if not identity.co_vai(BAC_SI_CHO_PHEP_GUI):
            raise SafetyGateError("Chỉ bác sĩ mới cho phép gửi kết quả cho khách.")
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                hien = await conn.fetchrow(
                    "SELECT xac_nhan_trang_thai, cho_phep_gui_luc "
                    "FROM public.tep_ket_qua "
                    "WHERE id = $1::uuid AND clinic_id = $2::uuid FOR UPDATE",
                    tep_id,
                    identity.clinic_id,
                )
                if hien is None:
                    raise NotFoundError("Không tìm thấy tệp này.")
                # External files: bắt buộc HOP_LE. Internal (NULL): cho qua.
                xn_state = hien["xac_nhan_trang_thai"]
                if xn_state is not None and xn_state != "HOP_LE":
                    raise SafetyGateError(
                        f"Chỉ tệp kết quả ở trạng thái HOP_LE mới được phép "
                        f"duyệt gửi cho khách (hiện tại: {xn_state})."
                    )
                where_extra = (
                    "AND xac_nhan_trang_thai = 'HOP_LE'" if xn_state is not None else ""
                )
                row = await conn.fetchrow(
                    f"""
                    UPDATE public.tep_ket_qua
                       SET cho_phep_gui_luc = now(),
                           cho_phep_gui_boi_staff_id = $1::uuid
                     WHERE id = $2::uuid AND clinic_id = $3::uuid
                       AND cho_phep_gui_luc IS NULL
                       {where_extra}
                    RETURNING id::text, clinic_patient_id::text
                    """,
                    identity.staff_id,
                    tep_id,
                    identity.clinic_id,
                )
                if row is None:
                    ton_tai = await conn.fetchval(
                        "SELECT 1 FROM public.tep_ket_qua "
                        "WHERE id = $1::uuid AND clinic_id = $2::uuid",
                        tep_id,
                        identity.clinic_id,
                    )
                    if ton_tai is None:
                        raise NotFoundError("Không tìm thấy tệp này.")
                    return {"ok": True, "da_cho_phep_tu_truoc": True}
                await record_event(
                    conn,
                    event_type="tep_ket_qua.cho_phep_gui",
                    aggregate_type="tep_ket_qua",
                    aggregate_id=row["id"],
                    identity=identity,
                    origin="api:cskh-ket-qua",
                    payload={"clinic_patient_id": row["clinic_patient_id"]},
                )
        return {"ok": True}

    async def cho_bac_si_cho_phep(
        self, *, identity: StaffIdentity
    ) -> list[dict[str, Any]]:
        """Tệp kết quả đang chờ bác sĩ cho phép gửi — cũ nhất trước.

        Gồm cả:
        - External files đã xác nhận HOP_LE.
        - Internal/non-order (NULL) — behavior trước #174.
        """
        if not identity.co_vai(BAC_SI_CHO_PHEP_GUI):
            raise SafetyGateError("Chỉ bác sĩ mới xem hàng chờ cho phép gửi.")
        rows = await self._pool.fetch(
            """
            SELECT t.id::text, t.ten_hien_thi, t.loai_tep, t.so_byte, t.tai_len_luc,
                   t.clinic_patient_id::text, p.full_name AS ten_khach,
                   p.patient_code, s.full_name AS tai_len_boi
              FROM public.tep_ket_qua t
              JOIN public.patient p ON p.clinic_patient_id = t.clinic_patient_id
              LEFT JOIN public.staff s ON s.id = t.tai_len_boi_staff_id
             WHERE t.clinic_id = $1::uuid
               AND (t.xac_nhan_trang_thai = 'HOP_LE'
                    OR t.xac_nhan_trang_thai IS NULL)
               AND t.cho_phep_gui_luc IS NULL AND t.gui_luc IS NULL
             ORDER BY t.tai_len_luc
             LIMIT 200
            """,
            identity.clinic_id,
        )
        return [dict(r) for r in rows]

    async def cho_xac_nhan(self, *, identity: StaffIdentity) -> list[dict[str, Any]]:
        """Danh sách tệp kết quả external đang chờ xác nhận — cũ nhất lên trước.

        Yêu cầu capability 'ket_qua.xac_nhan' (Fail-closed, 403 nếu không có).
        LƯU Ý HIỆN TẠI (CURRENT LIMITATION): SINGLE-PARTNER PILOT ONLY.
        """
        await kiem_tra_quyen_xac_nhan(self._pool, identity=identity)

        rows = await self._pool.fetch(
            """
            SELECT t.id::text AS tep_id,
                   t.clinic_patient_id::text,
                   p.full_name AS ten_khach,
                   p.patient_code,
                   t.service_order_id::text,
                   o.service_name AS ten_dich_vu,
                   t.tai_len_luc,
                   s.full_name AS tai_len_boi_ten,
                   m.role::text AS tai_len_boi_vai,
                   t.tai_len_boi_staff_id::text,
                   t.ten_hien_thi,
                   t.loai_tep,
                   t.mime,
                   t.xac_nhan_trang_thai
              FROM public.tep_ket_qua t
              JOIN public.patient p ON p.clinic_patient_id = t.clinic_patient_id
              JOIN public.service_order o
                ON o.id = t.service_order_id AND o.clinic_id = t.clinic_id
              JOIN public.node_definition n
                ON n.code = o.node_code AND n.clinic_id = t.clinic_id
              LEFT JOIN public.staff s ON s.id = t.tai_len_boi_staff_id
              LEFT JOIN public.clinic_membership m
                ON m.staff_id = s.id
               AND m.clinic_id = t.clinic_id
               AND m.is_active = true
             WHERE t.clinic_id = $1::uuid
               AND t.xac_nhan_trang_thai = 'CHO_XAC_NHAN'
               AND t.service_order_id IS NOT NULL
               AND n.lam_ben_ngoai = true
               AND o.exec_status NOT IN ('draft', 'cancelled')
             ORDER BY t.tai_len_luc ASC, t.id ASC
             LIMIT 100
            """,
            identity.clinic_id,
        )

        res: list[dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            is_own = r["tai_len_boi_staff_id"] is not None and str(
                r["tai_len_boi_staff_id"]
            ) == str(identity.staff_id)
            d["co_the_xac_nhan"] = not is_own
            d["khong_the_xac_nhan_ly_do"] = (
                "Bạn là người tải tệp này — cần người khác xác nhận."
                if is_own
                else None
            )
            res.append(d)
        return res
