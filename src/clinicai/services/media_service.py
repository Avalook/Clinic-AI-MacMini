"""Ảnh siêu âm — lưu trên đĩa máy chủ, không phải trong database.

Quang chọn (04/08/2026): lưu tạm trên máy Mac thay vì Supabase Storage.

VÌ SAO KHÔNG NHÉT VÀO DATABASE. Một ca siêu âm sinh ra vài ảnh, mỗi ảnh hàng
trăm KB; database hiện 20MB cho toàn bộ bệnh án của bốn tháng. Nhét ảnh vào đó
là làm mọi bản sao lưu, mọi lần khôi phục và mọi truy vấn nặng lên hàng trăm
lần để đổi lấy một tiện lợi duy nhất: đỡ phải nghĩ về tệp.

ĐÂY LÀ DỮ LIỆU BỆNH NHÂN. Ba điều được thi hành ở đây, không phải ở giao diện:

  1. TÊN TỆP DO HỆ THỐNG ĐẶT, không lấy từ người tải lên. Tên do client gửi có
     thể là "../../../etc/passwd" hoặc "…/.env"; ghép nó vào đường dẫn là mở
     đường ghi ra ngoài thư mục. Tên thật chỉ được giữ lại làm nhãn hiển thị.
  2. ĐƯỜNG DẪN LUÔN BẮT ĐẦU BẰNG clinic_id. Hai phòng khám không bao giờ đọc
     được tệp của nhau kể cả khi một truy vấn nào đó sai.
  3. CHỈ NHẬN ẢNH, và kiểm bằng NỘI DUNG chứ không bằng đuôi tệp. Một tệp
     "abc.jpg" chứa mã HTML sẽ được trình duyệt chạy nếu phục vụ sai kiểu.
"""

from __future__ import annotations

import hashlib
import os
import uuid
from pathlib import Path
from typing import Any

import asyncpg
import structlog

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.core.kho_tep import chay_tren_kho, han_theo_co

logger = structlog.get_logger()

#: Trong container: /var/lib/clinicai/media (ổ bind từ ./.media trên máy).
MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", "./.media/production"))


#: KHO GẮN NGOÀI PHẢI THẬT SỰ ĐANG GẮN (Tuyền 16/09/2026: lưu tệp vào Viettel
#: Cloud File Storage, không lưu trên ổ VPS).
#:
#: Kho ấy là một ổ mạng gắn vào máy chủ. Ổ rớt kết nối, hay máy khởi động lại mà
#: Docker lên TRƯỚC ổ mạng, thì thư mục bind trỏ vào ổ VPS bên dưới — ghi vẫn
#: thành công, và ảnh bệnh nhân nằm sai chỗ mà không ai biết. Nên khi cấu hình
#: `MEDIA_MARKER`, tệp đánh dấu ấy (chỉ có trên kho thật) phải có mặt thì mới ghi.
#: Đọc biến lúc gọi, không lúc import: đổi cấu hình chỉ cần khởi động lại.
def kiem_kho_da_gan() -> None:
    dau = os.environ.get("MEDIA_MARKER", "").strip()
    if dau and not (MEDIA_ROOT / dau).is_file():
        logger.error("kho_media_chua_gan", media_root=str(MEDIA_ROOT), marker=dau)
        raise ValidationError(
            "Kho lưu tệp (Viettel File Storage) đang không kết nối — tệp CHƯA "
            "được lưu. Báo kỹ thuật kiểm tra ổ lưu trữ rồi tải lại."
        )


#: 12MB. Máy siêu âm xuất ảnh khoảng 200KB–2MB; 12MB là rộng rãi mà vẫn chặn
#: được một video bị kéo nhầm vào ô ảnh.
MAX_BYTES = 12 * 1024 * 1024


#: Trần theo TỪNG LOẠI, không dùng chung một con số.
#:
#: Một con số duy nhất buộc phải lấy theo cái lớn nhất — và khi đó ô "chọn ảnh"
#: cũng nhận một video 80MB, rồi màn siêu âm cố hiển thị nó như ảnh. Video có
#: trần riêng và đọc từ môi trường, vì nó là thứ duy nhất ở đây đủ lớn để một
#: phòng khám cần chỉnh mà không sửa code.
#: KHÔNG GIỚI HẠN DUNG LƯỢNG TỆP KẾT QUẢ (Tuyền 16/09/2026: *"không giới hạn
#: dung lượng file đẩy lên nhé"*). Video siêu âm, phim chụp có thể vài GB.
#:
#: 0 = không giới hạn. Vẫn đặt lại được từng loại bằng biến môi trường
#: (MEDIA_MAX_BYTES_ANH / _VIDEO / _PDF / _TAI_LIEU) nếu sau này phòng khám cần.
#: An toàn còn lại là chốt Ổ ĐĨA SẮP ĐẦY (`MEDIA_MIN_FREE_BYTES`) — đó không phải
#: trần dung lượng mà là chống làm hỏng máy.
def _tran(loai: str) -> int:
    return int(os.environ.get(f"MEDIA_MAX_BYTES_{loai}", "0") or 0)


