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
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import IO, Any

import asyncpg
import structlog

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.core.kho_tep import chay_tren_kho
from clinicai.core.tran import canh_bao_neu_day
from clinicai.events.catalogue import (
    KetQuaDaGuiKhach,
    TepKetQuaDaKhoiPhuc,
    TepKetQuaDaThuHoi,
    TepKetQuaDaVe,
    TepKetQuaDaXacNhan,
    TepKetQuaDaXem,
    TepKetQuaDaXoa,
)
from clinicai.events.emit import emit_event, nguoi
from clinicai.permissions.can import can, can_o_phong_nao_do
from clinicai.services.audit import record_event
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

#: BƯỚC XÁC NHẬN TỆP ĐỐI TÁC — OFF (Tuyền 23/09/2026 khuya: "không cần nút xác
#: nhận kết quả, nó phải cho vào luôn trong phiếu khám của bác sĩ… không cần
#: xác nhận làm gì, hiện ra đó luôn là được"). Tắt: tệp đối tác được ghi HỢP LỆ
#: ngay lúc tải lên (người tải = người xác nhận, lý do ghi rõ là tự động) → mọi
#: chỗ đọc "kết quả hợp lệ" chạy y như cũ, vòng đọc của bác sĩ mở ngay. Bật lại
#: (True) là về luồng CHO_XAC_NHAN → màn Xác nhận kết quả. Không xoá đường cũ.
XAC_NHAN_TEP_DOI_TAC = False
LY_DO_TU_XAC_NHAN = "Tự động — phòng khám không dùng bước xác nhận tệp đối tác"

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


