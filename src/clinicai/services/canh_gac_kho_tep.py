"""CANH GÁC KHO TỆP (29/09/2026) — tự đo ổ Viettel CFS mỗi phút.

Sự cố 29/09 ~19:15: ổ CIFS gắn ở ``/mnt/viettel-cfs`` (trong container là
``MEDIA_ROOT``) đọc chỉ còn ~69KB/s, mất gói — người dùng kêu trước khi mình
biết. Phép đo này ghi rồi đọc lại một tệp đo 256KB cố định
(``MEDIA_ROOT/.canh-gac/do-toc-do.bin``) và mở cảnh báo ``KHO_TEP_CHAM`` qua
đúng cơ chế của bộ canh gác (bảng ``canh_bao`` → /ops "Lỗi & cảnh báo" +
Telegram ops nếu đã cấu hình).

VÌ SAO CHẠY TRONG API, KHÔNG TRONG ``su-kien``: container ``su-kien`` không gắn
thư mục media. Gắn thêm thì người đưa tin sự kiện — thứ bắt buộc chạy để khách
vào hàng — phụ thuộc thêm một ổ mạng có thể treo. API vốn đã gắn ổ ấy, và đo từ
API là đo đúng con đường người dùng đang đi.

AN TOÀN CHO API:
  · Mọi thao tác đĩa chạy ở MỘT luồng daemon riêng, có hạn giờ; vòng sự kiện
    chỉ chờ một future. Ổ treo thì luồng treo, vòng sự kiện không.
  · Tối đa MỘT phép đo đang bay: lần trước còn treo thì lần này tính là "treo"
    luôn, không đẻ thêm luồng (luồng treo trên ổ mạng không huỷ được).
  · Không dùng ngắt mạch chung ``core.kho_tep`` — phép đo không được làm tắt
    đường mở tệp của người dùng, và phải đo được cả khi ngắt mạch đang bật.
  · Không bao giờ ném.

CHỐNG NHÁY: chậm 2 lần liên tiếp mới mở, ổn 2 lần liên tiếp mới đóng.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import os
import sys
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import asyncpg
import structlog

from clinicai.services.canh_gac import NHIP_GIAY, KetQuaKiem, ap_dung

logger = structlog.get_logger()

MA = "KHO_TEP_CHAM"
CO_TEP_DO = 256 * 1024
#: 256KB mất quá 3 giây ≈ dưới 85KB/s. Bình thường ổ này > 1MB/s.
NGUONG_CHAM_GIAY = 3.0
#: Quá hạn thì thôi chờ (luồng vẫn treo đó, lần sau không đẻ thêm).
HAN_GIAY = 10.0
SO_LAN_LIEN_TIEP = 2
THU_MUC_DO = ".canh-gac"
TEN_TEP_DO = "do-toc-do.bin"


@dataclass(frozen=True)
class PhepDo:
    """Một lần đo. ``loi`` khác rỗng = không đo được (treo / lỗi / chưa gắn)."""

    luc: str
    doc_giay: float | None = None
    ghi_giay: float | None = None
    loi: str = ""

    @property
    def doc_kb_s(self) -> float | None:
        return _kb_s(self.doc_giay)

    @property
    def ghi_kb_s(self) -> float | None:
        return _kb_s(self.ghi_giay)

    @property
    def cham(self) -> bool:
        if self.loi:
            return True
        return any(_qua(g) for g in (self.doc_giay, self.ghi_giay))

    def ra_dict(self) -> dict[str, Any]:
        return {
            "luc": self.luc,
            "doc_kb_s": self.doc_kb_s,
            "ghi_kb_s": self.ghi_kb_s,
            "loi": self.loi or None,
            "cham": self.cham,
        }


def _qua(giay: float | None) -> bool:
    return giay is not None and giay > NGUONG_CHAM_GIAY


def _kb_s(giay: float | None) -> float | None:
    if giay is None:
        return None
    return round(CO_TEP_DO / 1024 / max(giay, 1e-6), 1)


def _bay_gio() -> str:
    return datetime.now(UTC).isoformat()


def do_dong_bo(goc: Path) -> tuple[float, float]:
    """CHẠM ĐĨA (đồng bộ — chỉ gọi ở luồng phụ). Ghi 256KB + fsync, bỏ trang
    đệm của tệp, đọc lại và so. Trả (giây ghi, giây đọc)."""
    dau = os.environ.get("MEDIA_MARKER", "").strip()
    if dau and not (goc / dau).is_file():
        # Ổ rớt → thư mục bind trỏ xuống ổ VPS bên dưới: đo ở đó thì "nhanh" giả.
        raise FileNotFoundError("kho chưa gắn (thiếu tệp đánh dấu)")
    thu_muc = goc / THU_MUC_DO
    thu_muc.mkdir(exist_ok=True)
    tep = thu_muc / TEN_TEP_DO
    du_lieu = os.urandom(CO_TEP_DO)

    t0 = time.monotonic()
    with open(tep, "wb") as f:
        f.write(du_lieu)
        f.flush()
        os.fsync(f.fileno())
    ghi = time.monotonic() - t0

    # Vừa ghi xong thì trang còn trong bộ đệm máy khách — đọc lại sẽ "nhanh" giả.
    # Bỏ đệm (Linux) để lần đọc thật sự đi qua mạng tới ổ.
    fd = os.open(tep, os.O_RDONLY)
    try:
        if sys.platform == "linux":
            os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
        t1 = time.monotonic()
        doc_ra = bytearray()
        while True:
            khuc = os.read(fd, 64 * 1024)
            if not khuc:
                break
            doc_ra += khuc
        doc = time.monotonic() - t1
    finally:
        os.close(fd)
    if bytes(doc_ra) != du_lieu:
        raise OSError("đọc lại không khớp dữ liệu vừa ghi")
    return ghi, doc


#: Luồng đo đang bay (nếu còn sống sau hạn = ổ đang treo).
_luong: threading.Thread | None = None


async def do_kho(goc: Path, *, han: float = HAN_GIAY) -> PhepDo:
    """Một lần đo, KHÔNG chặn vòng sự kiện, KHÔNG ném."""
    global _luong
    luc = _bay_gio()
    if _luong is not None and _luong.is_alive():
        return PhepDo(luc=luc, loi="lần đo trước vẫn đang treo trên ổ")

    kq: concurrent.futures.Future[tuple[float, float]] = concurrent.futures.Future()

    def _chay() -> None:
        # Đánh dấu ĐANG CHẠY: hết hạn thì bên chờ huỷ không được future này,
        # nên lúc ổ hồi và luồng trả về, set_result không nổ InvalidStateError.
        if not kq.set_running_or_notify_cancel():
            return
        try:
            kq.set_result(do_dong_bo(goc))
        except BaseException as e:  # noqa: BLE001 — chuyển lỗi về vòng sự kiện
            kq.set_exception(e)

    _luong = threading.Thread(target=_chay, name="canh-gac-kho-tep", daemon=True)
    _luong.start()
    try:
        ghi, doc = await asyncio.wait_for(asyncio.wrap_future(kq), timeout=han)
    except TimeoutError:
        return PhepDo(luc=luc, loi=f"quá hạn {han:g}s")
    except Exception as e:  # noqa: BLE001
        return PhepDo(luc=luc, loi=f"{type(e).__name__}: {e}"[:200])
    return PhepDo(luc=luc, doc_giay=doc, ghi_giay=ghi)


class TheoDoi:
    """Chống nháy: đếm chậm/ổn liên tiếp. ``cap_nhat`` trả True = mở,
    False = đóng, None = giữ nguyên trạng thái cảnh báo hiện có."""

    def __init__(self) -> None:
        self.cham_lien = 0
        self.on_lien = 0

    def cap_nhat(self, cham: bool) -> bool | None:
        if cham:
            self.cham_lien += 1
            self.on_lien = 0
            return True if self.cham_lien >= SO_LAN_LIEN_TIEP else None
        self.on_lien += 1
        self.cham_lien = 0
        return False if self.on_lien >= SO_LAN_LIEN_TIEP else None


def noi_dung(pd: PhepDo) -> str:
    if pd.loi:
        return (
            f"Kho tệp Viettel CFS không đo được: {pd.loi} — ảnh/tệp kết quả có "
            "thể không mở được."
        )
    if _qua(pd.ghi_giay) and not _qua(pd.doc_giay):
        viec, kb = "ghi", pd.ghi_kb_s
    else:
        viec, kb = "đọc", pd.doc_kb_s
    return f"Kho tệp Viettel CFS chậm: {viec} {kb:g} KB/s (bình thường > 1 MB/s)."


def ket_qua_kiem(pd: PhepDo, quyet: bool | None) -> KetQuaKiem:
    return KetQuaKiem(MA, "critical" if pd.loi else "warning", quyet, noi_dung(pd))


#: Số đo mới nhất cho /ops (API chạy một tiến trình — xem Dockerfile.api).
MOI_NHAT: dict[str, Any] | None = None
_theo_doi = TheoDoi()


async def mot_vong(
    pool: asyncpg.Pool, goc: Path, *, han: float = HAN_GIAY
) -> PhepDo | None:
    """Đo + mở/đóng cảnh báo. Không bao giờ ném."""
    global MOI_NHAT
    try:
        pd = await do_kho(goc, han=han)
        MOI_NHAT = pd.ra_dict()
        quyet = _theo_doi.cap_nhat(pd.cham)
        if pd.cham:
            logger.warning("kho_tep_cham", **MOI_NHAT)
        await ap_dung(pool, [ket_qua_kiem(pd, quyet)])
        return pd
    except Exception:  # noqa: BLE001
        logger.exception("canh_gac_kho_tep_hong")
        return None


def bat() -> bool:
    """Chỉ chạy khi MEDIA_ROOT được khai tường minh (container api đặt sẵn) —
    test và máy dev không có biến này thì không ghi rác vào ./.media."""
    return bool(os.environ.get("MEDIA_ROOT")) and os.environ.get(
        "CANH_GAC_KHO_TEP", "1"
    ).strip() not in ("0", "false", "")


async def chay_nen(pool: asyncpg.Pool) -> None:
    """Vòng nền trong API: mỗi phút một lần đo. Huỷ khi tắt app."""
    from clinicai.services.media_service import MEDIA_ROOT

    logger.info("canh_gac_kho_tep_bat_dau", goc=str(MEDIA_ROOT))
    while True:
        await mot_vong(pool, MEDIA_ROOT)
        await asyncio.sleep(NHIP_GIAY)