MAX_BYTES_VIDEO = _tran("VIDEO")
MAX_BYTES_PDF = _tran("PDF")
MAX_BYTES_THEO_LOAI: dict[str, int] = {
    "ANH": _tran("ANH"),
    "VIDEO": MAX_BYTES_VIDEO,
    "PDF": MAX_BYTES_PDF,
    "TAI_LIEU": _tran("TAI_LIEU"),
}


def vuot_tran(loai: str, so_byte: int) -> int | None:
    """Trần của loại tệp nếu `so_byte` vượt nó; None = không vượt/không trần."""
    tran = MAX_BYTES_THEO_LOAI.get(loai, 0)
    return tran if tran > 0 and so_byte > tran else None


# Video kết quả chưa có kho/vòng đời vận hành an toàn (UI cũng đang nói rõ là
# chưa nhận). Giữ nhận diện để đọc dữ liệu cũ, nhưng đường upload chỉ mở khi
# người vận hành chủ động cấu hình sau khi có quota/backup phù hợp.
KET_QUA_VIDEO_UPLOAD_ENABLED = os.environ.get(
    "KET_QUA_VIDEO_UPLOAD_ENABLED", "false"
).lower() in {"1", "true", "yes"}
KET_QUA_UPLOAD_ALLOWED_TYPES = (
    frozenset({"ANH", "PDF", "VIDEO", "TAI_LIEU"})
    if KET_QUA_VIDEO_UPLOAD_ENABLED
    else frozenset({"ANH", "PDF", "TAI_LIEU"})
)
#: 0 = không giới hạn (khi BẤT KỲ loại nào không có trần).
MAX_BYTES_KET_QUA_UPLOAD = (
    0
    if any(MAX_BYTES_THEO_LOAI[loai] <= 0 for loai in KET_QUA_UPLOAD_ALLOWED_TYPES)
    else max(MAX_BYTES_THEO_LOAI[loai] for loai in KET_QUA_UPLOAD_ALLOWED_TYPES)
)


def ket_qua_patient_lock_key(*, clinic_id: str, clinic_patient_id: str) -> str:
    """Shared DB advisory-lock namespace for upload/delivery transitions."""
    return f"cskh-ket-qua:{clinic_id}:{clinic_patient_id}"


#: Nhận diện bằng CHỮ KÝ ĐẦU TỆP, không bằng đuôi tên. Đuôi là thứ người tải
#: lên tự đặt; mấy byte đầu là thứ tệp thật sự là.
_MAGIC: tuple[tuple[bytes, str, str], ...] = (
    (b"\xff\xd8\xff", "image/jpeg", ".jpg"),
    (b"\x89PNG\r\n\x1a\n", "image/png", ".png"),
    (b"DICM", "application/dicom", ".dcm"),
)


#: Chữ ký cho TỆP KẾT QUẢ (đường CSKH): ảnh + video + phiếu PDF.
#:
#: MP4/MOV để `ftyp` ở BYTE THỨ 4, không phải đầu tệp — cùng kiểu bẫy như DICOM.
#: Kiểm bằng đuôi `.mp4` thì một tệp `.mp4` chứa HTML sẽ được trình duyệt chạy
#: nếu phục vụ sai kiểu; đây là dữ liệu bệnh nhân, không phải ảnh đại diện.
_MAGIC_KET_QUA: tuple[tuple[bytes, str, str, str], ...] = (
    (b"\xff\xd8\xff", "image/jpeg", ".jpg", "ANH"),
    (b"\x89PNG\r\n\x1a\n", "image/png", ".png", "ANH"),
    (b"%PDF-", "application/pdf", ".pdf", "PDF"),
    (b"\x1a\x45\xdf\xa3", "video/webm", ".webm", "VIDEO"),
    (b"GIF87a", "image/gif", ".gif", "ANH"),
    (b"GIF89a", "image/gif", ".gif", "ANH"),
)

