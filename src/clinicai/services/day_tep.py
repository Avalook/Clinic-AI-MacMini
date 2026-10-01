"""ĐẨY TỆP KẾT QUẢ TỪ Ổ VPS SANG VIETTEL CFS (Tuyền chốt 30/09/2026).

Chạy trong container RIÊNG ``day-tep`` (``python -m clinicai.worker --day-tep``),
gắn CẢ HAI ổ: ổ VPS (``MEDIA_LOCAL_ROOT``) và kho CFS (``MEDIA_ROOT``).

VÌ SAO. Ổ mạng Viettel CFS chập chờn (29/09 đọc còn 69KB/s, 105 lần kết nối lại
từ 16/09). Tải lên thẳng vào đó là lượt tải hỏng mỗi lần ổ chậm. Từ 01/10 tải
lên ghi vào ổ VPS (dòng ``vi_tri='vps'``) — container này đẩy sang CFS SAU, lúc
ổ ổn, và không ai phải đứng chờ.

MỖI VÒNG (~30s):
  (a) Đo CFS (ghi + fsync + đọc lại một tệp nhỏ, có hạn giờ — dùng lại phép đo
      của ``canh_gac_kho_tep`` với tệp đo RIÊNG). Chỉ đẩy khi 2 lần đo liên
      tiếp ổn.
  (b) Lấy một lô ``vi_tri='vps'`` (cũ trước, ``FOR UPDATE SKIP LOCKED``, bỏ
      tệp đang lùi dần). Mỗi tệp: chép sang ``CFS/.tam`` + fsync → ĐỌC LẠI từ
      CFS tính sha256, so với ``tep_ket_qua.sha256`` và ``so_byte`` → khớp mới
      đổi tên về ``khoa`` và ``UPDATE vi_tri='cfs', da_day_luc=now()``. Lỗi →
      ``so_lan_day_loi+1``, ``loi_day_cuoi``, lùi dần theo số lần lỗi.
  (c) Dọn bản VPS: tệp đã đẩy quá ``GIU_NGAY`` ngày → xoá bản VPS, ghi
      ``da_xoa_ban_vps_luc``; ổ VPS vượt ``TRAN_BYTES`` → xoá sớm bản đã đẩy cũ
      nhất tới dưới trần. KHÔNG BAO GIỜ xoá tệp chưa đẩy (``vi_tri='vps'`` là
      bản DUY NHẤT của nó) — câu SQL chỉ chọn ``vi_tri='cfs'``.
  (d) Job dọn V9 (``don_tep_ket_qua``: tệp xoá mềm > 30 ngày + ``.tam`` sót của
      HAI ổ) — mỗi ngày một lần, chuyển từ su-kien sang đây vì đây mới có ổ.
  (e) Cảnh báo ổ VPS gần đầy (> 80% trần hoặc đĩa máy còn < 5GB) qua
      ``canh_gac.ap_dung`` → bảng ``canh_bao`` → /ops + Telegram ops.

KHÔNG KHOÁ DÒNG TRONG LÚC CHÉP. ``FOR UPDATE SKIP LOCKED`` chỉ giữ trong giao
dịch chọn lô (ngắn); chép một video vài trăm MB mất cả phút, giữ khoá dòng suốt
lúc ấy thì bác sĩ bấm "cho phép gửi" trên đúng tệp đó sẽ đứng chờ. Một tiến
trình duy nhất được bảo đảm bằng khoá tư vấn cấp phiên (``pg_try_advisory_lock``);
câu đánh dấu cuối có điều kiện ``vi_tri='vps' AND sha256=…``.

AN TOÀN: mọi thao tác ổ qua ``chay_tren_kho`` (luồng phụ, hạn giờ, ngắt mạch
riêng từng ổ). Ổ treo → bỏ lượt, KHÔNG làm chết tiến trình; ``mot_vong`` không
bao giờ ném.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Any

import asyncpg
import structlog

from clinicai.core.exceptions import ExternalServiceError
from clinicai.core.kho_tep import HAN_GIAY, KHO_VPS, chay_tren_kho
from clinicai.services import canh_gac_kho_tep, media_service
from clinicai.services.canh_gac import (
    CHO_DAY_LAU_GIO,
    NGUONG_LOI_DAY,
    KetQuaKiem,
    ap_dung,
)
from clinicai.services.media_service import giai_trong

logger = structlog.get_logger()

GB = 1024 * 1024 * 1024
MB = 1024 * 1024


def _so_env(ten: str, mac_dinh: int) -> int:
    """Số nguyên dương từ env; rỗng / rác / âm → mặc định (không ném)."""
    try:
        v = int(str(os.environ.get(ten, "")).strip())
    except ValueError:
        return mac_dinh
    return v if v > 0 else mac_dinh


#: Nhịp vòng lặp.
NHIP_GIAY = _so_env("DAY_TEP_NHIP_GIAY", 30)
#: Giữ bản VPS bao nhiêu ngày sau khi đã đẩy (đọc nhanh tệp mới).
GIU_NGAY = _so_env("DAY_TEP_GIU_NGAY", 7)
#: Trần dung lượng thư mục ổ VPS: vượt thì xoá sớm bản ĐÃ đẩy cũ nhất.
TRAN_BYTES = _so_env("DAY_TEP_TRAN_BYTES", 8 * GB)
#: Mỗi lượt đẩy tối đa bấy nhiêu tệp.
MOI_LO = 20
#: Số lần đo CFS ổn liên tiếp trước khi đẩy.
SO_LAN_ON = 2
#: Lùi dần sau lỗi: 60s, 120s, 240s… tối đa 1 giờ.
LUI_CO_BAN_GIAY = 60
LUI_TOI_DA_GIAY = 3600
#: Một tệp đẩy hỏng từ chừng này lần → cảnh báo (canh gác trong su-kien mở).
NGUONG_LOI_CANH_BAO = NGUONG_LOI_DAY
#: Ổ VPS dùng quá tỉ lệ này của trần → cảnh báo.
CANH_PHAN_TRAN = 0.8
#: Đĩa máy (ổ chứa MEDIA_LOCAL_ROOT) còn dưới chừng này → cảnh báo.
HOST_CANH_BYTES = 5 * GB
#: Tệp đo riêng của container này (API đo cùng ổ bằng tệp khác).
TEN_TEP_DO = "do-toc-do-day-tep.bin"
#: Mỗi lần đọc / ghi khi chép.
KHUC = 4 * MB
#: Hạn cho một lần quét dung lượng ổ VPS.
HAN_QUET_GIAY = 60.0
#: Khoá tư vấn: chỉ MỘT tiến trình đẩy tệp.
KHOA_MOT_TIEN_TRINH = "clinicai:day-tep"
MA_O_VPS = "O_VPS_DAY"
#: Bảng có tệp ổ VPS → CFS, CÙNG bộ cột đẩy (khoa, so_byte, sha256, vi_tri,
#: da_day_luc, so_lan_day_loi, loi_day_cuoi, day_loi_luc, da_xoa_ban_vps_luc,
#: da_don_tep_luc, tai_len_luc). Ảnh chuyển khoản (mig 20261002300000) đi cùng
#: đường với tệp kết quả — không làm đường đẩy thứ hai. Tên bảng chỉ lấy từ
#: danh sách này (chèn vào SQL).
BANG_TEP: tuple[str, ...] = ("tep_ket_qua", "anh_chuyen_khoan")


def _bang(bang: str) -> str:
    if bang not in BANG_TEP:
        raise ValueError(f"bảng tệp lạ: {bang!r}")
    return bang


def lui_giay(so_lan_loi: int) -> int:
    """Chờ bao lâu sau lần hỏng thứ ``so_lan_loi`` (HÀM THUẦN — cùng công thức
    với ``_SQL_LO``)."""
    n = max(so_lan_loi, 1)
    return int(min(LUI_TOI_DA_GIAY, LUI_CO_BAN_GIAY * 2 ** (n - 1)))


def han_day(so_byte: int) -> float:
    """Hạn cho MỘT lần đẩy: chép + đọc lại ⇒ 2 lượt qua ổ, ≥ 1MB/s mỗi lượt."""
    return HAN_GIAY + 2 * so_byte / MB


class DayTepError(Exception):
    """Đẩy MỘT tệp hỏng vì lý do của chính tệp (lệch sha, mất bản VPS…)."""


# ── (b) chép + kiểm ──────────────────────────────────────────────────────────


def _sha_doc_lai(duong: Path) -> tuple[int, str]:
    """Đọc lại tệp vừa ghi trên CFS — BỎ trang đệm trước (Linux) để lần đọc đi
    qua mạng tới ổ thật, không đọc lại bộ đệm máy khách. (số byte, sha256)."""
    h = hashlib.sha256()
    n = 0
    fd = os.open(duong, os.O_RDONLY)
    try:
        if sys.platform == "linux":
            os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
        while True:
            khuc = os.read(fd, KHUC)
            if not khuc:
                break
            h.update(khuc)
            n += len(khuc)
    finally:
        os.close(fd)
    return n, h.hexdigest()


def chep_va_kiem(
    nguon: Path, goc_cfs: Path, khoa: str, so_byte: int, sha256: str
) -> Path:
    """ĐỒNG BỘ (chạy qua ``chay_tren_kho``). Chép ``nguon`` (ổ VPS) sang
    ``goc_cfs/.tam`` + fsync, đọc lại kiểm sha256 + số byte, khớp mới đổi tên về
    ``goc_cfs/khoa``. Trả đường đích. Lệch / thiếu → ``DayTepError``; tệp tạm luôn
    bị xoá khi hỏng."""
    dau = os.environ.get("MEDIA_MARKER", "").strip()
    if dau and not (goc_cfs / dau).is_file():
        # Ổ rớt → thư mục bind trỏ xuống ổ VPS bên dưới: "đẩy" vào đó là tự lừa.
        raise DayTepError("kho CFS chưa gắn (thiếu tệp đánh dấu)")
    dich = giai_trong(goc_cfs, khoa)
    if dich is None:
        raise DayTepError("khoá tệp không hợp lệ")
    if not nguon.is_file():
        raise DayTepError("không thấy bản trên ổ VPS")
    tam = goc_cfs / ".tam"
    tam.mkdir(parents=True, exist_ok=True)
    tmp = tam / f"{uuid.uuid4().hex}.day"
    try:
        h = hashlib.sha256()
        n = 0
        with nguon.open("rb") as vao, tmp.open("xb") as ra:
            while True:
                khuc = vao.read(KHUC)
                if not khuc:
                    break
                ra.write(khuc)
                h.update(khuc)
                n += len(khuc)
            ra.flush()
            os.fsync(ra.fileno())
        if n != so_byte or h.hexdigest() != sha256:
            raise DayTepError("bản trên ổ VPS lệch số byte / sha256 so với database")
        n2, sha2 = _sha_doc_lai(tmp)
        if n2 != so_byte or sha2 != sha256:
            raise DayTepError("đọc lại trên CFS lệch số byte / sha256 — chưa đánh dấu")
        dich.parent.mkdir(parents=True, exist_ok=True)
        os.replace(tmp, dich)
        os.chmod(dich, 0o600)
        return dich
    except BaseException:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise


#: Lô chờ đẩy: cũ trước, bỏ tệp đã dọn (V9), bỏ tệp đang LÙI DẦN sau lỗi (cùng
#: công thức ``lui_giay``). Khoá dòng CHỈ trong giao dịch chọn lô.
_SQL_LO = """
SELECT t.id::text AS id, t.clinic_id::text AS clinic_id, t.khoa,
       t.so_byte, t.sha256, t.so_lan_day_loi
  FROM {bang} t
 WHERE t.vi_tri = 'vps'
   AND t.da_don_tep_luc IS NULL
   AND (t.day_loi_luc IS NULL
        OR t.day_loi_luc + make_interval(
               secs => least($3::float8,
                             $2::float8 * power(2, greatest(t.so_lan_day_loi, 1) - 1)))
           <= now())
 ORDER BY t.tai_len_luc, t.id
 LIMIT $1
 FOR UPDATE OF t SKIP LOCKED
