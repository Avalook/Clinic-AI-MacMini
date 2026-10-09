"""ĐỒNG HỒ TIỀN LLM (09/10/2026).

Mọi lần ClinicAI gọi Anthropic qua `AnthropicClient` có `pool` → một dòng
`llm_lan_goi`: model, token, USD. Không cần vào Console vẫn biết đã đốt bao
nhiêu (key thường không đọc được số dư; số dư chỉ có trong Console → Billing).

TRẦN THEO NGÀY: trước mỗi lần gọi, cộng tiền hôm nay (giờ VN); chạm trần thì
TỪ CHỐI gọi (`VuotTranChiPhiError`) — người dùng thấy "đã chạm trần", không phải hoá
đơn bất ngờ. Đổi trần bằng `LLM_TRAN_NGAY_USD`, không sửa code.

BẢNG GIÁ là bản chép của trang giá Anthropic (USD / 1 triệu token) lúc viết —
giá đổi thì sửa MỘT chỗ ở đây. Model chưa có trong bảng: vẫn ghi token, tiền
để trống (`None`), màn nói "chưa có giá" chứ không đoán.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import asyncpg
import structlog

logger = structlog.get_logger()

_TRIEU = Decimal(1_000_000)


@dataclass(frozen=True)
class Gia:
    """USD cho 1 triệu token."""

    vao: Decimal
    ra: Decimal
    doc_cache: Decimal

    @property
    def ghi_cache(self) -> Decimal:
        # Ghi cache 5 phút = 1,25 × giá vào (trang giá prompt caching).
        return self.vao * Decimal("1.25")


#: Giá Anthropic API trực tiếp, chép 06/10/2026. Khoá là tiền tố mã model —
#: phản hồi có thể mang mã kèm ngày (vd `claude-haiku-4-5-20251001`).
#: Haiku 5.5: giá này cho prompt ≤ 100K token (dài hơn đắt hơn — agent gửi vài
#: nghìn token nên không chạm).
BANG_GIA: dict[str, Gia] = {
    "claude-fable-5-1": Gia(Decimal("10"), Decimal("50"), Decimal("0.25")),
    "claude-opus-5-5": Gia(Decimal("4"), Decimal("20"), Decimal("0.20")),
    "claude-sonnet-5-5": Gia(Decimal("2"), Decimal("10"), Decimal("0.20")),
    "claude-haiku-5-5": Gia(Decimal("0.10"), Decimal("0.50"), Decimal("0.01")),
    "claude-sonnet-4-6": Gia(Decimal("3"), Decimal("15"), Decimal("0.30")),
    "claude-haiku-4-5": Gia(Decimal("1"), Decimal("5"), Decimal("0.10")),
}


def gia_cua(model: Any) -> Gia | None:
    """Giá theo tiền tố DÀI NHẤT khớp. Không khớp / rác → None."""
    if not isinstance(model, str) or not model:
        return None
    khop = [k for k in BANG_GIA if model.startswith(k)]
    return BANG_GIA[max(khop, key=len)] if khop else None


def _so_token(x: Any) -> int:
    return x if isinstance(x, int) and not isinstance(x, bool) and x > 0 else 0


def tinh_usd(
    model: Any, *, vao: Any, ra: Any, doc_cache: Any = 0, ghi_cache: Any = 0
) -> Decimal | None:
    """Tiền USD của một lần gọi. Model chưa có giá → None (không đoán)."""
    g = gia_cua(model)
    if g is None:
        return None
    tong = (
        _so_token(vao) * g.vao
        + _so_token(ra) * g.ra
        + _so_token(doc_cache) * g.doc_cache
        + _so_token(ghi_cache) * g.ghi_cache
    )
    return (tong / _TRIEU).quantize(Decimal("0.000001"))


def _so_env(ten: str, mac_dinh: str) -> Decimal:
    try:
        v = Decimal(os.environ.get(ten, mac_dinh).strip())
    except Exception:  # noqa: BLE001 — env rác → mặc định, không chết lúc khởi động
        v = Decimal(mac_dinh)
    return v if v >= 0 else Decimal(mac_dinh)


def tran_ngay_usd() -> Decimal:
    return _so_env("LLM_TRAN_NGAY_USD", "2")


def ty_gia_vnd() -> Decimal:
    """Chỉ để hiện "≈ đồng" — tiền thật vẫn là USD."""
    return _so_env("LLM_TY_GIA_VND", "26000")


class VuotTranChiPhiError(Exception):
    """Tiền LLM hôm nay đã chạm trần — không gọi thêm."""


_HOM_NAY = (
    "luc >= (date_trunc('day', now() AT TIME ZONE 'Asia/Ho_Chi_Minh')"
    " AT TIME ZONE 'Asia/Ho_Chi_Minh')"
)


async def da_tieu_hom_nay(pool: asyncpg.Pool) -> Decimal:
    v = await pool.fetchval(
        f"SELECT coalesce(sum(chi_phi_usd), 0) FROM llm_lan_goi WHERE {_HOM_NAY}"
    )
    return Decimal(v or 0)


async def chan_neu_vuot_tran(pool: asyncpg.Pool) -> None:
    tran = tran_ngay_usd()
    da = await da_tieu_hom_nay(pool)
    if da >= tran:
        raise VuotTranChiPhiError(
            f"Tiền LLM hôm nay {da} USD đã chạm trần {tran} USD (LLM_TRAN_NGAY_USD)."
        )


async def ghi_lan_goi(
    pool: asyncpg.Pool,
    *,
    tinh_nang: str,
    model: str,
    vao: int = 0,
    ra: int = 0,
    doc_cache: int = 0,
    ghi_cache: int = 0,
    clinic_id: str | None = None,
    thanh_cong: bool = True,
    loi: str | None = None,
    ma_yeu_cau: str | None = None,
    thoi_gian_ms: int | None = None,
) -> str | None:
    """Ghi một lần gọi. KHÔNG BAO GIỜ ném: đồng hồ hỏng không được làm hỏng
    lần gọi đã trả tiền xong."""
    try:
        return str(
            await pool.fetchval(
                """
                INSERT INTO llm_lan_goi
                    (tinh_nang, model, input_tokens, output_tokens,
                     cache_doc_tokens, cache_ghi_tokens, chi_phi_usd, clinic_id,
                     thanh_cong, loi, ma_yeu_cau, thoi_gian_ms)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8::uuid, $9, $10, $11, $12)
                RETURNING id
                """,
                tinh_nang,
                model or "?",
                _so_token(vao),
                _so_token(ra),
                _so_token(doc_cache),
                _so_token(ghi_cache),
                tinh_usd(
                    model, vao=vao, ra=ra, doc_cache=doc_cache, ghi_cache=ghi_cache
                ),
                clinic_id,
                thanh_cong,
                (loi or None) and str(loi)[:500],
                ma_yeu_cau,
                thoi_gian_ms,
            )
        )
    except Exception:  # noqa: BLE001
        logger.exception("llm_chi_phi_ghi_hong", model=model, tinh_nang=tinh_nang)
        return None


def _f(x: Any) -> float:
    return float(x or 0)


async def so_lieu(pool: asyncpg.Pool, *, so_ngay: int = 7) -> dict[str, Any]:
    """Cho màn: hôm nay so với trần, theo model / theo ngày trong `so_ngay`
    ngày, 20 lần gọi gần nhất, và bảng giá đang áp."""
    so_ngay = max(1, min(int(so_ngay), 31))
    tu = (
        "luc >= (date_trunc('day', now() AT TIME ZONE 'Asia/Ho_Chi_Minh')"
        " AT TIME ZONE 'Asia/Ho_Chi_Minh') - make_interval(days => $1 - 1)"
    )
    theo_model = await pool.fetch(
        f"""
        SELECT model, count(*) AS lan_goi,
               count(*) FILTER (WHERE NOT thanh_cong) AS lan_loi,
               sum(input_tokens) AS vao, sum(output_tokens) AS ra,
               sum(cache_doc_tokens) AS doc_cache,
               sum(cache_ghi_tokens) AS ghi_cache,
               sum(chi_phi_usd) AS usd,
               bool_or(chi_phi_usd IS NULL AND thanh_cong) AS thieu_gia
          FROM llm_lan_goi WHERE {tu}
         GROUP BY model ORDER BY sum(chi_phi_usd) DESC NULLS LAST
        """,
        so_ngay,
    )
    theo_ngay = await pool.fetch(
        f"""
        SELECT (luc AT TIME ZONE 'Asia/Ho_Chi_Minh')::date AS ngay,
               count(*) AS lan_goi, sum(chi_phi_usd) AS usd
          FROM llm_lan_goi WHERE {tu}
         GROUP BY 1 ORDER BY 1 DESC
        """,
        so_ngay,
    )
    gan_day = await pool.fetch(
        """
        SELECT luc, tinh_nang, model, input_tokens, output_tokens,
               cache_doc_tokens, cache_ghi_tokens, chi_phi_usd, thanh_cong,
               loi, thoi_gian_ms
          FROM llm_lan_goi ORDER BY luc DESC LIMIT 20
        """
    )
    hom_nay = await da_tieu_hom_nay(pool)
    tran = tran_ngay_usd()
    ty_gia = ty_gia_vnd()
    return {
        "hom_nay_usd": float(hom_nay),
        "hom_nay_vnd": int(hom_nay * ty_gia),
        "tran_ngay_usd": float(tran),
        "con_lai_hom_nay_usd": float(max(Decimal(0), tran - hom_nay)),
        "ty_gia_vnd": int(ty_gia),
        "so_ngay": so_ngay,
        # Đủ 20 dòng = còn cũ hơn nữa không hiện — màn nói "20 lần gần nhất".
        "gan_day_bi_cat": len(gan_day) >= 20,
        "theo_model": [
            {
                "model": r["model"],
                "lan_goi": int(r["lan_goi"]),
                "lan_loi": int(r["lan_loi"]),
                "vao": int(r["vao"] or 0),
                "ra": int(r["ra"] or 0),
                "doc_cache": int(r["doc_cache"] or 0),
                "ghi_cache": int(r["ghi_cache"] or 0),
                "usd": _f(r["usd"]),
                "thieu_gia": bool(r["thieu_gia"]),
            }
            for r in theo_model
        ],
        "theo_ngay": [
            {
                "ngay": r["ngay"].isoformat(),
                "lan_goi": int(r["lan_goi"]),
                "usd": _f(r["usd"]),
            }
            for r in theo_ngay
        ],
        # 20 dòng — cố ý: "gần đây" (màn nói rõ), không phải sổ đầy đủ.
        "gan_day": [
            {
                "luc": r["luc"].isoformat(),
                "tinh_nang": r["tinh_nang"],
                "model": r["model"],
                "vao": r["input_tokens"],
                "ra": r["output_tokens"],
                "doc_cache": r["cache_doc_tokens"],
                "ghi_cache": r["cache_ghi_tokens"],
                "usd": None if r["chi_phi_usd"] is None else float(r["chi_phi_usd"]),
                "thanh_cong": r["thanh_cong"],
                "loi": r["loi"],
                "thoi_gian_ms": r["thoi_gian_ms"],
            }
            for r in gan_day
        ],
        "bang_gia": [
            {
                "model": k,
                "vao": float(g.vao),
                "ra": float(g.ra),
                "doc_cache": float(g.doc_cache),
                "ghi_cache": float(g.ghi_cache),
            }
            for k, g in BANG_GIA.items()
        ],
        "gia_ngay": "06/10/2026",
    }