#: Ảnh iPhone (HEIC) và AVIF cũng mở đầu bằng khối `ftyp` như MP4. Bản trước
#: không phân biệt nên một ảnh HEIC được cất thành VIDEO MP4 — lưu được mà không
#: xem được (tự kiểm 16/09/2026). Trình duyệt trên máy tính phòng khám không hiển
#: thị HEIC, nên TỪ CHỐI kèm câu nói rõ cách xử lý.
_FTYP_ANH_KHONG_XEM_DUOC = frozenset(
    {
        b"heic",
        b"heix",
        b"hevc",
        b"heim",
        b"heis",
        b"hevm",
        b"hevs",
        b"mif1",
        b"msf1",
        b"avif",
        b"avis",
    }
)

#: Tài liệu Office (DOCX/XLSX) là tệp ZIP. Word/Excel đặt `[Content_Types].xml`
#: ngay đầu tệp; phân biệt DOCX/XLSX bằng thư mục `word/` hay `xl/` bên trong.
_MIME_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

#: Nhãn con của khối `ftyp` → kiểu thật. `qt  ` là MOV (máy siêu âm Mỹ hay xuất
#: kiểu này), phần còn lại coi là MP4.
_FTYP_MOV = frozenset({b"qt  "})


def sniff_ket_qua(data: bytes) -> tuple[str, str, str]:
    """Kiểu thật của một tệp kết quả: (mime, đuôi, loại). Hoặc từ chối.

    Trả về LOẠI chứ không chỉ mime, vì loại quyết định hai thứ khác nhau: trần
    dung lượng, và cách màn hình hiển thị nó (thẻ img hay thẻ video).
    """
    for magic, mime, ext, loai in _MAGIC_KET_QUA:
        if data.startswith(magic):
            return mime, ext, loai
    # WEBP: "RIFF" + 4 byte độ dài + "WEBP". (AVI cũng "RIFF" — không nhận.)
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp", ".webp", "ANH"
    if data.startswith(b"PK\x03\x04"):
        if b"word/" in data:
            return _MIME_DOCX, ".docx", "TAI_LIEU"
        if b"xl/" in data:
            return _MIME_XLSX, ".xlsx", "TAI_LIEU"
        # Chỉ có đoạn đầu tệp (lúc đọc thử để biết trần dung lượng): đủ biết là
        # tài liệu Office; loại cụ thể quyết khi có trọn tệp.
        if b"[Content_Types].xml" in data[:4096] and len(data) <= 8192:
            return _MIME_DOCX, ".docx", "TAI_LIEU"
        raise ValidationError(
            "Tệp nén (ZIP) không nhận. Tài liệu chỉ nhận Word (.docx) hoặc Excel "
            "(.xlsx)."
        )
    # DICOM: chữ ký nằm ở byte 128. Loại TAI_LIEU, không phải ANH (27/09/2026,
    # đợt 3): trình duyệt không vẽ được DICOM — coi là ảnh thì ô xem nhanh và
    # trang ảnh của bản in thành khung trống. Nhận để lưu + tải về.
    if len(data) > 132 and data[128:132] == b"DICM":
        return "application/dicom", ".dcm", "TAI_LIEU"
    # MP4/MOV: `ftyp` ở byte 4, nhãn con ở byte 8.
    if len(data) > 12 and data[4:8] == b"ftyp":
        if data[8:12] in _FTYP_ANH_KHONG_XEM_DUOC:
            raise ValidationError(
                "Ảnh HEIC/AVIF (thường từ iPhone) chưa xem được trên máy tính phòng "
                "khám. Trên iPhone chọn Cài đặt → Camera → Định dạng → Tương thích "
                "nhất, hoặc gửi ảnh chụp màn hình (JPG/PNG)."
            )
        if data[8:12] in _FTYP_MOV:
            return "video/quicktime", ".mov", "VIDEO"
        return "video/mp4", ".mp4", "VIDEO"
    raise ValidationError(
        "Chỉ nhận ảnh (JPG/PNG/WEBP/GIF/DICOM), video (MP4/MOV/WebM), phiếu PDF, "
        "tài liệu Word (.docx) hoặc Excel (.xlsx)."
    )