"""


async def _ghi_loi(
    pool: asyncpg.Pool, r: Any, loi: str, bang: str = "tep_ket_qua"
) -> None:
    await pool.execute(
        f"UPDATE {_bang(bang)}"  # noqa: S608 — tên bảng từ BANG_TEP
        "   SET so_lan_day_loi = so_lan_day_loi + 1,"
        "       loi_day_cuoi = left($3, 500), day_loi_luc = now()"
        " WHERE id = $1::uuid AND clinic_id = $2::uuid AND vi_tri = 'vps'",
        r["id"],
        r["clinic_id"],
        loi,
    )
    logger.warning(
        "day_tep_loi", tep_id=r["id"], lan=int(r["so_lan_day_loi"]) + 1, loi=loi
    )


async def day_mot_lo(
    pool: asyncpg.Pool,
    *,
    goc_vps: Path | None = None,
    goc_cfs: Path | None = None,
    gioi_han: int = MOI_LO,
    bang: str = "tep_ket_qua",
) -> dict[str, Any]:
    """Đẩy một lô của ``bang``. Ném ``ExternalServiceError`` KHÔNG — CFS chậm
    thì dừng lô (``bo_qua='kho_cham'``). Lỗi DB thì ném (``mot_vong`` bọc)."""
    goc_vps = goc_vps or media_service.goc_vps()
    goc_cfs = goc_cfs or media_service.goc_cfs()
    ket: dict[str, Any] = {"da_day": 0, "loi": 0, "bo_qua": None}
    async with pool.acquire() as conn, conn.transaction():
        lo = await conn.fetch(
            _SQL_LO.format(bang=_bang(bang)),
            gioi_han,
            LUI_CO_BAN_GIAY,
            LUI_TOI_DA_GIAY,
        )
    if not lo:
        return ket

    from clinicai.services.tep_ket_qua_service import MEDIA_MIN_FREE_BYTES

    def _con_trong() -> int:
        return shutil.disk_usage(goc_cfs).free

    try:
        trong = await chay_tren_kho(_con_trong)
    except (ExternalServiceError, OSError) as loi:
        ket["bo_qua"] = "kho_cham"
        logger.warning("day_tep_khong_do_duoc_cho_trong_cfs", loi=repr(loi))
        return ket

    for r in lo:
        khoa = str(r["khoa"])
        so_byte = int(r["so_byte"] or 0)
        if trong - so_byte < MEDIA_MIN_FREE_BYTES:
            ket["bo_qua"] = "cfs_day"
            logger.error("day_tep_cfs_sap_day", trong=trong, can=so_byte)
            break
        try:
            nguon = await chay_tren_kho(partial(giai_trong, goc_vps, khoa), kho=KHO_VPS)
            if nguon is None:
                raise DayTepError("khoá tệp không hợp lệ")
            await chay_tren_kho(
                partial(chep_va_kiem, nguon, goc_cfs, khoa, so_byte, str(r["sha256"])),
                han=han_day(so_byte),
            )
        except ExternalServiceError:
            # CFS (hoặc ổ VPS) quá hạn / đang ngắt mạch: tệp không có lỗi gì —
            # KHÔNG cộng lần lỗi, dừng lô, lượt sau đo lại rồi mới thử.
            ket["bo_qua"] = "kho_cham"
            logger.warning("day_tep_dung_vi_kho_cham", da_day=ket["da_day"])
            break
        except (DayTepError, OSError) as loi:
            ket["loi"] += 1
            await _ghi_loi(pool, r, f"{type(loi).__name__}: {loi}"[:500], bang)
            continue
        kq = await pool.execute(
            f"UPDATE {_bang(bang)} SET vi_tri = 'cfs', da_day_luc = now()"
            " WHERE id = $1::uuid AND clinic_id = $2::uuid"
            "   AND vi_tri = 'vps' AND sha256 = $3",
            r["id"],
            r["clinic_id"],
            str(r["sha256"]),
        )
        if str(kq).endswith(" 1"):
            ket["da_day"] += 1
            trong -= so_byte
            logger.info("day_tep_xong", tep_id=r["id"], so_byte=so_byte)
    return ket


# ── (c) dọn bản VPS ──────────────────────────────────────────────────────────


def dung_luong(goc: Path) -> int:
    """Tổng byte các tệp dưới ``goc`` (không theo symlink). Đồng bộ."""
    tong = 0
    if not goc.is_dir():
        return 0
    ngan = [goc]
    while ngan:
        d = ngan.pop()
        try:
            with os.scandir(d) as it:
                for e in it:
                    try:
                        if e.is_dir(follow_symlinks=False):
                            ngan.append(Path(e.path))
                        elif e.is_file(follow_symlinks=False):
                            tong += e.stat(follow_symlinks=False).st_size
                    except OSError:
                        continue
        except OSError:
            continue
    return tong


def _xoa_tep(goc: Path, clinic_id: str, khoa: str) -> int:
    """Xoá ``goc/khoa`` (đúng phòng khám, trong gốc). Trả số byte đã giải phóng
    (0 nếu không còn). Đồng bộ."""
    if not khoa.startswith(f"{clinic_id}/"):
        return 0
    p = giai_trong(goc, khoa)
    if p is None:
        return 0
    try:
        co = p.stat().st_size
    except FileNotFoundError:
        return 0
    p.unlink(missing_ok=True)
    return co


async def _xoa_ban_vps(
    pool: asyncpg.Pool, goc_vps: Path, r: Any, bang: str = "tep_ket_qua"
) -> int:
    """Xoá bản VPS của MỘT tệp ĐÃ đẩy + ghi mốc, trong giao dịch giữ khoá dòng
    (ổ VPS nhanh). Kiểm lại ``vi_tri='cfs'`` dưới khoá. Trả byte đã giải phóng."""
    async with pool.acquire() as conn, conn.transaction():
        con = await conn.fetchval(
            f"SELECT t.khoa FROM {_bang(bang)} t"  # noqa: S608
            " WHERE t.id = $1::uuid AND t.clinic_id = $2::uuid"
            "   AND t.vi_tri = 'cfs' AND t.da_day_luc IS NOT NULL"
            "   AND t.da_xoa_ban_vps_luc IS NULL"
            " FOR UPDATE",
            r["id"],
            r["clinic_id"],
        )
        if con is None:
            return 0
        clinic_id = str(r["clinic_id"])
        khoa = str(con)
        giai = await chay_tren_kho(
            partial(_xoa_tep, goc_vps, clinic_id, khoa), kho=KHO_VPS
        )
        await conn.execute(
            f"UPDATE {_bang(bang)} SET da_xoa_ban_vps_luc = now()"  # noqa: S608
            " WHERE id = $1::uuid AND clinic_id = $2::uuid AND vi_tri = 'cfs'",
            r["id"],
            clinic_id,
        )
    return int(giai)


_SQL_HET_HAN_GIU = """
SELECT t.id::text AS id, t.clinic_id::text AS clinic_id
  FROM {bang} t
 WHERE t.vi_tri = 'cfs' AND t.da_day_luc IS NOT NULL
   AND t.da_xoa_ban_vps_luc IS NULL
   AND t.da_day_luc < now() - make_interval(days => $1)
 ORDER BY t.da_day_luc
 LIMIT $2