#: Vai tải lên / liệt kê tệp — Y HỆT cửa `_TEP_TAI_LEN_GUARD` của router CSKH
#: (INTAKE_ROLES + bác sĩ, BS siêu âm, thư ký y khoa, điều dưỡng siêu âm).
VAI_TAI_LEN: frozenset[ClinicRole] = frozenset(
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


#: Quyền (không phải vai) mở thêm cửa ĐỌC tệp kết quả — 29/09/2026: khối Đối
#: tác + khối Phòng dịch vụ (ở bất kỳ phòng nào, kể cả quyền theo lịch).
QUYEN_DOC_TEP_THEM: tuple[str, ...] = (
    "partner.work",
    "service.execute.start",
    "service.execute.complete",
)


async def doc_duoc_tep_ket_qua(
    conn: asyncpg.Connection, identity: StaffIdentity
) -> bool:
    """Người này ĐỌC (xem, liệt kê) được tệp kết quả của phòng khám không?

    Vai cũ (NORMAL_READ_ROLES) giữ nguyên. THÊM theo LEGO (Tuyền chốt 26/09:
    "khám CHỈ CẦN LEGO"; đợt 3 27/09): ai đọc được phiếu khám / kết quả CLS —
    đúng hàm quyền của phiếu khám (`kiem_quyen_core`, việc `doc_ket_qua_cls`)
    — thì đọc được ảnh / tệp gắn chỉ định. Trước đây tài khoản có lego Bàn khám
    / Phòng dịch vụ mà vai tài khoản không thuộc danh sách thì đọc được phiếu
    nhưng khung ảnh báo "không đọc được". Giữ thêm cửa quầy in phiếu
    (`doc_duoc_in_phieu`, 27/09) — trang ảnh của bản in.

    THÊM 29/09/2026 (Tuyền: "file kết quả mọi chỗ đều hiện được và tải/in
    được"): người có quyền của khối ĐỐI TÁC (`partner.work` — nhân sự phòng
    khám làm việc đối tác, kể cả nhờ lịch) hoặc khối PHÒNG DỊCH VỤ (thực hiện
    dịch vụ ở bất kỳ phòng nào) — họ tải tệp lên thì phải xem lại được.

    Vai PARTNER (tài khoản người NGOÀI phòng khám) KHÔNG BAO GIỜ qua: kiểm vai ấy
    TRƯỚC mọi nhánh quyền, kể cả lỡ được cấp `partner.work`.
    Phạm vi phòng khám do câu truy vấn của nơi gọi giữ (`clinic_id`).
    """
    if identity.co_vai(NORMAL_READ_ROLES):
        return True
    if identity.co_vai([ClinicRole.PARTNER]):
        return False
    from clinicai.permissions.y_khoa import doc_duoc_in_phieu
    from clinicai.services.phieu_kham_service import kiem_quyen_core

    for q in QUYEN_DOC_TEP_THEM:
        if await can_o_phong_nao_do(conn, identity, q):
            return True

    try:
        await kiem_quyen_core(conn, identity, "doc_ket_qua_cls")
        return True
    except SafetyGateError:
        pass
    return await doc_duoc_in_phieu(conn, identity)


async def tai_len_duoc_tep_ket_qua(
    conn: asyncpg.Connection, identity: StaffIdentity
) -> bool:
    """Người này TẢI LÊN được tệp kết quả không? Vai cũ (`VAI_TAI_LEN`), hoặc
    có khối GHI y khoa (ghi bệnh án / điền kết quả — lego Bàn khám, Phòng dịch
    vụ): người điền phiếu kết quả phải gửi được ảnh của chính kết quả ấy."""
    if identity.co_vai(VAI_TAI_LEN):
        return True
    if identity.co_vai([ClinicRole.PARTNER]):
        return False
    from clinicai.permissions.y_khoa import QUYEN_GHI_Y_KHOA

    for q in QUYEN_GHI_Y_KHOA:
        if await can(conn, identity, q):
            return True
    return False


async def _hoi_quyen_xac_nhan(
    conn: asyncpg.Connection | asyncpg.Pool, identity: StaffIdentity
) -> bool:
    if isinstance(conn, asyncpg.Pool):
        async with conn.acquire() as c:
            return await can(c, identity, "result.file.confirm")
    return await can(conn, identity, "result.file.confirm")


async def co_quyen_xac_nhan(
    conn: asyncpg.Connection | asyncpg.Pool,
    identity: StaffIdentity,
) -> bool:
    """Người này xác nhận được tệp kết quả ở phòng khám này không?

    MỘT hệ quyền (23/09/2026): quyền thật là `result.file.confirm` trong
    `capability_grant`, theo từng phòng khám. `staff_capability` cũ đã nghỉ.

    Đối tác KHÔNG BAO GIỜ xác nhận được, kể cả lỡ được cấp: tệp là của chính họ
    gửi lên, tự xác nhận thì phép kiểm mất nghĩa. Đây là tách vai (người gửi ≠
    người xác nhận), không phải phân quyền theo vai.
    """
    if identity.co_vai([ClinicRole.PARTNER]):
        return False
    return await _hoi_quyen_xac_nhan(conn, identity)


async def kiem_tra_quyen_xac_nhan(
    conn: asyncpg.Connection | asyncpg.Pool,
    *,
    identity: StaffIdentity,
) -> None:
    """Như `co_quyen_xac_nhan`, nhưng chặn bằng lỗi khi không có quyền."""
    if identity.co_vai([ClinicRole.PARTNER]):
        raise SafetyGateError("Đối tác không có quyền xác nhận kết quả.")
    if not await _hoi_quyen_xac_nhan(conn, identity):
        raise SafetyGateError(
            "Bạn không có quyền xác nhận tệp kết quả. Quản lý cấp ở màn Phân quyền."
        )


#: Mở tệp là "đã xem" với người làm chuyên môn đọc kết quả (không phải CSKH
#: mở để gửi, không phải lễ tân).
XEM_LA_DA_XEM: frozenset[ClinicRole] = frozenset(
    {ClinicRole.DOCTOR, ClinicRole.ULTRASOUND_DOCTOR, ClinicRole.TKYK}
)


# ── Xoá mềm tệp kết quả (V9, Tuyền chốt 30/09/2026) ─────────────────────────
#
# Hướng "MỞ HẾT": người có lego Kết quả (`result.file.delete`, khối `ket_qua`)
# xoá được mọi lúc; người tải lên xoá được tệp của mình khi chưa ai khác xem /
# duyệt. Chỉ giữ chặn khi tệp đã tới tay khách hoặc phiên đọc đã đóng: lúc ấy
# chỉ còn "Đính chính – gỡ tệp", cần quyền duyệt kết quả và lý do. Lý do LUÔN
# bắt buộc. Xoá = ẩn (view `v_tep_ket_qua_hieu_luc`), khôi phục được 30 ngày.

LOAI_XOA = "XOA"
LOAI_DINH_CHINH = "DINH_CHINH"
#: Khôi phục được trong bấy nhiêu ngày; job dọn ổ cũng đợi đúng mốc này.
SO_NGAY_KHOI_PHUC = 30
LY_DO_XOA_TOI_DA = 500

#: Phiên đọc kết quả của chỉ định đã ĐÓNG — cột tính kèm dòng tệp (bí danh `t`).
PHIEN_DOC_DONG_SQL = """EXISTS (
    SELECT 1 FROM round_requirement q_xd
      JOIN review_round r_xd
        ON r_xd.id = q_xd.round_id AND r_xd.clinic_id = q_xd.clinic_id
     WHERE q_xd.clinic_id = t.clinic_id
       AND q_xd.service_order_id = t.service_order_id
       AND r_xd.status = 'closed')"""

#: Các cột `xoa_duoc` / `khoi_phuc_duoc` cần — ghép vào SELECT có bí danh `t`.
COT_XOA_SQL = (
    "t.tai_len_boi_staff_id::text AS x_tai_len_boi,"
    " t.da_xem_luc AS x_da_xem_luc, t.da_xem_boi_staff_id::text AS x_da_xem_boi,"
    " t.cho_phep_gui_luc AS x_cho_phep_luc,"
    " t.cho_phep_gui_boi_staff_id::text AS x_cho_phep_boi,"
    " t.gui_luc AS x_gui_luc, t.da_xoa_luc, t.da_xoa_loai, t.da_xoa_ly_do,"
    " t.da_xoa_boi_staff_id::text AS x_da_xoa_boi, t.da_don_tep_luc,"
    f" {PHIEN_DOC_DONG_SQL} AS x_phien_doc_dong"
)


@dataclass(frozen=True)
class QuyenXoaTep:
    """Quyền của MỘT người với việc xoá tệp — hỏi DB một lần, dùng cho cả
    danh sách (hàm `xoa_duoc` thuần, test được không cần DB)."""

    staff_id: str
    doc_duoc: bool
    co_quyen_xoa: bool
    co_quyen_duyet: bool


@dataclass(frozen=True)
class KetQuaXoa:
    duoc: bool
    #: XOA | DINH_CHINH khi `duoc`; loại của lần xoá khi hỏi khôi phục.
    loai: str | None = None
    #: Không được thì vì sao; được mà là Đính chính thì câu nhắc.
    ly_do: str | None = None


def _co(tep: Mapping[str, Any], ten: str) -> Any:
    try:
        return tep[ten]
    except (KeyError, IndexError):
        return None


def xoa_duoc(tep: Mapping[str, Any], quyen: QuyenXoaTep) -> KetQuaXoa:
    """Người có `quyen` xoá được tệp này không — theo loại nào, vì sao không.

    `tep` là dòng đọc kèm `COT_XOA_SQL`. Hàm THUẦN: máy chủ quyết, giao diện
    chỉ hiện nút khi `duoc` (không luật nào trong TSX).
    """
    if _co(tep, "da_xoa_luc") is not None:
        return KetQuaXoa(False, None, "Tệp này đã xoá.")
    la_nguoi_tai = bool(quyen.staff_id) and (
        str(_co(tep, "x_tai_len_boi") or "") == quyen.staff_id
    )
    if not (quyen.doc_duoc or la_nguoi_tai):
        return KetQuaXoa(False, None, "Bạn không có quyền với tệp kết quả.")
    da_gui = _co(tep, "x_gui_luc") is not None
    if da_gui or bool(_co(tep, "x_phien_doc_dong")):
        vi_sao = "Tệp đã gửi khách" if da_gui else "Phiên đọc kết quả đã đóng"
        if quyen.co_quyen_duyet:
            return KetQuaXoa(
                True,
                LOAI_DINH_CHINH,
                f"{vi_sao} — chỉ gỡ được bằng Đính chính, ghi rõ lý do.",
            )
        return KetQuaXoa(
            False,
            None,
            f"{vi_sao} — cần người có quyền duyệt kết quả để đính chính, gỡ tệp.",
        )
    if quyen.co_quyen_xoa:
        return KetQuaXoa(True, LOAI_XOA)
    if la_nguoi_tai:
        xem_boi_khac = _co(tep, "x_da_xem_luc") is not None and (
            str(_co(tep, "x_da_xem_boi") or "") != quyen.staff_id
        )
        duyet_boi_khac = _co(tep, "x_cho_phep_luc") is not None and (
            str(_co(tep, "x_cho_phep_boi") or "") != quyen.staff_id
        )
        if not (xem_boi_khac or duyet_boi_khac):
            return KetQuaXoa(True, LOAI_XOA)
        return KetQuaXoa(
            False,
            None,
            "Bác sĩ đã xem / duyệt tệp này — cần người có quyền xoá tệp kết quả.",
        )
    return KetQuaXoa(
        False,
        None,
        "Chỉ người tải lên hoặc người có quyền xoá tệp kết quả mới xoá được.",
    )


def han_khoi_phuc(da_xoa_luc: Any) -> datetime | None:
    """Mốc cuối còn khôi phục được; rỗng / rác → None (không ném)."""
    if not isinstance(da_xoa_luc, datetime):
        return None
    if da_xoa_luc.tzinfo is None:
        da_xoa_luc = da_xoa_luc.replace(tzinfo=UTC)
    return da_xoa_luc + timedelta(days=SO_NGAY_KHOI_PHUC)


def khoi_phuc_duoc(
    tep: Mapping[str, Any], quyen: QuyenXoaTep, bay_gio: datetime | None = None
) -> KetQuaXoa:
    """Người có `quyen` khôi phục được tệp đã xoá này không (trong 30 ngày, tệp
    vật lý còn). Xoá thường: người đã xoá hoặc người có quyền xoá; Đính chính:
    người có quyền duyệt kết quả."""
    loai = _co(tep, "da_xoa_loai")
    if _co(tep, "da_xoa_luc") is None:
        return KetQuaXoa(False, None, "Tệp này chưa bị xoá.")
    if _co(tep, "da_don_tep_luc") is not None:
        return KetQuaXoa(False, loai, "Tệp đã dọn khỏi ổ — không khôi phục được.")
    han = han_khoi_phuc(_co(tep, "da_xoa_luc"))
    bay_gio = bay_gio or datetime.now(UTC)
    if han is None or bay_gio > han:
        return KetQuaXoa(
            False,
            loai,
            f"Đã quá {SO_NGAY_KHOI_PHUC} ngày kể từ lúc xoá — không khôi phục được.",
        )
    if loai == LOAI_DINH_CHINH:
        if quyen.co_quyen_duyet:
            return KetQuaXoa(True, loai)
        return KetQuaXoa(
            False, loai, "Tệp gỡ bằng Đính chính — cần quyền duyệt kết quả."
        )
    nguoi_xoa = bool(quyen.staff_id) and (
        str(_co(tep, "x_da_xoa_boi") or "") == quyen.staff_id
    )
    if quyen.co_quyen_xoa or nguoi_xoa:
        return KetQuaXoa(True, loai)
    return KetQuaXoa(
        False, loai, "Chỉ người đã xoá hoặc người có quyền xoá tệp mới khôi phục."
    )


_COT_XOA_NOI_BO = frozenset(
    {
        "x_tai_len_boi",
        "x_da_xem_luc",
        "x_da_xem_boi",
        "x_cho_phep_luc",
        "x_cho_phep_boi",
        "x_gui_luc",
        "x_da_xoa_boi",
        "x_phien_doc_dong",
        "da_don_tep_luc",
    }
)


def gan_co_xoa(tep: Mapping[str, Any], quyen: QuyenXoaTep) -> dict[str, Any]:
    """Dòng tệp (đọc kèm `COT_XOA_SQL`) → dict kèm cờ máy chủ cho giao diện:
    tệp còn hiệu lực có `xoa_duoc / xoa_loai / xoa_ly_do`; tệp đã xoá có
    `khoi_phuc_duoc / khoi_phuc_ly_do / khoi_phuc_han`. Bỏ cột nội bộ."""
    d = {k: v for k, v in dict(tep).items() if k not in _COT_XOA_NOI_BO}
    if _co(tep, "da_xoa_luc") is None:
        kq = xoa_duoc(tep, quyen)
        d["xoa_duoc"] = kq.duoc
        d["xoa_loai"] = kq.loai
        d["xoa_ly_do"] = kq.ly_do
    else:
        kq = khoi_phuc_duoc(tep, quyen)
        han = han_khoi_phuc(_co(tep, "da_xoa_luc"))
        d["khoi_phuc_duoc"] = kq.duoc
        d["khoi_phuc_ly_do"] = None if kq.duoc else kq.ly_do
        d["khoi_phuc_han"] = han.isoformat() if han else None
    return d


async def quyen_xoa_tep(
    conn: asyncpg.Connection, identity: StaffIdentity
) -> QuyenXoaTep:
    """Hỏi DB một lần: đọc được tệp không, có quyền xoá, có quyền duyệt kết quả
    (kể cả theo phòng nhờ lịch — "MỞ HẾT"). Vai PARTNER bên ngoài không có
    quyền xoá / duyệt, kể cả lỡ được cấp; chỉ còn luật người tải lên."""
    doc = await doc_duoc_tep_ket_qua(conn, identity)
    if identity.co_vai([ClinicRole.PARTNER]):
        return QuyenXoaTep(str(identity.staff_id), doc, False, False)

    async def _co_quyen(q: str) -> bool:
        return await can(conn, identity, q) or await can_o_phong_nao_do(
            conn, identity, q
        )

    return QuyenXoaTep(
        staff_id=str(identity.staff_id),
        doc_duoc=doc,
        co_quyen_xoa=await _co_quyen("result.file.delete"),
        co_quyen_duyet=await _co_quyen("result.review.approve"),
    )


def chuan_ly_do_xoa(ly_do: Any) -> str:
    """Lý do xoá: bắt buộc, gọn khoảng trắng, tối đa 500 ký tự."""
    chu = " ".join(str(ly_do or "").split())
    if not chu:
        raise ValidationError("Xoá tệp kết quả bắt buộc phải có lý do.")
    if len(chu) > LY_DO_XOA_TOI_DA:
        raise ValidationError(f"Lý do tối đa {LY_DO_XOA_TOI_DA} ký tự.")
    return chu


async def _tinh_lai_ket_qua_luc(
    conn: asyncpg.Connection, clinic_id: str, service_order_id: str
) -> None:
    """Sau khi xoá tệp: chỉ định không còn tệp hiệu lực nào (và không có kết quả
    ghi chữ / phiếu kết quả hoàn tất) → CHƯA có kết quả. Không gỡ mốc thì chỉ
    định vẫn hiện "đã có kết quả" cho một tệp đã xoá (cùng luật TU_CHOI)."""
    await conn.execute(
        "UPDATE service_order o SET ket_qua_luc = NULL, updated_at = now()"
        " WHERE o.clinic_id = $1::uuid AND o.id = $2::uuid"
        "   AND o.ket_qua_luc IS NOT NULL"
        "   AND nullif(btrim(coalesce(o.result_note, '')), '') IS NULL"
        "   AND NOT EXISTS (SELECT 1 FROM v_tep_ket_qua_hieu_luc t"
        "        WHERE t.clinic_id = $1::uuid AND t.service_order_id = $2::uuid"
        "          AND coalesce(t.xac_nhan_trang_thai, 'HOP_LE')"
        "              IN ('CHO_XAC_NHAN', 'HOP_LE'))"
        "   AND NOT EXISTS (SELECT 1 FROM form_instance f"
        "        WHERE f.clinic_id = $1::uuid AND f.service_order_id = $2::uuid"
        "          AND f.trang_thai = 'READY')",
        clinic_id,
        service_order_id,
    )


async def _luot_cua_tep(
    conn: asyncpg.Connection,
    clinic_id: str,
    service_order_id: str | None,
    appointment_id: str | None,
) -> str | None:
    """Lượt khám của tệp — qua chỉ định, rồi qua lịch hẹn. Không có thì None
    (tệp gắn thẳng hồ sơ khách: dòng thời gian của lượt không nhận)."""
    if service_order_id:
        v = await conn.fetchval(
            "SELECT visit_id::text FROM public.service_order"
            " WHERE id = $1::uuid AND clinic_id = $2::uuid",
            service_order_id,
            clinic_id,
        )
        if v:
            return str(v)
    if appointment_id:
        v = await conn.fetchval(
            "SELECT visit_id::text FROM public.visit"
            " WHERE appointment_id = $1::uuid AND clinic_id = $2::uuid"
            " ORDER BY created_at DESC LIMIT 1",
            appointment_id,
            clinic_id,
        )
        if v:
            return str(v)
    return None


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
        ben: int | None = None,
    ) -> dict[str, Any]:
        """Nhận một tệp kết quả và cất nó lên đĩa.

        `ben` (26/09/2026): bên của tệp trong mẫu hai bên (Thai A=0, Thai B=1,
        trái=0, phải=1…); None = tệp chung.

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
                    "       coalesce(nd.lam_ben_ngoai, false) AS lam_ben_ngoai"
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
                # Chọn chỉ định ở màn Khách hàng (27/09 đợt 3): chỉ định phải
                # thuộc ĐÚNG lượt đang chọn, không chỉ đúng khách.
                if (
                    appointment_id
                    and cua_chi_dinh["appointment_id"]
                    and cua_chi_dinh["appointment_id"] != appointment_id
                ):
                    raise ValidationError(
                        "Chỉ định này không thuộc lượt khám đang chọn."
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

        await chay_tren_kho(kiem_kho_da_gan)
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
        if loai == "TAI_LIEU" and mime != "application/dicom":
            # Chỉ tài liệu Office (ZIP) mới mở ra xem thư mục bên trong; DICOM
            # cũng là TAI_LIEU (27/09 đợt 3) nhưng đã nhận bằng chữ ký byte 128.
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
                # BỎ CHỐT "ĐÃ TRẢ KẾT QUẢ" CỦA CSKH (Tuyền 28/09/2026: "không cần
                # chặn cskh cái gì nữa"). Trước đây mốc TRA_KQ xét theo KHÁCH
                # chặn mọi tệp mới — màn Đối tác báo "Việc này đã xác nhận trả
                # kết quả" cho một việc còn chờ tài liệu. Tải tệp không phụ thuộc
                # mốc chăm sóc khách nữa.

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
                tu_hop_le = is_external and not XAC_NHAN_TEP_DOI_TAC
                xac_nhan_state = (
                    ("HOP_LE" if tu_hop_le else "CHO_XAC_NHAN") if is_external else None
                )
                # Internal files: giữ auto cho_phep_gui nếu bác sĩ tải lên.
                auto_gui = not is_external and identity.co_vai(TU_CHO_PHEP_GUI)
                row_id = await conn.fetchval(
                    """
                    INSERT INTO public.tep_ket_qua
                        (clinic_id, clinic_patient_id, appointment_id, khoa,
                         ten_hien_thi, loai_tep, mime, so_byte, sha256,
                         tai_len_boi_staff_id,
                         cho_phep_gui_luc, cho_phep_gui_boi_staff_id,
                         service_order_id, xac_nhan_trang_thai,
                         xac_nhan_luc, xac_nhan_boi_staff_id, xac_nhan_ly_do,
                         ben)
                    VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6, $7, $8, $9,
                            $10::uuid,
                            CASE WHEN $12 THEN now() ELSE NULL END,
                            CASE WHEN $12 THEN $10::uuid ELSE NULL END,
                            $11::uuid, $13,
                            CASE WHEN $14 THEN now() END,
                            CASE WHEN $14 THEN $10::uuid END,
                            CASE WHEN $14 THEN $15 END,
                            $16)
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
                    tu_hop_le,
                    LY_DO_TU_XAC_NHAN,
                    ben,
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
                # Sự kiện trong CÙNG giao dịch với dòng tệp: khối Chuông nghe để
                # báo bác sĩ / thư ký / điều dưỡng / CSKH (người nhận chỉnh được),
                # dòng thời gian ghi "tệp đã về". Trước 24/09 gọi thẳng
                # `bao_ket_qua_ve` sau commit.
                luot_tep = await _luot_cua_tep(
                    conn, identity.clinic_id, service_order_id, appointment_id
                )
                await emit_event(
                    conn,
                    ten="result_file.uploaded",
                    clinic_id=identity.clinic_id,
                    aggregate_id=str(row_id),
                    payload=TepKetQuaDaVe(
                        tep_id=str(row_id),
                        visit_id=luot_tep,
                        service_order_id=service_order_id,
                        cho_xac_nhan=is_external and XAC_NHAN_TEP_DOI_TAC,
                    ),
                    boi=nguoi(identity),
                    correlation_id=luot_tep,
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
        # Vòng đọc (mở chỗ chờ "có kết quả" cho bác sĩ chính) do khối VÒNG ĐỌC
        # làm khi nghe `result_file.uploaded` — không gọi thẳng khối Khám nữa.
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
                   AND da_xoa_luc IS NULL
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
            so_id = str(tep["service_order_id"]) if tep["service_order_id"] else None
            if trang_thai == "TU_CHOI" and so_id:
                # Tệp bị từ chối mà chỉ định không còn tệp nào đang chờ / hợp
                # lệ → CHƯA có kết quả. Không gỡ mốc thì chỉ định vẫn hiện "đối
                # tác đã gửi kết quả", rơi khỏi danh sách "Cần làm" của đối tác
                # và nhắc quá hạn (H7) coi như xong (rà 23/09 khuya).
                await conn.execute(
                    "UPDATE service_order SET ket_qua_luc = NULL"
                    " WHERE clinic_id = $1::uuid AND id = $2::uuid"
                    "   AND NOT EXISTS (SELECT 1 FROM v_tep_ket_qua_hieu_luc t"
                    "        WHERE t.clinic_id = $1::uuid"
                    "          AND t.service_order_id = $2::uuid"
                    "          AND t.xac_nhan_trang_thai"
                    "              IN ('CHO_XAC_NHAN', 'HOP_LE'))",
                    cid,
                    so_id,
                )
            luot_tep = await _luot_cua_tep(conn, cid, so_id, None)
            await emit_event(
                conn,
                ten="result_file.confirmed",
                clinic_id=cid,
                aggregate_id=str(tep["id"]),
                payload=TepKetQuaDaXacNhan(
                    tep_id=str(tep["id"]),
                    visit_id=luot_tep,
                    service_order_id=so_id,
                    trang_thai=trang_thai,
                ),
                boi=nguoi(identity),
                correlation_id=luot_tep,
            )

        # Vòng đọc: khối VÒNG ĐỌC nghe `result_file.confirmed`.

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
                   AND da_xoa_luc IS NULL
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
            if tep["service_order_id"]:
                so_id = str(tep["service_order_id"])
                luot_tep = await _luot_cua_tep(conn, cid, so_id, None)
                await emit_event(
                    conn,
                    ten="result_file.revoked",
                    clinic_id=cid,
                    aggregate_id=str(tep["id"]),
                    payload=TepKetQuaDaThuHoi(
                        tep_id=str(tep["id"]),
                        visit_id=luot_tep,
                        service_order_id=so_id,
                    ),
                    boi=nguoi(identity),
                    correlation_id=luot_tep,
                )

        return {"ok": True, "id": str(tep["id"]), "trang_thai": "THU_HOI"}

    async def danh_sach(
        self, *, identity: StaffIdentity, clinic_patient_id: str
    ) -> list[dict[str, Any]]:
        """Tệp kết quả của một khách, mới nhất trước.

        Cùng luật đọc với nội dung tệp (`doc_duoc_tep_ket_qua`) — trước 27/09
        (đợt 3) cửa này chỉ xét vai nên người có lego mở được ảnh mà không
        liệt kê được ảnh.

        Chỉ tệp CÒN HIỆU LỰC (view `v_tep_ket_qua_hieu_luc`, V9 30/09): tệp đã
        xoá mềm hay đã thu hồi không hiện — trước đây tệp thu hồi vẫn lọt vào
        danh sách như thể còn là kết quả. Mỗi tệp kèm cờ máy chủ `xoa_duoc /
        xoa_loai / xoa_ly_do` (`xoa_duoc`) — giao diện chỉ hiện nút theo cờ.
        """
        async with self._pool.acquire() as conn:
            if not await doc_duoc_tep_ket_qua(conn, identity):
                raise SafetyGateError("Không có quyền xem tệp kết quả.")
            quyen = await quyen_xoa_tep(conn, identity)
            rows = await conn.fetch(
                f"""
                SELECT t.id::text, t.ten_hien_thi, t.loai_tep, t.mime, t.so_byte,
                       t.ben, t.tai_len_luc, t.gui_luc, t.gui_kenh,
                       t.cho_phep_gui_luc, t.appointment_id::text,
                       t.service_order_id::text,
                       t.xac_nhan_trang_thai, t.xac_nhan_luc, t.xac_nhan_ly_do,
                       t.thu_hoi_luc, t.thu_hoi_ly_do,
                       s.full_name AS tai_len_boi,
                       g.full_name AS gui_boi,
                       b.full_name AS cho_phep_gui_boi,
                       xn.full_name AS xac_nhan_boi,
                       th.full_name AS thu_hoi_boi,
                       {COT_XOA_SQL}
                  FROM public.v_tep_ket_qua_hieu_luc t
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
        # 200 tệp của MỘT khách: trần này gần như không bao giờ chạm, nhưng
        # chạm thì phải kêu — hàm trả về list nên không gắn `bi_cat` vào được.
        canh_bao_neu_day(
            "tep_ket_qua.cua_mot_khach", len(rows), 200, khach=clinic_patient_id
        )
        return [gan_co_xoa(r, quyen) for r in rows]

    async def da_xoa_gan_day(
        self, *, identity: StaffIdentity, clinic_patient_id: str
    ) -> list[dict[str, Any]]:
        """Tệp của khách đã xoá mềm trong 30 ngày, tệp vật lý còn — để hiện dòng
        "Đã xoá · Hoàn tác" (V9). Kèm `khoi_phuc_duoc` do máy chủ quyết."""
        async with self._pool.acquire() as conn:
            if not await doc_duoc_tep_ket_qua(conn, identity):
                raise SafetyGateError("Không có quyền xem tệp kết quả.")
            quyen = await quyen_xoa_tep(conn, identity)
            rows = await conn.fetch(
                f"""
                SELECT t.id::text, t.ten_hien_thi, t.loai_tep, t.mime, t.so_byte,
                       t.ben, t.tai_len_luc, t.appointment_id::text,
                       t.service_order_id::text,
                       x.full_name AS da_xoa_boi,
                       {COT_XOA_SQL}
                  FROM public.tep_ket_qua t
                  LEFT JOIN public.staff x ON x.id = t.da_xoa_boi_staff_id
                 WHERE t.clinic_id = $1::uuid AND t.clinic_patient_id = $2::uuid
                   AND t.da_xoa_luc IS NOT NULL AND t.da_don_tep_luc IS NULL
                   AND t.da_xoa_luc > now() - make_interval(days => $3)
                 ORDER BY t.da_xoa_luc DESC
                 LIMIT 100
                """,
                identity.clinic_id,
                clinic_patient_id,
                SO_NGAY_KHOI_PHUC,
            )
        return [gan_co_xoa(r, quyen) for r in rows]

    async def xoa_tep(
        self, *, identity: StaffIdentity, tep_id: str, ly_do: Any
    ) -> dict[str, Any]:
        """Xoá mềm một tệp kết quả (V9). Trong CÙNG giao dịch: ghi vết xoá, tính
        lại `service_order.ket_qua_luc`, nhật ký, phát `result_file.deleted`.
        Máy chủ tự chọn loại: tệp đã gửi khách / phiên đọc đã đóng → Đính chính.
        """
        ly_do_sach = chuan_ly_do_xoa(ly_do)
        cid = identity.clinic_id
        async with self._pool.acquire() as conn, conn.transaction():
            quyen = await quyen_xoa_tep(conn, identity)
            tep = await conn.fetchrow(
                f"""
                SELECT t.id::text AS id, t.service_order_id::text AS so_id,
                       t.appointment_id::text AS appt_id,
                       t.clinic_patient_id::text AS pid,
                       {COT_XOA_SQL}
                  FROM public.tep_ket_qua t
                 WHERE t.id = $1::uuid AND t.clinic_id = $2::uuid
                   FOR UPDATE OF t
                """,
                tep_id,
                cid,
            )
            if tep is None:
                raise NotFoundError("Không tìm thấy tệp này.")
            if tep["da_xoa_luc"] is not None:
                return {"ok": True, "id": tep["id"], "already": True}
            kq = xoa_duoc(tep, quyen)
            if not kq.duoc:
                raise SafetyGateError(kq.ly_do or "Bạn không xoá được tệp này.")
            loai = kq.loai or LOAI_XOA
            await conn.execute(
                "UPDATE public.tep_ket_qua"
                "   SET da_xoa_luc = now(), da_xoa_boi_staff_id = $3::uuid,"
                "       da_xoa_ly_do = $4, da_xoa_loai = $5"
                " WHERE id = $1::uuid AND clinic_id = $2::uuid"
                "   AND da_xoa_luc IS NULL",
                tep_id,
                cid,
                identity.staff_id,
                ly_do_sach,
                loai,
            )
            so_id = tep["so_id"]
            if so_id:
                await _tinh_lai_ket_qua_luc(conn, cid, so_id)
            await record_event(
                conn,
                event_type=(
                    "tep_ket_qua.dinh_chinh"
                    if loai == LOAI_DINH_CHINH
                    else "tep_ket_qua.xoa"
                ),
                aggregate_type="tep_ket_qua",
                aggregate_id=tep["id"],
                identity=identity,
                origin="api:tep-ket-qua:xoa",
                payload={
                    "loai": loai,
                    "ly_do": ly_do_sach,
                    "service_order_id": so_id,
                    "clinic_patient_id": tep["pid"],
                },
            )
            luot_tep = await _luot_cua_tep(conn, cid, so_id, tep["appt_id"])
            await emit_event(
                conn,
                ten="result_file.deleted",
                clinic_id=cid,
                aggregate_id=tep["id"],
                payload=TepKetQuaDaXoa(
                    tep_id=tep["id"],
                    visit_id=luot_tep,
                    service_order_id=so_id,
                    loai=loai,
                    ly_do=ly_do_sach,
                ),
                boi=nguoi(identity),
                correlation_id=luot_tep,
            )
            han = await conn.fetchval(
                "SELECT da_xoa_luc FROM public.tep_ket_qua"
                " WHERE id = $1::uuid AND clinic_id = $2::uuid",
                tep_id,
                cid,
            )
        logger.info(
            "tep_ket_qua_xoa", tep_id=tep_id, loai=loai, by_staff_id=identity.staff_id
        )
        moc = han_khoi_phuc(han)
        return {
            "ok": True,
            "id": tep["id"],
            "loai": loai,
            "khoi_phuc_han": moc.isoformat() if moc else None,
        }

    async def khoi_phuc_tep(
        self, *, identity: StaffIdentity, tep_id: str
    ) -> dict[str, Any]:
        """Khôi phục tệp đã xoá mềm (trong 30 ngày, tệp vật lý còn). Cùng giao
        dịch: gỡ vết xoá (trigger chỉ cho khi chưa dọn), đặt lại mốc "đã có kết
        quả" của chỉ định, nhật ký, phát `result_file.restored`."""
        cid = identity.clinic_id
        async with self._pool.acquire() as conn, conn.transaction():
            quyen = await quyen_xoa_tep(conn, identity)
            tep = await conn.fetchrow(
                f"""
                SELECT t.id::text AS id, t.service_order_id::text AS so_id,
                       t.appointment_id::text AS appt_id,
                       t.thu_hoi_luc, t.xac_nhan_trang_thai,
                       {COT_XOA_SQL}
                  FROM public.tep_ket_qua t
                 WHERE t.id = $1::uuid AND t.clinic_id = $2::uuid
                   FOR UPDATE OF t
                """,
                tep_id,
                cid,
            )
            if tep is None:
                raise NotFoundError("Không tìm thấy tệp này.")
            if tep["da_xoa_luc"] is None:
                return {"ok": True, "id": tep["id"], "already": True}
            kq = khoi_phuc_duoc(tep, quyen)
            if not kq.duoc:
                raise SafetyGateError(kq.ly_do or "Không khôi phục được tệp này.")
            await conn.execute(
                "UPDATE public.tep_ket_qua"
                "   SET da_xoa_luc = NULL, da_xoa_boi_staff_id = NULL,"
                "       da_xoa_ly_do = NULL, da_xoa_loai = NULL"
                " WHERE id = $1::uuid AND clinic_id = $2::uuid"
                "   AND da_don_tep_luc IS NULL",
                tep_id,
                cid,
            )
            so_id = tep["so_id"]
            con_la_ket_qua = tep["thu_hoi_luc"] is None and (
                tep["xac_nhan_trang_thai"] in (None, "CHO_XAC_NHAN", "HOP_LE")
            )
            if so_id and con_la_ket_qua:
                await conn.execute(
                    "UPDATE public.service_order"
                    "   SET ket_qua_luc = now(), updated_at = now()"
                    " WHERE id = $1::uuid AND clinic_id = $2::uuid"
                    "   AND ket_qua_luc IS NULL",
                    so_id,
                    cid,
                )
            await record_event(
                conn,
                event_type="tep_ket_qua.khoi_phuc",
                aggregate_type="tep_ket_qua",
                aggregate_id=tep["id"],
                identity=identity,
                origin="api:tep-ket-qua:khoi-phuc",
                payload={
                    "loai_da_xoa": tep["da_xoa_loai"],
                    "service_order_id": so_id,
                },
            )
            luot_tep = await _luot_cua_tep(conn, cid, so_id, tep["appt_id"])
            await emit_event(
                conn,
                ten="result_file.restored",
                clinic_id=cid,
                aggregate_id=tep["id"],
                payload=TepKetQuaDaKhoiPhuc(
                    tep_id=tep["id"], visit_id=luot_tep, service_order_id=so_id
                ),
                boi=nguoi(identity),
                correlation_id=luot_tep,
            )
        logger.info(
            "tep_ket_qua_khoi_phuc", tep_id=tep_id, by_staff_id=identity.staff_id
        )
        return {"ok": True, "id": tep["id"]}

    async def chi_dinh_cua_lich(
        self, *, identity: StaffIdentity, appointment_id: str
    ) -> list[dict[str, Any]]:
        """Chỉ định (còn hiệu lực) của lượt khám mở từ một lịch hẹn — để người
        tải tệp ở màn Khách hàng CHỌN tệp là kết quả của chỉ định nào (27/09,
        đợt 3). Cùng bộ lọc với lúc tải lên (`tai_len`: không nháp, không huỷ),
        nên chỉ định nào hiện ở đây thì máy chủ nhận. Không tự ghép theo tên.
        """
        async with self._pool.acquire() as conn:
            if not await doc_duoc_tep_ket_qua(conn, identity):
                raise SafetyGateError("Không có quyền xem tệp kết quả.")
            rows = await conn.fetch(
                "SELECT o.id::text AS service_order_id, o.service_name,"
                "       o.service_code, o.lan_chi_dinh AS lan"
                "  FROM public.service_order o"
                "  JOIN public.visit v"
                "    ON v.visit_id = o.visit_id AND v.clinic_id = o.clinic_id"
                " WHERE o.clinic_id = $1::uuid AND v.appointment_id = $2::uuid"
                "   AND o.exec_status NOT IN ('draft', 'cancelled')"
                "   AND coalesce(o.execution_status, '') <> 'CANCELLED'"
                " ORDER BY o.created_at, o.id",
                identity.clinic_id,
                appointment_id,
            )
        return [dict(r) for r in rows]

    async def duong_dan_de_doc(
        self, *, identity: StaffIdentity, tep_id: str
    ) -> tuple[Path, str, int, str]:
        """(đường dẫn, mime, số byte, tên hiển thị) — sau khi chứng minh quyền.

        Trả về ĐƯỜNG DẪN chứ không phải nội dung: video phải đi theo luồng, và
        một hàm trả `bytes` là một hàm buộc mọi lời gọi phải nạp cả tệp vào RAM.

        Quyền đọc:
        A. `doc_duoc_tep_ket_qua`: vai NORMAL_READ_ROLES, hoặc đọc được kết quả
           CLS theo lego (đợt 3, 27/09), hoặc khâu quầy in phiếu
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
              FROM public.v_tep_ket_qua_hieu_luc t
              LEFT JOIN public.service_order o
                ON o.id = t.service_order_id AND o.clinic_id = t.clinic_id
              LEFT JOIN public.node_definition n
                ON n.code = o.node_code AND n.clinic_id = t.clinic_id
             WHERE t.id = $1::uuid AND t.clinic_id = $2::uuid
            """,
            tep_id,
            identity.clinic_id,
        )
        # Tệp đã xoá mềm / đã thu hồi (V9): không mở được nữa — như không có.
        if row is None:
            raise NotFoundError("Không tìm thấy tệp này (có thể đã bị xoá).")

        # Vai cũ, lego đọc phiếu khám / kết quả (đợt 3), quầy in phiếu.
        async with self._pool.acquire() as conn:
            duoc_doc = await doc_duoc_tep_ket_qua(conn, identity)
        if not duoc_doc and await co_quyen_xac_nhan(self._pool, identity):
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

        # Chạm ổ mạng ở luồng phụ, có hạn giờ (sự cố treo API 29/09 20:00).
        def _giai() -> tuple[Path, bool, bool]:
            p = (MEDIA_ROOT / khoa).resolve()
            return p, p.is_relative_to(MEDIA_ROOT.resolve()), p.exists()

        path, trong_kho, con = await chay_tren_kho(_giai)
        if not trong_kho:
            raise ValidationError("Đường dẫn tệp không hợp lệ.")
        if not con:
            raise NotFoundError("Tệp không còn trên máy chủ — báo kỹ thuật.")
        if identity.co_vai(XEM_LA_DA_XEM):
            await self._ghi_da_xem(identity, tep_id, row["service_order_id"])
        return path, row["mime"], row["so_byte"], row["ten_hien_thi"] or ""

    async def _ghi_da_xem(
        self, identity: StaffIdentity, tep_id: str, service_order_id: str | None
    ) -> None:
        """Bác sĩ MỞ kết quả = đã xem (Tuyền chốt 24/09/2026: duyệt không bắt
        buộc; mở kết quả thì hệ thống TỰ ghi "đã xem lúc…"). Chỉ lần đầu."""
        async with self._pool.acquire() as conn, conn.transaction():
            moi = await conn.fetchval(
                "UPDATE public.tep_ket_qua"
                "   SET da_xem_luc = now(), da_xem_boi_staff_id = $3::uuid"
                " WHERE id = $1::uuid AND clinic_id = $2::uuid AND da_xem_luc IS NULL"
                "   AND da_xoa_luc IS NULL"
                " RETURNING id::text",
                tep_id,
                identity.clinic_id,
                identity.staff_id,
            )
            if moi is None:
                return
            luot_tep = await _luot_cua_tep(
                conn, identity.clinic_id, service_order_id, None
            )
            await emit_event(
                conn,
                ten="result_file.viewed",
                clinic_id=identity.clinic_id,
                aggregate_id=tep_id,
                payload=TepKetQuaDaXem(tep_id=tep_id, visit_id=luot_tep),
                boi=nguoi(identity),
                correlation_id=luot_tep,
            )

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
        # Tệp đã xoá mềm (V9) không gửi được — như không có. Tệp thu hồi vẫn
        # báo rõ "chưa hợp lệ để gửi" ở dưới.
        hien = await self._pool.fetchrow(
            "SELECT gui_luc, cho_phep_gui_luc, xac_nhan_trang_thai "
            "FROM public.tep_ket_qua "
            "WHERE id = $1::uuid AND clinic_id = $2::uuid AND da_xoa_luc IS NULL",
            tep_id,
            identity.clinic_id,
        )
        if hien is None:
            raise NotFoundError("Không tìm thấy tệp này (có thể đã bị xoá).")
        # KHÔNG CÒN ĐỢI BÁC SĨ CHO PHÉP (Tuyền chốt 23/09/2026: "cứ open đi,
        # cho gửi cũng được"). Luật 15/09 đã TẮT ở đây và ở trigger
        # `tep_ket_qua_gui_phai_duoc_cho_phep` (migration 20260923000021).
        # External files: phải ở HOP_LE. Internal (NULL): không yêu cầu.
        xn_state = hien.get("xac_nhan_trang_thai")
        if xn_state is not None and xn_state != "HOP_LE":
            raise ConflictError(
                "Tệp kết quả chưa ở trạng thái hợp lệ để gửi cho khách."
            )
        # External: vẫn phải HOP_LE (đúng người, đúng chỉ định). Internal: gửi được.
        where_extra = (
            "AND xac_nhan_trang_thai = 'HOP_LE'" if xn_state is not None else ""
        )
        async with self._pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow(
                f"""
                UPDATE public.tep_ket_qua
                   SET gui_luc = now(), gui_boi_staff_id = $1::uuid, gui_kenh = $2
                 WHERE id = $3::uuid AND clinic_id = $4::uuid AND gui_luc IS NULL
                   AND da_xoa_luc IS NULL
                   {where_extra}
                RETURNING id::text, service_order_id::text, appointment_id::text
                """,
                identity.staff_id,
                kenh,
                tep_id,
                identity.clinic_id,
            )
            if row is None:
                raise NotFoundError("Tệp này đã được gửi rồi.")
            luot_tep = await _luot_cua_tep(
                conn,
                identity.clinic_id,
                row["service_order_id"],
                row["appointment_id"],
            )
            await emit_event(
                conn,
                ten="result_file.sent_to_patient",
                clinic_id=identity.clinic_id,
                aggregate_id=tep_id,
                payload=KetQuaDaGuiKhach(tep_id=tep_id, visit_id=luot_tep, kenh=kenh),
                boi=nguoi(identity),
                correlation_id=luot_tep,
            )
        return {"ok": True}

    async def cho_phep_gui(
        self, *, identity: StaffIdentity, tep_id: str
    ) -> dict[str, Any]:
        """Bác sĩ đã xem tệp và cho phép CSKH gửi cho khách."""
        async with self._pool.acquire() as conn:
            # QUYỀN duyệt kết quả, không vai (28/09/2026).
            if not await can(conn, identity, "result.review.approve"):
                raise SafetyGateError("Bạn không có quyền cho phép gửi kết quả.")
            async with conn.transaction():
                hien = await conn.fetchrow(
                    "SELECT xac_nhan_trang_thai, cho_phep_gui_luc "
                    "FROM public.tep_ket_qua "
                    "WHERE id = $1::uuid AND clinic_id = $2::uuid"
                    "  AND da_xoa_luc IS NULL FOR UPDATE",
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
        async with self._pool.acquire() as c0:
            if not await can(c0, identity, "result.review.approve"):
                raise SafetyGateError("Bạn không có quyền duyệt kết quả.")
        rows = await self._pool.fetch(
            """
            SELECT t.id::text, t.ten_hien_thi, t.loai_tep, t.so_byte, t.tai_len_luc,
                   t.clinic_patient_id::text, p.full_name AS ten_khach,
                   p.patient_code, s.full_name AS tai_len_boi
              FROM public.v_tep_ket_qua_hieu_luc t
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
        # Hàng tồn "chờ cho phép gửi": chạm trần nghĩa là còn tệp chưa ai thấy.
        canh_bao_neu_day("tep_ket_qua.cho_cho_phep_gui", len(rows), 200)
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
              FROM public.v_tep_ket_qua_hieu_luc t
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
        canh_bao_neu_day("tep_ket_qua.cho_xac_nhan", len(rows), 100)
        return res
