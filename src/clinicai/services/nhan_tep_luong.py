"""Nhận một lượt tải tệp multipart THEO LUỒNG, ghi thẳng vào kho media.

VÌ SAO KHÔNG DÙNG `UploadFile` (Tuyền chốt 16/09/2026: không giới hạn dung lượng).

`UploadFile` của Starlette cất trọn thân request ra một tệp tạm trước, rồi service
mới chép tệp tạm ấy sang chỗ ở thật. Đo trên final cloud cùng ngày: video 2GB lên
tệp tạm trong ~1 phút, rồi mất thêm vài phút chép lại từ kho Viettel sang chính kho
Viettel (~9MB/s, qua mạng hai chiều). Tệp càng lớn càng phí gấp đôi, và kho tạm
phải có chỗ cho BẢN SAO THỨ HAI của tệp lớn nhất.

Ở đây thân request chảy thẳng vào `<MEDIA_ROOT>/.tam/<ngẫu nhiên>.part` — cùng kho
với chỗ ở thật — nên service chỉ còn ĐỔI TÊN, không chép lại byte nào.

Và một lợi ích an toàn: route dùng cửa này không khai `Form`/`File`, nên FastAPI
kiểm quyền (dependency) TRƯỚC khi đọc byte nào của thân. Với `UploadFile`, một
người không có quyền vẫn đẩy trọn vài GB lên máy chủ rồi mới nhận 403.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO

from python_multipart.multipart import MultipartParser, parse_options_header
from starlette.requests import ClientDisconnect, Request

from clinicai.api.exceptions import ValidationError
from clinicai.core.kho_tep import chay_tren_kho
from clinicai.services.media_service import (
    KET_QUA_VIDEO_UPLOAD_ENABLED,
    MEDIA_ROOT,
    kiem_kho_da_gan,
    sniff_ket_qua,
    vuot_tran,
)

#: Số byte đầu dùng để nhận kiểu tệp (đủ cho mọi chữ ký trong sniff_ket_qua).
SO_BYTE_DAU = 8192
#: Gom tới chừng này rồi mới ghi một lần — mỗi lần ghi lên ổ mạng là một vòng đi về.
_GOM_GHI = 4 * 1024 * 1024
#: Trường chữ (mã khách, mã chỉ định…) chỉ vài chục ký tự; quá thế là rác.
_TRAN_TRUONG_CHU = 4096


@dataclass
class TepDaNhan:
    """Tệp đã nằm trọn trên kho, chờ service đổi tên về chỗ ở thật."""

    duong: Path
    so_byte: int
    sha256: str
    dau: bytes
    ten: str | None


@dataclass
class _Phan:
    ten_truong: str = ""
    ten_tep: str | None = None
    la_tep: bool = False
    chu: bytearray = field(default_factory=bytearray)


def thu_muc_tam() -> Path:
    return MEDIA_ROOT / ".tam"


def _mo_ghi(duong: Path) -> IO[bytes]:
    duong.parent.mkdir(parents=True, exist_ok=True)
    return duong.open("xb")


async def nhan_multipart(
    request: Request, *, truong_tep: str = "file"
) -> tuple[dict[str, str], TepDaNhan]:
    """Đọc thân multipart: trả (các trường chữ, tệp đã ghi xong trên kho).

    Lỗi ở bất kỳ bước nào → tệp `.part` bị xoá trước khi ném lỗi ra ngoài.
    """
    loai_noi_dung, tham_so = parse_options_header(request.headers.get("content-type"))
    ranh_gioi = tham_so.get(b"boundary")
    if loai_noi_dung != b"multipart/form-data" or not ranh_gioi:
        raise ValidationError("Yêu cầu tải tệp phải là multipart/form-data.")

    await chay_tren_kho(kiem_kho_da_gan)
    try:
        khai = int(request.headers.get("content-length") or 0)
    except ValueError:
        khai = 0
    # Khoảng trống an toàn kiểm TRƯỚC khi nhận byte nào; service kiểm lại lần nữa.
    from clinicai.services.tep_ket_qua_service import MEDIA_MIN_FREE_BYTES

    if khai and shutil.disk_usage(MEDIA_ROOT).free - khai < MEDIA_MIN_FREE_BYTES:
        raise ValidationError(
            "Máy chủ không còn đủ dung lượng trống an toàn để lưu tệp. "
            "Báo kỹ thuật dọn hoặc mở rộng ổ đĩa."
        )

    duong = thu_muc_tam() / f"{uuid.uuid4().hex}.part"
    truong: dict[str, str] = {}
    phan = _Phan()
    so_phan_tep = 0
    tieu_de: dict[str, bytes] = {"ten": b"", "gia_tri": b""}
    cac_tieu_de: dict[bytes, bytes] = {}
    cho_ghi = bytearray()
    loi: list[str] = []

    def dau_phan() -> None:
        nonlocal phan
        phan = _Phan()
        cac_tieu_de.clear()

    def ten_tieu_de(data: bytes, start: int, end: int) -> None:
        tieu_de["ten"] += data[start:end]

    def gia_tri_tieu_de(data: bytes, start: int, end: int) -> None:
        tieu_de["gia_tri"] += data[start:end]

    def het_tieu_de() -> None:
        cac_tieu_de[tieu_de["ten"].lower()] = tieu_de["gia_tri"]
        tieu_de["ten"] = b""
        tieu_de["gia_tri"] = b""

    def xong_tieu_de() -> None:
        nonlocal so_phan_tep
        _, opts = parse_options_header(cac_tieu_de.get(b"content-disposition"))
        phan.ten_truong = opts.get(b"name", b"").decode("utf-8", "replace")
        if b"filename" in opts:
            phan.la_tep = True
            phan.ten_tep = opts[b"filename"].decode("utf-8", "replace")
            if phan.ten_truong != truong_tep:
                loi.append(f"Trường tệp không đúng tên '{truong_tep}'.")
            so_phan_tep += 1
            if so_phan_tep > 1:
                loi.append("Mỗi lần chỉ gửi một tệp.")

    def du_lieu(data: bytes, start: int, end: int) -> None:
        if phan.la_tep:
            cho_ghi.extend(data[start:end])
        else:
            phan.chu.extend(data[start:end])
            if len(phan.chu) > _TRAN_TRUONG_CHU:
                loi.append("Trường chữ quá dài.")

    ten_tep: list[str | None] = [None]

    def het_phan() -> None:
        if phan.la_tep:
            ten_tep[0] = phan.ten_tep
        elif phan.ten_truong:
            truong[phan.ten_truong] = phan.chu.decode("utf-8", "replace").strip()

    parser = MultipartParser(
        ranh_gioi,
        {
            "on_part_begin": dau_phan,
            "on_header_field": ten_tieu_de,
            "on_header_value": gia_tri_tieu_de,
            "on_header_end": het_tieu_de,
            "on_headers_finished": xong_tieu_de,
            "on_part_data": du_lieu,
            "on_part_end": het_phan,
        },
    )

    h = hashlib.sha256()
    so_byte = 0
    dau = bytearray()
    da_nhan_kieu = False
    loai = ""
    tep: IO[bytes] | None = None

    async def ghi_ra(het: bool) -> None:
        nonlocal so_byte, da_nhan_kieu, loai, tep
        if not cho_ghi:
            return
        if so_byte == 0:
            # Chưa ghi byte nào → `cho_ghi` vẫn chứa tệp TỪ BYTE ĐẦU TIÊN.
            dau[:] = cho_ghi[:SO_BYTE_DAU]
        if not da_nhan_kieu and (len(dau) >= SO_BYTE_DAU or het):
            # Nhận kiểu NGAY KHI có đủ byte đầu: tệp rác bị từ chối trước khi
            # kịp chiếm vài GB trên kho.
            _mime, _ext, loai = sniff_ket_qua(bytes(dau))
            if loai == "VIDEO" and not KET_QUA_VIDEO_UPLOAD_ENABLED:
                raise ValidationError(
                    "Video kết quả chưa được bật. Hiện chỉ nhận ảnh hoặc phiếu PDF."
                )
            da_nhan_kieu = True
        if not het and not da_nhan_kieu:
            return
        if len(cho_ghi) < _GOM_GHI and not het:
            return
        khuc = bytes(cho_ghi)
        cho_ghi.clear()
        h.update(khuc)
        so_byte += len(khuc)
        if loai:
            tran = vuot_tran(loai, so_byte)
            if tran is not None:
                raise ValidationError(
                    f"Tệp quá lớn. Tối đa {tran // 1024 // 1024}MB cho loại này."
                )
        if tep is None:
            tep = await asyncio.to_thread(_mo_ghi, duong)
        await asyncio.to_thread(tep.write, khuc)

    try:
        try:
            async for chunk in request.stream():
                parser.write(chunk)
                if loi:
                    raise ValidationError(loi[0])
                await ghi_ra(het=False)
            parser.finalize()
        except ClientDisconnect as e:
            raise ValidationError(
                "Mất kết nối giữa chừng — tệp CHƯA được lưu, hãy tải lại."
            ) from e
        if loi:
            raise ValidationError(loi[0])
        await ghi_ra(het=True)
        if so_phan_tep == 0 or so_byte == 0 or tep is None:
            raise ValidationError("Tệp rỗng.")
        await asyncio.to_thread(tep.close)
        tep = None
        return truong, TepDaNhan(
            duong=duong,
            so_byte=so_byte,
            sha256=h.hexdigest(),
            dau=bytes(dau),
            ten=ten_tep[0],
        )
    except BaseException:
        if tep is not None:
            await asyncio.to_thread(tep.close)
        await asyncio.to_thread(_xoa, duong)
        raise


def _xoa(duong: Path) -> None:
    try:
        os.unlink(duong)
    except FileNotFoundError:
        pass


def uuid_hoac_loi(gia_tri: str | None, ten: str, *, bat_buoc: bool) -> str | None:
    """Trường mã dạng UUID: rỗng → None (nếu không bắt buộc); sai dạng → 422."""
    if not gia_tri:
        if bat_buoc:
            raise ValidationError(f"Thiếu {ten}.")
        return None
    try:
        return str(uuid.UUID(gia_tri))
    except ValueError as e:
        raise ValidationError(f"{ten} không hợp lệ.") from e
