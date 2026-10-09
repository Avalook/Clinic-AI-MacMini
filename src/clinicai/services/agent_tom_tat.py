"""TÓM TẮT NGÀY CỦA AGENT GIÁM SÁT — chỗ DUY NHẤT agent dùng LLM (09/10/2026).

Hiến pháp §20: rule đủ thì dùng rule. Phát hiện là rule (`agent_giam_sat.py`);
LLM chỉ làm việc rule không làm được — đọc cả ngày nhận định rồi viết cho người
đọc: chuyện gì đáng để ý, đề xuất gì, luật nào cần xem lại, điều gì chưa biết.

GỬI ĐI GÌ (hợp đồng mục G, NĐ 13/2023): chỉ số đếm + nội dung nhận định — vốn
đã không tên / SĐT / mã khách (test `test_agent_giam_sat` canh). Không đọc bảng
khách, không đọc phiếu khám, không đọc chữ tự do của người.

KHOÁ LÀ TỆP, không phải biến môi trường: `/run/secrets/agent_llm_api_key`
(docker secret, xem docker-compose.yml). Cố ý tách khỏi ANTHROPIC_API_KEY — có
biến ấy là main.py bật AI phân loại xét nghiệm, thứ gửi NỘI DUNG kết quả đi.
Không có tệp / tệp rỗng / không phải khoá thật → tính năng tắt, màn nói rõ.

TIỀN: mọi lần gọi đi qua `AnthropicClient(pool=…)` → ghi `llm_lan_goi`, chạm
trần ngày thì tự dừng (`llm/chi_phi.py`).
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Awaitable, Callable
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import asyncpg
import structlog

from clinicai.core.clock import hom_nay_vn, now_vn
from clinicai.core.tran import canh_bao_neu_day
from clinicai.llm.anthropic_client import AnthropicClient, LLMResponse
from clinicai.services.agent_giam_sat import LOAI, PHIEN_BAN

logger = structlog.get_logger()

TINH_NANG = "agent_tom_tat"
#: Tối đa nhận định gửi kèm một lần — đủ cho một ngày đông, chặn prompt phình.
TRAN_NHAN_DINH = 80
#: Lỗi thì chờ chừng này mới thử tự động lại (đỡ log rác mỗi phút).
CHO_THU_LAI_GIAY = 30 * 60

_lan_thu_cuoi: dict[str, float] = {}


def duong_khoa() -> Path:
    return Path(os.environ.get("AGENT_LLM_KEY_PATH", "/run/secrets/agent_llm_api_key"))


def doc_khoa() -> str | None:
    """Khoá thật (`sk-ant-…`) hoặc None. Không bao giờ ném, không log khoá."""
    try:
        k = duong_khoa().read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return k if k.startswith("sk-ant-") and len(k) > 20 else None


def model() -> str:
    # Sonnet 5.5 (Tuyền chọn 09/10/2026 — rẻ bằng nửa Opus, đủ cho việc tóm
    # tắt nhận định đã có cấu trúc). Đổi model = đặt AGENT_LLM_MODEL, không sửa code.
    return os.environ.get("AGENT_LLM_MODEL", "").strip() or "claude-sonnet-5-5"


def gio_tu_dong() -> int:
    try:
        g = int(os.environ.get("AGENT_TOM_TAT_GIO", "18"))
    except ValueError:
        g = 18
    return g if 0 <= g <= 23 else 18


HE_THONG = """Bạn là agent giám sát vận hành của ClinicAI — phần mềm quản lý \
phòng khám \
Dr4Women. Bạn đọc các nhận định mà luật giám sát ghi trong một ngày (đã không có tên \
khách) và viết bản tóm tắt cho đội vận hành.

Nguyên tắc:
- Ưu tiên: an toàn > phản ánh đúng thực tế > không để rơi khách hay việc > trải nghiệm \
khách > bảo vệ nhân viên > điều phối > hiệu suất > kinh doanh.
- Tách rõ điều quan sát được với điều suy ra. Nhận định có \
muc_bang_chung = "suy_ra" là \
đoán từ chỗ vắng sự kiện, không phải sự thật đã xác nhận.
- Dữ liệu không đủ để kết luận thì nói thẳng là chưa đủ dữ liệu. Không bịa số, không \
đoán nguyên nhân không có trong dữ liệu.
- Tìm điều kiện của hệ thống khiến chuyện xảy ra trước khi nghĩ tới lỗi \
của người. \
Không nêu và không đoán cá nhân nào.
- Không chẩn đoán, không bàn chuyên môn y khoa.
- Nhận định quản lý đã chấm "sai" là dấu hiệu luật giám sát cần sửa, không phải sự \
việc thật.
- Bạn chỉ đề xuất. Con người quyết định và thực hiện.

