"""BỘ CANH GÁC (27/09/2026 — theo dõi lỗi Pha 1).

Chạy trong vòng `su-kien` (vốn bắt buộc chạy) MỖI PHÚT, không cần Kuma, không
cần thêm service. Mỗi phép kiểm trả "có chuyện" hay "ổn":
  · có chuyện  → MỞ cảnh báo (`canh_bao`, mỗi mã một cảnh báo đang mở; lặp lại
                 thì cộng `so_lan`, không đẻ dòng mới) + gửi Telegram kênh ops
                 LẦN ĐẦU nếu đã cấu hình (`TELEGRAM_BOT_TOKEN` +
                 `TELEGRAM_OPS_CHAT_ID`).
  · ổn         → ĐÓNG cảnh báo đang mở của mã ấy (+ báo "đã hết").
Màn /ops tab "Lỗi & cảnh báo" đọc bảng này — nên kể cả chưa có Telegram, người
trực mở màn là thấy.

Phân công: Kuma canh TỪ NGOÀI (API chết thì canh gác chết theo); canh gác canh
TỪ TRONG (API sống mà nghiệp vụ kẹt). Hai lớp, không thay nhau.

Không bao giờ ném: một phép kiểm hỏng không được làm chết vòng giao tin.
Nội dung cảnh báo chỉ SỐ ĐẾM — không tên khách (Telegram là dịch vụ ngoài).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import asyncpg
import httpx
import structlog

from clinicai.services.luot_treo import dieu_kien_luot_treo

logger = structlog.get_logger()

NHIP_GIAY = 60
#: Nhiều KIỂU lỗi khác nhau cùng lúc = hỏng diện rộng (DB, mạng), không phải
#: một nút lỗi lẻ.
NGUONG_KIEU_LOI_5P = 3


@dataclass(frozen=True)
class KetQuaKiem:
    ma: str
    muc: str  # warning | critical
    #: True = mở/cộng dồn · False = đóng · None = giữ nguyên (phép đo có chống
    #: nháy, vd. kho tệp: chưa đủ số lần liên tiếp để đổi trạng thái).
    co_chuyen: bool | None
    noi_dung: str


def danh_gia(so: dict[str, Any]) -> list[KetQuaKiem]:
    """HÀM THUẦN: từ số đếm → các kết quả kiểm (test được không cần DB)."""
    from clinicai.api.v1.health import danh_gia_su_kien

    ly_do = danh_gia_su_kien(so["su_kien"])
    ra = [
        KetQuaKiem(
            "SU_KIEN",
            "critical",
            bool(ly_do),
            "Người đưa tin sự kiện kẹt: " + "; ".join(ly_do)
            if ly_do
            else "Người đưa tin sự kiện chạy bình thường.",
        ),
        KetQuaKiem(
            "LOI_MOI",
            "warning",
            so["loi_moi_15p"] > 0,
            f"{so['loi_moi_15p']} kiểu lỗi MỚI trong 15 phút "
            f"({so['lan_loi_15p']} lần) — xem /ops tab Lỗi & cảnh báo.",
        ),
        KetQuaKiem(
            "LOI_DANG_DIEN",
            "critical",
            so["kieu_loi_5p"] >= NGUONG_KIEU_LOI_5P,
            f"{so['kieu_loi_5p']} kiểu lỗi cùng xảy ra trong 5 phút — "
            "hệ thống có thể đang hỏng diện rộng.",
        ),
        KetQuaKiem(
            "HANG_CHO_MA",
            "warning",
            so["hang_cho_ma"] > 0,
            f"{so['hang_cho_ma']} chỗ chờ của khách đã về (check-out) vẫn mở.",
        ),
        KetQuaKiem(
            "LUOT_TREO",
            "warning",
            so["luot_treo"] > 0,
            f"{so['luot_treo']} lượt khám từ hôm trước chưa đóng (check-out).",
        ),
    ]
    return ra


async def do_so(conn: asyncpg.Connection) -> dict[str, Any]:
    from clinicai.api.v1.health import do_su_kien

    su_kien = await do_su_kien(conn)
    r = await conn.fetchrow(
        f"""
        SELECT
          (SELECT count(*) FROM loi_nhom
            WHERE trang_thai = 'MOI' AND lan_dau > now() - interval '15 minutes')
            AS loi_moi_15p,
          (SELECT coalesce(sum(so_lan), 0) FROM loi_nhom
            WHERE lan_dau > now() - interval '15 minutes') AS lan_loi_15p,
          (SELECT count(*) FROM loi_nhom
            WHERE lan_cuoi > now() - interval '5 minutes'
              AND trang_thai <> 'BO_QUA') AS kieu_loi_5p,
          (SELECT count(*) FROM queue_entry q JOIN visit v ON v.visit_id = q.visit_id
            WHERE q.status IN ('blocked', 'waiting', 'called', 'serving')
              AND v.closed_at IS NOT NULL) AS hang_cho_ma,
          -- Lượt TREO = còn mở từ hôm trước — CÙNG câu với màn Check-out
          -- ("Lượt tồn đọng từ hôm trước"), xem services/luot_treo.py.
          (SELECT count(*) FROM visit v
            WHERE {dieu_kien_luot_treo("v")}) AS luot_treo
        """
    )
    assert r is not None
    return {
        "su_kien": su_kien,
        "loi_moi_15p": int(r["loi_moi_15p"]),
        "lan_loi_15p": int(r["lan_loi_15p"]),
        "kieu_loi_5p": int(r["kieu_loi_5p"]),
        "hang_cho_ma": int(r["hang_cho_ma"]),
        "luot_treo": int(r["luot_treo"]),
    }


async def _mo(conn: asyncpg.Connection, k: KetQuaKiem) -> bool:
    """Mở / cộng dồn. Trả True nếu cảnh báo MỚI mở (để báo một lần)."""
    moi = await conn.fetchval(
        """
        INSERT INTO canh_bao (ma, muc, noi_dung) VALUES ($1, $2, $3)
        ON CONFLICT (ma) WHERE dong_luc IS NULL DO UPDATE
           SET so_lan = canh_bao.so_lan + 1, lan_cuoi = now(),
               noi_dung = EXCLUDED.noi_dung
        RETURNING (xmax = 0)
        """,
        k.ma,
        k.muc,
        k.noi_dung,
    )
    return bool(moi)


async def _dong(conn: asyncpg.Connection, ma: str) -> bool:
    kq = await conn.execute(
        "UPDATE canh_bao SET dong_luc = now() WHERE ma = $1 AND dong_luc IS NULL", ma
    )
    return str(kq).endswith(" 1")


async def gui_telegram_ops(chu: str) -> bool:
    """Kênh Telegram RIÊNG cho cảnh báo kỹ thuật (Tuyền chốt 27/09). Chưa cấu
    hình thì thôi — cảnh báo vẫn nằm ở /ops."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_OPS_CHAT_ID", "").strip()
    if not token or not chat:
        return False
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat, "text": chu, "disable_web_page_preview": True},
            )
        return r.status_code == 200
    except httpx.HTTPError:
        return False