def phan_tich_range(rng: str | None, so_byte: int) -> tuple[int, int] | None:
    """`bytes=START-END` → (đầu, cuối) đã kẹp vào tệp. None = trả trọn tệp.

    Trả về `(1, 0)` — một khoảng rỗng — khi yêu cầu nằm NGOÀI tệp, để lời gọi
    biết mà trả 416. Trình phát video hỏi khoảng vượt cuối tệp là chuyện bình
    thường; trả 200 kèm trọn tệp cho một câu hỏi như thế là bắt trình duyệt tải
    lại từ đầu mỗi lần người xem kéo thanh tua tới cuối.

    Đây là hàm THUẦN và nằm ngoài route có lý do: nó là phần duy nhất của đường
    phục vụ video có nhiều nhánh, và nhét nó trong một route thì mỗi nhánh phải
    kiểm bằng một request thật.
    """
    if not rng or not rng.startswith("bytes=") or so_byte <= 0:
        return None
    phan = rng.removeprefix("bytes=").split("-", 1)
    try:
        # `bytes=-500` = 500 byte CUỐI. Trình phát dùng dạng này để đọc chỉ mục
        # MP4 nằm ở đuôi tệp; hiểu nhầm nó thành "từ byte 0" là tải cả video.
        if not phan[0]:
            n = int(phan[1]) if len(phan) > 1 and phan[1] else 0
            if n <= 0:
                return None
            return (max(0, so_byte - n), so_byte - 1)
        dau = int(phan[0])
        cuoi = int(phan[1]) if len(phan) > 1 and phan[1] else so_byte - 1
    except ValueError:
        return None
    dau = max(0, dau)
    cuoi = min(cuoi, so_byte - 1)
    return (dau, cuoi)


def duong_dan_ket_qua(
    *, clinic_id: str, clinic_patient_id: str, ext: str
) -> tuple[Path, str]:
    """Đường dẫn trên đĩa + khoá lưu vào database, cho tệp kết quả của CSKH.

    Cùng luật với `safe_path`: không một phần nào của đường dẫn đến từ người
    dùng, và mọi thứ bắt đầu bằng clinic_id nên hai phòng khám không đọc được
    tệp của nhau kể cả khi một truy vấn nào đó sai.
    """
    key = f"{clinic_id}/ket-qua/{clinic_patient_id}/{uuid.uuid4().hex}{ext}"
    return (MEDIA_ROOT / key), key


def sniff(data: bytes) -> tuple[str, str]:
    """Kiểu thật của tệp, hoặc từ chối.

    DICOM để chữ ký `DICM` ở byte 128 chứ không phải đầu tệp — máy siêu âm xuất
    thẳng DICOM là chuyện thường, và nhận nhầm nó thành "không phải ảnh" sẽ đẩy
    kỹ thuật viên sang chép tay qua USB.
    """
    for magic, mime, ext in _MAGIC:
        if magic == b"DICM":
            if len(data) > 132 and data[128:132] == b"DICM":
                return mime, ext
        elif data.startswith(magic):
            return mime, ext
    raise ValidationError(
        "Chỉ nhận ảnh JPG, PNG hoặc tệp DICOM. Tệp này không phải ảnh."
    )


def safe_path(*, clinic_id: str, ultrasound_id: str, ext: str) -> tuple[Path, str]:
    """Đường dẫn tuyệt đối trên đĩa, và khoá tương đối để lưu vào database.

    Không một phần nào của đường dẫn đến từ người dùng: clinic_id và
    ultrasound_id là UUID đã qua kiểm kiểu, tên tệp là UUID mới sinh. Nên không
    có gì để thoát ra khỏi thư mục.
    """
    key = f"{clinic_id}/ultrasound/{ultrasound_id}/{uuid.uuid4().hex}{ext}"
    return (MEDIA_ROOT / key), key