Viết tiếng Việt, ngắn gọn, đúng các mục sau (bỏ mục nào không có gì để nói):
## Tình hình hôm nay
2–4 câu, có số.
## Điểm cần chú ý
Tối đa 5 gạch đầu dòng; mỗi dòng: chuyện gì · bằng chứng (số, giờ) · vì sao đáng chú ý.
## Đề xuất
Tối đa 3; mỗi đề xuất: làm gì · vai nào phù hợp (không nêu tên người) · \
làm sao biết đã xong.
## Luật giám sát cần xem lại
Nhận định bị chấm sai, trùng nhau, hoặc báo cùng một chuyện hai lần.
## Chưa biết
Điều dữ liệu hôm nay không cho biết.
Không chép lại dữ liệu thô. Dưới 350 từ."""


async def dau_vao(pool: asyncpg.Pool, *, clinic_id: str, ngay: date) -> dict[str, Any]:
    """Thứ DUY NHẤT gửi cho LLM: số đếm + nhận định của ngày (không tên khách)."""
    dau = ngay
    cuoi = ngay + timedelta(days=1)
    giao_ngay = (
        "mo_luc < ($3::date AT TIME ZONE 'Asia/Ho_Chi_Minh')"
        " AND (dong_luc IS NULL OR dong_luc >= ($2::date AT TIME ZONE"
        " 'Asia/Ho_Chi_Minh'))"
    )
    rows = await pool.fetch(
        f"""
        SELECT loai, muc, muc_bang_chung, noi_dung, so_lan, danh_gia,
               danh_gia_ghi_chu, ly_do_dong,
               to_char(mo_luc AT TIME ZONE 'Asia/Ho_Chi_Minh', 'HH24:MI') AS mo,
               to_char(dong_luc AT TIME ZONE 'Asia/Ho_Chi_Minh', 'HH24:MI') AS dong
          FROM agent_nhan_dinh
         WHERE clinic_id = $1::uuid AND {giao_ngay}
         ORDER BY CASE muc WHEN 'critical' THEN 0 ELSE 1 END, mo_luc
         LIMIT {TRAN_NHAN_DINH}
        """,
        clinic_id,
        dau,
        cuoi,
    )
    bi_cat = canh_bao_neu_day(
        "agent.tom_tat.nhan_dinh", len(rows), TRAN_NHAN_DINH, clinic_id=clinic_id
    )
    theo_loai = await pool.fetch(
        f"""
        SELECT loai, count(*) AS so, count(*) FILTER (WHERE dong_luc IS NULL) AS con_mo,
               count(*) FILTER (WHERE danh_gia = 'dung') AS dung,
               count(*) FILTER (WHERE danh_gia = 'sai') AS sai
          FROM agent_nhan_dinh
         WHERE clinic_id = $1::uuid AND {giao_ngay}
         GROUP BY loai
        """,
        clinic_id,
        dau,
        cuoi,
    )
    luot = await pool.fetchrow(
        """
        SELECT count(*) AS check_in,
               count(*) FILTER (WHERE closed_at IS NOT NULL) AS da_dong
          FROM visit
         WHERE clinic_id = $1::uuid AND checked_in_at IS NOT NULL
           AND (checked_in_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date = $2::date
        """,
        clinic_id,
        dau,
    )
    return {
        "ngay": ngay.isoformat(),
        "phien_ban_luat": PHIEN_BAN,
        "luot_kham": {
            "check_in": int(luot["check_in"]) if luot else 0,
            "da_dong": int(luot["da_dong"]) if luot else 0,
        },
        "theo_loai": [
            {
                "loai": r["loai"],
                "ten": LOAI.get(r["loai"], r["loai"]),
                "so_nhan_dinh": int(r["so"]),
                "con_mo": int(r["con_mo"]),
                "cham_dung": int(r["dung"]),
                "cham_sai": int(r["sai"]),
            }
            for r in theo_loai
        ],
        "nhan_dinh": [
            {
                "loai": r["loai"],
                "muc": r["muc"],
                "muc_bang_chung": r["muc_bang_chung"],
                "noi_dung": r["noi_dung"],
                "mo": r["mo"],
                "dong": r["dong"],
                "ly_do_dong": r["ly_do_dong"],
                "so_phut_thay": int(r["so_lan"]),
                "cham": r["danh_gia"],
                "ghi_chu_cham": r["danh_gia_ghi_chu"],
            }
            for r in rows
        ],
        "nhan_dinh_bi_cat": bi_cat,
    }


class LlmTatError(Exception):
    """Chưa có khoá LLM thật — tóm tắt bằng LLM đang tắt."""


class TomTatHongError(Exception):
    """LLM không trả được bản tóm tắt (từ chối / rỗng)."""


GoiLlm = Callable[..., Awaitable[LLMResponse]]


async def tao(
    pool: asyncpg.Pool,
    *,
    clinic_id: str,
    ngay: date,
    staff_id: str | None = None,
    goi: GoiLlm | None = None,
) -> dict[str, Any]:
    """Tạo một bản tóm tắt cho ngày `ngay`. `goi` để test thay LLM thật.

    Ném `LlmTatError` (không khoá), `VuotTranChiPhiError` (chạm trần),
    `TomTatHongError` (LLM từ chối / rỗng), hoặc lỗi API sau khi đã thử lại.
    """
    client: AnthropicClient | None = None
    if goi is None:
        khoa = doc_khoa()
        if khoa is None:
            raise LlmTatError("Chưa có khoá LLM cho agent (tệp agent_llm_api_key).")
        client = AnthropicClient(api_key=khoa, pool=pool)
        goi = client.chat
    try:
        dv = await dau_vao(pool, clinic_id=clinic_id, ngay=ngay)
        resp = await goi(
            messages=[
                {
                    "role": "user",
                    "content": "Dữ liệu giám sát (JSON):\n"
                    + json.dumps(dv, ensure_ascii=False),
                }
            ],
            system=HE_THONG,
            model=model(),
            # Opus 5.5 / Sonnet 5.5 trả 400 khi có tham số lấy mẫu.
            temperature=None,
            # Thinking luôn bật ở Opus 5.5 — chừa chỗ cho cả nghĩ lẫn chữ.
            max_tokens=8000,
            tinh_nang=TINH_NANG,
            # Bị từ chối thì API tự chạy lại trên model dự phòng cùng lượt gọi.
            extra_headers={"anthropic-beta": "server-side-fallback-2026-07-01"},
            extra_body={"fallbacks": "default", "output_config": {"effort": "medium"}},
        )
    finally:
        if client is not None:
            await client.close()
    noi_dung = (resp.text or "").strip()
    if resp.stop_reason == "refusal" or not noi_dung:
        raise TomTatHongError(
            "LLM không trả bản tóm tắt"
            + (" (từ chối)." if resp.stop_reason == "refusal" else " (rỗng).")
        )
    r = await pool.fetchrow(
        """
        INSERT INTO agent_tom_tat
            (clinic_id, ngay, noi_dung, model, lan_goi_id, tao_boi)
        VALUES ($1::uuid, $2, $3, $4, $5::uuid, $6::uuid)
        RETURNING id::text, tao_luc
        """,
        clinic_id,
        ngay,
        noi_dung,
        resp.model,
        resp.lan_goi_id,
        staff_id,
    )
    assert r is not None
    return {
        "id": r["id"],
        "ngay": ngay.isoformat(),
        "noi_dung": noi_dung,
        "model": resp.model,
        "tao_luc": r["tao_luc"].isoformat(),
        "tu_dong": staff_id is None,
    }


async def doc(pool: asyncpg.Pool, *, clinic_id: str, ngay: date) -> dict[str, Any]:
    """Bản mới nhất của ngày + LLM đang bật hay tắt (màn nói rõ)."""
    r = await pool.fetchrow(
        """
        SELECT id::text, noi_dung, model, tao_luc, tao_boi IS NULL AS tu_dong
          FROM agent_tom_tat
         WHERE clinic_id = $1::uuid AND ngay = $2
         ORDER BY tao_luc DESC LIMIT 1
        """,
        clinic_id,
        ngay,
    )
    return {
        "ngay": ngay.isoformat(),
        "llm_bat": doc_khoa() is not None,
        "model": model(),
        "gio_tu_dong": gio_tu_dong(),
        "tom_tat": None
        if r is None
        else {
            "id": r["id"],
            "noi_dung": r["noi_dung"],
            "model": r["model"],
            "tao_luc": r["tao_luc"].isoformat(),
            "tu_dong": bool(r["tu_dong"]),
        },
    }


async def tu_dong(pool: asyncpg.Pool) -> None:
    """Gọi mỗi phút từ vòng su-kien. Từ `gio_tu_dong()` giờ VN, mỗi phòng khám
    có MỘT bản tự động / ngày. Ngày không có gì (0 lượt, 0 nhận định) thì bỏ —
    không trả tiền để nghe "hôm nay yên". Không bao giờ ném."""
    try:
        if doc_khoa() is None or now_vn().hour < gio_tu_dong():
            return
        ngay = hom_nay_vn()
        clinics = await pool.fetch(
            """
            SELECT c.id::text AS id FROM clinic c
             WHERE NOT EXISTS (SELECT 1 FROM agent_tom_tat t
                                WHERE t.clinic_id = c.id AND t.ngay = $1
                                  AND t.tao_boi IS NULL)
               AND (EXISTS (SELECT 1 FROM agent_nhan_dinh n
                             WHERE n.clinic_id = c.id
                               AND (n.mo_luc AT TIME ZONE
                                    'Asia/Ho_Chi_Minh')::date = $1)
                    OR EXISTS (SELECT 1 FROM visit v
                                WHERE v.clinic_id = c.id
                                  AND (v.checked_in_at AT TIME ZONE
                                       'Asia/Ho_Chi_Minh')::date = $1))
            """,
            ngay,
        )
    except Exception:  # noqa: BLE001
        logger.exception("agent_tom_tat_tu_dong_hong")
        return
    for r in clinics:
        cid = r["id"]
        if time.monotonic() - _lan_thu_cuoi.get(cid, -1e9) < CHO_THU_LAI_GIAY:
            continue
        _lan_thu_cuoi[cid] = time.monotonic()
        try:
            await tao(pool, clinic_id=cid, ngay=ngay)
            logger.info("agent_tom_tat_xong", clinic_id=cid, ngay=ngay.isoformat())
        except Exception:  # noqa: BLE001 — chạm trần / API hỏng: thử lại sau
            logger.exception("agent_tom_tat_hong", clinic_id=cid)