async def ap_dung(pool: asyncpg.Pool, ket_qua: list[KetQuaKiem]) -> None:
    """Mở / đóng cảnh báo theo kết quả kiểm + báo Telegram ops lúc đổi trạng
    thái. Dùng chung cho vòng su-kien và phép đo kho tệp trong API. CÓ THỂ ném
    (lỗi DB) — người gọi bọc."""
    async with pool.acquire() as conn:
        thay_doi: list[tuple[KetQuaKiem, bool]] = []
        for k in ket_qua:
            if k.co_chuyen is None:
                continue
            if k.co_chuyen:
                if await _mo(conn, k):
                    thay_doi.append((k, True))
            elif await _dong(conn, k.ma):
                thay_doi.append((k, False))
    for k, mo in thay_doi:
        dau = ("🔴" if k.muc == "critical" else "🟠") if mo else "✅ Đã hết:"
        chu = f"{dau} ClinicAI · {k.noi_dung}"
        logger.warning("canh_gac_mo" if mo else "canh_gac_dong", ma=k.ma, muc=k.muc)
        if await gui_telegram_ops(chu) and mo:
            await pool.execute(
                "UPDATE canh_bao SET bao_luc = now()"
                " WHERE ma = $1 AND dong_luc IS NULL",
                k.ma,
            )


async def mot_vong(pool: asyncpg.Pool) -> list[KetQuaKiem]:
    """Một lượt canh gác. Không bao giờ ném."""
    try:
        async with pool.acquire() as conn:
            ket_qua = danh_gia(await do_so(conn))
        await ap_dung(pool, ket_qua)
        return ket_qua
    except Exception:  # noqa: BLE001 — canh gác hỏng không được làm chết vòng
        logger.exception("canh_gac_hong")
        return []


async def danh_sach(pool: asyncpg.Pool, *, gioi_han: int = 50) -> list[dict[str, Any]]:
    rows = await pool.fetch(
        """
        SELECT id::text, ma, muc, noi_dung, so_lan, mo_luc, lan_cuoi, dong_luc, bao_luc
          FROM canh_bao
         ORDER BY (dong_luc IS NULL) DESC, lan_cuoi DESC
         LIMIT $1
        """,
        gioi_han,
    )
    return [
        {
            k: (v.isoformat() if hasattr(v, "isoformat") else v)
            for k, v in dict(r).items()
        }
        for r in rows
    ]