class MediaService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def attach_ultrasound_image(
        self,
        *,
        identity: StaffIdentity,
        ultrasound_id: str,
        data: bytes,
        display_name: str | None,
    ) -> dict[str, Any]:
        """Gắn một ảnh vào bản ghi siêu âm."""
        if not data:
            raise ValidationError("Tệp rỗng.")
        if len(data) > MAX_BYTES:
            raise ValidationError(
                f"Ảnh quá lớn ({len(data) // 1024 // 1024}MB). "
                f"Tối đa {MAX_BYTES // 1024 // 1024}MB."
            )
        mime, ext = sniff(data)

        async with self._pool.acquire() as conn, conn.transaction():
            rec = await conn.fetchrow(
                "SELECT ultrasound_id, signed_at FROM public.ultrasound_record"
                " WHERE ultrasound_id = $1::uuid AND clinic_id = $2::uuid",
                ultrasound_id,
                identity.clinic_id,
            )
            if rec is None:
                raise ValidationError("Không tìm thấy bản ghi siêu âm.")
            # ĐÃ KÝ THÌ KHOÁ, kể cả việc thêm ảnh. Một phiếu đã ký mà ảnh vẫn
            # thay đổi được thì chữ ký không còn nói lên điều gì — bác sĩ ký cái
            # họ đã nhìn thấy.
            if rec["signed_at"] is not None:
                raise ValidationError(
                    "Kết quả đã ký — không thêm ảnh được. Phải qua đường đính chính."
                )

            await chay_tren_kho(kiem_kho_da_gan)
            path, key = safe_path(
                clinic_id=identity.clinic_id, ultrasound_id=ultrasound_id, ext=ext
            )
            # Ghi ra tệp tạm rồi đổi tên: một lần ghi bị cắt giữa chừng (hết
            # đĩa, mất điện) để lại tệp tạm, không để lại một ảnh hỏng mà
            # database vẫn khai là có.
            tmp = path.with_suffix(path.suffix + ".tmp")

            def _ghi() -> None:
                path.parent.mkdir(parents=True, exist_ok=True)
                tmp.write_bytes(data)
                tmp.replace(path)
                path.chmod(0o600)

            # Luồng phụ có hạn (29/09): ổ Viettel treo → báo "kho chậm", giao
            # dịch huỷ, API không treo. Ảnh ≤ 12MB nên một lần là đủ.
            await chay_tren_kho(_ghi, han=han_theo_co(len(data)))

            await conn.execute(
                "UPDATE public.ultrasound_record"
                "   SET image_refs = array_append(coalesce(image_refs, '{}'), $2),"
                "       updated_at = now()"
                # clinic_id ở đây là THỪA về mặt logic (câu SELECT ngay trên đã
                # xác nhận bản ghi thuộc phòng khám này, cùng transaction) —
                # nhưng backend chạy bằng service role và BỎ QUA RLS, nên mọi
                # câu chạm bảng của tenant phải tự mang bộ lọc. Thừa thì không
                # mất gì; thiếu thì một lần sửa sau này biến nó thành lỗ thật.
                " WHERE ultrasound_id = $1::uuid AND clinic_id = $3::uuid",
                ultrasound_id,
                key,
                identity.clinic_id,
            )

        logger.info(
            "ultrasound_image_attached",
            ultrasound_id=ultrasound_id,
            bytes=len(data),
            mime=mime,
            by_staff_id=identity.staff_id,
        )
        return {
            "ok": True,
            "key": key,
            "mime": mime,
            "bytes": len(data),
            # Tên người tải lên đặt CHỈ để hiển thị, không bao giờ chạm đĩa.
            "display_name": (display_name or "").strip()[:120] or None,
            "sha256": hashlib.sha256(data).hexdigest()[:16],
        }

    async def read_ultrasound_image(
        self, *, identity: StaffIdentity, key: str
    ) -> tuple[bytes, str]:
        """Đọc một ảnh, sau khi xác nhận nó thuộc phòng khám của người hỏi.

        KHÔNG tin `key` từ trình duyệt. Nó phải (a) bắt đầu bằng đúng clinic_id
        của người đang đăng nhập, và (b) thật sự nằm trong `image_refs` của một
        bản ghi thuộc phòng khám đó. Thiếu phép kiểm thứ hai thì đoán được một
        UUID là đọc được ảnh của bệnh nhân bất kỳ.
        """
        if not key.startswith(f"{identity.clinic_id}/"):
            raise ValidationError("Ảnh không thuộc phòng khám này.")

        owned = await self._pool.fetchval(
            "SELECT 1 FROM public.ultrasound_record"
            " WHERE clinic_id = $1::uuid AND $2 = ANY(image_refs) LIMIT 1",
            identity.clinic_id,
            key,
        )
        if not owned:
            raise ValidationError("Không tìm thấy ảnh.")

        # Chốt cuối: dù hai phép kiểm trên có sai, đường dẫn giải ra vẫn phải
        # nằm trong thư mục media. Chạm ổ mạng ở luồng phụ, có hạn giờ (sự
        # cố treo API 29/09 20:00).
        def _doc() -> bytes | None:
            p = (MEDIA_ROOT / key).resolve()
            if not p.is_relative_to(MEDIA_ROOT.resolve()):
                raise ValidationError("Đường dẫn ảnh không hợp lệ.")
            return p.read_bytes() if p.exists() else None

        doc = await chay_tren_kho(_doc)
        if doc is None:
            raise ValidationError("Tệp ảnh không còn trên máy chủ — báo kỹ thuật.")
        data = doc
        mime, _ = sniff(data)
        return data, mime
