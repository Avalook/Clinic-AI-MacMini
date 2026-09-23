"""Hẹn giờ — "sau bao lâu thì làm gì".

Rất nhiều luật của phòng khám có chữ "quá … phút": khách chờ quá 20 phút thì báo
trưởng ca; việc đối soát tiền để quá một ngày thì nhắc lại; khách hẹn tái khám mà
chưa tới thì gọi. Trước file này, hệ thống không có chỗ nào để hẹn một việc trong
tương lai — nên mọi luật loại ấy đều phải có người nhớ hộ, và người thì quên.

HAI LUẬT, và cả hai đều đã có hệ khác trả giá để học:

1. **Hẹn ghi CÙNG giao dịch với việc sinh ra nó.** Mở việc ở một giao dịch, hẹn
   nhắc ở giao dịch khác, thì có ngày việc mở mà lời nhắc không bao giờ tới —
   đúng loại hỏng không ai phát hiện cho tới lúc cần.

2. **Tới giờ phải KIỂM LẠI hiện trạng.** Lời nhắc đặt lúc 10:00 cho 10:20 không
   biết chuyện lúc 10:05 người ta đã xử lý xong. Bắn một lời nhắc sai là cách
   nhanh nhất để người trực học cách bỏ qua mọi lời nhắc — sau đó thì lời nhắc
   đúng cũng vô dụng.

Vì luật 2, mỗi loại hẹn phải tự trả lời "giờ còn cần làm nữa không?" chứ không
chỉ "làm gì". Hàm xử lý trả về `True` là đã làm, `False` là **hết cần** — cả hai
đều là kết thúc bình thường, không phải lỗi.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import asyncpg
import structlog

logger = structlog.get_logger()

SO_LAN_THU_TOI_DA = 5
HAN_THUE_GIAY = 120


@dataclass(frozen=True)
class HenDenHan:
    id: str
    clinic_id: str
    loai: str
    ve_cai_gi: str | None
    correlation_id: str | None
    chi_tiet: dict[str, Any]
    so_lan_thu: int


#: Trả về True = đã làm; False = hiện trạng đã đổi, không cần làm nữa.
XuLyHen = Callable[[asyncpg.Connection, HenDenHan], Awaitable[bool]]

_BO_XU_LY: dict[str, XuLyHen] = {}


def dang_ky_loai(loai: str, xu_ly: XuLyHen) -> None:
    _BO_XU_LY[loai] = xu_ly


async def hen(
    conn: asyncpg.Connection,
    *,
    clinic_id: str,
    loai: str,
    sau: timedelta,
    ve_cai_gi: str | None = None,
    correlation_id: str | None = None,
    chi_tiet: dict[str, Any] | None = None,
) -> str | None:
    """Đặt một cái hẹn. Gọi TRONG giao dịch của việc sinh ra nó.

    Trả về mã hẹn, hoặc None khi đã có một cái hẹn cùng loại cho cùng đối tượng
    đang chờ — hẹn hai lần cho một chuyện là hai lời nhắc cho một chuyện.
    """
    ma = await conn.fetchval(
        """
        INSERT INTO hen_gio
            (clinic_id, loai, ve_cai_gi, correlation_id, chi_tiet, den_gio)
        VALUES ($1::uuid, $2, $3::uuid, $4::uuid, $5::jsonb, now() + $6::interval)
        ON CONFLICT DO NOTHING
        RETURNING id::text
        """,
        clinic_id,
        loai,
        ve_cai_gi,
        correlation_id,
        json.dumps(chi_tiet or {}, ensure_ascii=False),
        sau,
    )
    return str(ma) if ma else None


async def huy_hen(
    conn: asyncpg.Connection, *, clinic_id: str, loai: str, ve_cai_gi: str
) -> None:
    """Chuyện đã xong sớm thì gỡ hẹn — đỡ một lần kiểm lại vô ích."""
    await conn.execute(
        "UPDATE hen_gio SET trang_thai = 'BO_QUA', lam_luc = now(),"
        "       ket_qua = 'huy_vi_xong_som'"
        " WHERE clinic_id = $1::uuid AND loai = $2 AND ve_cai_gi = $3::uuid"
        "   AND trang_thai = 'CHO'",
        clinic_id,
        loai,
        ve_cai_gi,
    )


_NHAN_MOT_HEN = """
WITH ung_vien AS (
    SELECT id FROM hen_gio
     WHERE trang_thai = 'CHO' AND den_gio <= now()
     ORDER BY den_gio
     FOR UPDATE SKIP LOCKED
     LIMIT 1
)
UPDATE hen_gio h
   SET trang_thai = 'DANG_LAM', so_lan_thu = h.so_lan_thu + 1,
       thue_den = now() + make_interval(secs => $1)
  FROM ung_vien
 WHERE h.id = ung_vien.id