"""

#: Vượt trần: bản đã đẩy CŨ NHẤT trước. KHÔNG BAO GIỜ chọn ``vi_tri='vps'``.
_SQL_DA_DAY_CU_NHAT = """
SELECT t.id::text AS id, t.clinic_id::text AS clinic_id
  FROM {bang} t
 WHERE t.vi_tri = 'cfs' AND t.da_day_luc IS NOT NULL
   AND t.da_xoa_ban_vps_luc IS NULL
 ORDER BY t.da_day_luc, t.id
 LIMIT $1
"""


async def don_ban_vps(
    pool: asyncpg.Pool,
    *,
    goc_vps: Path | None = None,
    giu_ngay: int | None = None,
    tran: int | None = None,
) -> dict[str, Any]:
    """Dọn bản VPS của tệp đã đẩy: quá hạn giữ, rồi tới dưới trần. Trả số đếm
    + dung lượng sau dọn. Ổ chậm → ném ``ExternalServiceError`` (nơi gọi bỏ
    lượt)."""
    goc_vps = goc_vps or media_service.goc_vps()
    giu = giu_ngay if giu_ngay is not None else GIU_NGAY
    tran_ = tran if tran is not None else TRAN_BYTES
    ket: dict[str, Any] = {"het_han": 0, "vuot_tran": 0, "dung": 0}
    for bang in BANG_TEP:
        for r in await pool.fetch(_SQL_HET_HAN_GIU.format(bang=bang), giu, 500):
            await _xoa_ban_vps(pool, goc_vps, r, bang)
            ket["het_han"] += 1
    dung = await chay_tren_kho(
        partial(dung_luong, goc_vps), han=HAN_QUET_GIAY, kho=KHO_VPS
    )
    for bang in BANG_TEP:
        if dung <= tran_:
            break
        for r in await pool.fetch(_SQL_DA_DAY_CU_NHAT.format(bang=bang), 500):
            if dung <= tran_:
                break
            giai = await _xoa_ban_vps(pool, goc_vps, r, bang)
            dung -= giai
            ket["vuot_tran"] += 1
        if dung > tran_:
            logger.warning("day_tep_vuot_tran_chi_con_tep_chua_day", dung=dung)
    ket["dung"] = dung
    return ket


# ── (e) cảnh báo ổ VPS ───────────────────────────────────────────────────────


def danh_gia_o_vps(dung: int, trong_may: int, tran: int | None = None) -> KetQuaKiem:
    """HÀM THUẦN: ổ VPS gần đầy? (dung lượng thư mục, byte trống của đĩa máy)."""
    tran_ = tran if tran is not None else TRAN_BYTES
    from clinicai.services.tep_ket_qua_service import MEDIA_LOCAL_MIN_FREE_BYTES

    nguy = trong_may < MEDIA_LOCAL_MIN_FREE_BYTES
    day = dung > CANH_PHAN_TRAN * tran_ or trong_may < HOST_CANH_BYTES
    gb = 1024**3
    noi = (
        f"Ổ lưu tạm trên VPS: thư mục tệp {dung / gb:.1f}/{tran_ / gb:.0f} GB, "
        f"đĩa máy còn {trong_may / gb:.1f} GB"
        + (" — ĐANG TỪ CHỐI tải lên." if nguy else ".")
        + (" Kiểm việc đẩy tệp sang Viettel CFS." if day else "")
    )
    return KetQuaKiem(MA_O_VPS, "critical" if nguy else "warning", day, noi)


# ── vòng lặp ─────────────────────────────────────────────────────────────────


@dataclass
class TrangThai:
    """Trạng thái giữa các vòng (một tiến trình)."""

    on_lien: int = 0
    lan_don_v9: float = field(default_factory=lambda: time.monotonic())
    lan_canh: float = 0.0
    dung: int = 0


async def mot_vong(
    pool: asyncpg.Pool,
    tt: TrangThai,
    *,
    goc_vps: Path | None = None,
    goc_cfs: Path | None = None,
) -> dict[str, Any]:
    """Một vòng (a)→(e). KHÔNG BAO GIỜ ném — trả số đếm để log / test."""
    from clinicai.services import don_tep_ket_qua

    goc_vps = goc_vps or media_service.goc_vps()
    goc_cfs = goc_cfs or media_service.goc_cfs()
    ket: dict[str, Any] = {"do": None, "day": None, "don": None, "v9": None}

    # (a) đo CFS — không bao giờ ném, không chặn vòng sự kiện
    try:
        pd = await canh_gac_kho_tep.do_kho(goc_cfs, ten_tep=TEN_TEP_DO)
        tt.on_lien = 0 if pd.cham else tt.on_lien + 1
        ket["do"] = pd.ra_dict()
    except Exception:  # noqa: BLE001
        tt.on_lien = 0
        logger.exception("day_tep_do_hong")

    # (b) đẩy — chỉ khi CFS ổn đủ số lần liên tiếp
    if tt.on_lien >= SO_LAN_ON:
        try:
            ket["day"] = await day_mot_lo(pool, goc_vps=goc_vps, goc_cfs=goc_cfs)
        except Exception:  # noqa: BLE001
            logger.exception("day_tep_day_hong")
        # Ảnh chuyển khoản (01/10/2026): cùng đường, lô riêng.
        try:
            ket["day_anh_ck"] = await day_mot_lo(
                pool, goc_vps=goc_vps, goc_cfs=goc_cfs, bang="anh_chuyen_khoan"
            )
        except Exception:  # noqa: BLE001
            logger.exception("day_tep_day_anh_ck_hong")
    else:
        ket["day"] = {"bo_qua": "cfs_chua_on", "on_lien": tt.on_lien}

    # (c) dọn bản VPS (chỉ ổ VPS + DB, không cần CFS)
    try:
        ket["don"] = await don_ban_vps(pool, goc_vps=goc_vps)
        tt.dung = int(ket["don"]["dung"])
    except Exception:  # noqa: BLE001
        logger.exception("day_tep_don_hong")

    # (d) job dọn V9 mỗi ngày (lượt đầu sau 10 phút — không tranh việc lúc deploy)
    if time.monotonic() - tt.lan_don_v9 >= don_tep_ket_qua.NHIP_GIAY:
        tt.lan_don_v9 = time.monotonic()
        ket["v9"] = await don_tep_ket_qua.mot_luot(pool, goc=goc_cfs, goc_vps=goc_vps)

    # (e) cảnh báo ổ VPS mỗi phút
    if time.monotonic() - tt.lan_canh >= 60:
        tt.lan_canh = time.monotonic()
        try:
            trong = await chay_tren_kho(
                lambda: shutil.disk_usage(goc_vps).free, kho=KHO_VPS
            )
            await ap_dung(pool, [danh_gia_o_vps(tt.dung, int(trong))])
        except Exception:  # noqa: BLE001
            logger.exception("day_tep_canh_bao_hong")
    return ket


async def so_lieu(conn: asyncpg.Connection) -> dict[str, Any]:
    """Số cho /ops: tệp chờ đẩy, đã đẩy hôm nay, đang lỗi. Chỉ SỐ ĐẾM."""
    r = await conn.fetchrow(
        """
        SELECT
          count(*) FILTER (WHERE vi_tri = 'vps' AND da_don_tep_luc IS NULL)
            AS cho_day,
          coalesce(sum(so_byte) FILTER (
              WHERE vi_tri = 'vps' AND da_don_tep_luc IS NULL), 0)::bigint
            AS cho_day_byte,
          min(tai_len_luc) FILTER (WHERE vi_tri = 'vps' AND da_don_tep_luc IS NULL)
            AS cu_nhat,
          count(*) FILTER (
              WHERE da_day_luc >= date_trunc(
                  'day', now() AT TIME ZONE 'Asia/Ho_Chi_Minh')
                  AT TIME ZONE 'Asia/Ho_Chi_Minh')
            AS da_day_hom_nay,
          count(*) FILTER (WHERE vi_tri = 'vps' AND da_don_tep_luc IS NULL
                             AND so_lan_day_loi > 0) AS dang_loi,
          count(*) FILTER (WHERE vi_tri = 'vps' AND da_don_tep_luc IS NULL
                             AND so_lan_day_loi >= $1) AS loi_nang
          FROM tep_ket_qua
        """,
        NGUONG_LOI_CANH_BAO,
    )
    assert r is not None
    cu = r["cu_nhat"]
    return {
        "cho_day": int(r["cho_day"]),
        "cho_day_byte": int(r["cho_day_byte"]),
        "cu_nhat_luc": cu.isoformat() if cu is not None else None,
        "da_day_hom_nay": int(r["da_day_hom_nay"]),
        "dang_loi": int(r["dang_loi"]),
        "loi_nang": int(r["loi_nang"]),
    }


def danh_gia_suc_khoe(so: dict[str, Any], bay_gio: datetime | None = None) -> list[str]:
    """HÀM THUẦN: lý do đường đẩy tệp đang hỏng (rỗng = ổn), từ ``so_lieu``."""
    ly_do: list[str] = []
    cu = so.get("cu_nhat_luc")
    if cu:
        try:
            moc = datetime.fromisoformat(str(cu))
        except ValueError:
            moc = None
        now = bay_gio or datetime.now(UTC)
        if moc is not None and now - moc > timedelta(hours=CHO_DAY_LAU_GIO):
            ly_do.append(
                f"{so.get('cho_day', 0)} tệp chờ đẩy, tệp cũ nhất quá "
                f"{CHO_DAY_LAU_GIO} giờ"
            )
    if int(so.get("loi_nang") or 0) > 0:
        ly_do.append(
            f"{so['loi_nang']} tệp đẩy hỏng từ {NGUONG_LOI_CANH_BAO} lần trở lên"
        )
    return ly_do


__all__ = [
    "GIU_NGAY",
    "DayTepError",
    "NHIP_GIAY",
    "TRAN_BYTES",
    "TrangThai",
    "chep_va_kiem",
    "danh_gia_o_vps",
    "danh_gia_suc_khoe",
    "day_mot_lo",
    "don_ban_vps",
    "dung_luong",
    "lui_giay",
    "mot_vong",
    "so_lieu",
]