RETURNING h.id::text, h.clinic_id::text, h.loai, h.ve_cai_gi::text,
          h.correlation_id::text, h.chi_tiet, h.so_lan_thu
"""


async def lam_mot_hen(pool: asyncpg.Pool) -> bool:
    """Xử lý đúng một cái hẹn đã tới giờ. False = chưa cái nào tới hạn."""
    async with pool.acquire() as conn, conn.transaction():
        dong = await conn.fetchrow(_NHAN_MOT_HEN, float(HAN_THUE_GIAY))
        if dong is None:
            return False
        cai_hen = HenDenHan(
            id=dong["id"],
            clinic_id=dong["clinic_id"],
            loai=dong["loai"],
            ve_cai_gi=dong["ve_cai_gi"],
            correlation_id=dong["correlation_id"],
            chi_tiet=json.loads(dong["chi_tiet"]),
            so_lan_thu=dong["so_lan_thu"],
        )

    xu_ly = _BO_XU_LY.get(cai_hen.loai)
    if xu_ly is None:
        # Loại hẹn không ai nhận: dừng có tiếng, đừng nuốt.
        await pool.execute(
            "UPDATE hen_gio SET trang_thai = 'CHET', lam_luc = now(),"
            "       loi_gan_nhat = 'khong co ai xu ly loai hen nay'"
            " WHERE id = $1::uuid",
            cai_hen.id,
        )
        logger.error("hen_gio_khong_co_nguoi_xu_ly", loai=cai_hen.loai)
        return True

    try:
        async with pool.acquire() as conn, conn.transaction():
            da_lam = await xu_ly(conn, cai_hen)
            await conn.execute(
                "UPDATE hen_gio SET trang_thai = $2, lam_luc = now(),"
                "       thue_den = NULL, ket_qua = $3"
                " WHERE id = $1::uuid",
                cai_hen.id,
                "XONG" if da_lam else "BO_QUA",
                "da_lam" if da_lam else "het_can",
            )
    except Exception as loi:  # noqa: BLE001 — mọi lỗi thành thử lại hoặc chết
        het_luot = cai_hen.so_lan_thu >= SO_LAN_THU_TOI_DA
        await pool.execute(
            "UPDATE hen_gio"
            "   SET trang_thai = $2,"
            "       den_gio = CASE WHEN $2 = 'CHO'"
            "                      THEN now() + make_interval(secs => $3)"
            "                      ELSE den_gio END,"
            "       lam_luc = CASE WHEN $2 = 'CHET' THEN now() END,"
            "       thue_den = NULL, loi_gan_nhat = $4"
            " WHERE id = $1::uuid",
            cai_hen.id,
            "CHET" if het_luot else "CHO",
            60.0 * cai_hen.so_lan_thu,
            str(loi)[:2000],
        )
        logger.warning(
            "hen_gio_hong", loai=cai_hen.loai, chet=het_luot, loi=str(loi)[:200]
        )
    return True


async def thu_hoi_hen_treo(pool: asyncpg.Pool) -> int:
    """Worker chết giữa chừng thì trả cái hẹn về hàng."""
    return int(
        await pool.fetchval(
            "WITH qua_han AS ("
            "  UPDATE hen_gio SET trang_thai = 'CHO', thue_den = NULL,"
            "         loi_gan_nhat = 'worker bo do, thu hoi'"
            "   WHERE trang_thai = 'DANG_LAM' AND thue_den < now()"
            "  RETURNING 1) SELECT count(*) FROM qua_han"
        )
        or 0
    )


async def chay_vong_hen(pool: asyncpg.Pool, *, nghi_giay: float = 5.0) -> None:
    while True:
        try:
            await thu_hoi_hen_treo(pool)
            con = True
            while con:
                con = await lam_mot_hen(pool)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — vòng chạy không được phép chết
            logger.exception("vong_hen_gio_hong")
        await asyncio.sleep(nghi_giay)


__all__ = [
    "HAN_THUE_GIAY",
    "SO_LAN_THU_TOI_DA",
    "HenDenHan",
    "XuLyHen",
    "chay_vong_hen",
    "dang_ky_loai",
    "hen",
    "huy_hen",
    "lam_mot_hen",
    "thu_hoi_hen_treo",
]
