"""LƯU HỘI THOẠI của trợ lý — bảng `tro_ly_hoi_thoai` + `tro_ly_tin`.

Mỗi lượt khách nhắn ghi MỌI tin bộ não sinh ra (tin khách, các lượt gọi công cụ,
kết quả công cụ, nháp), theo đúng thứ tự — lượt sau dựng lại lịch sử y hệt thứ
model đã thấy. Dòng nháp (`la_nhap`) mang `meta`: công cụ đã gọi, model, phiên
bản lời nhắc, token, lý do chuyển người — để trả lời được "sao AI nói vậy".

Nhân viên duyệt nháp: `duyet` (gửi nguyên) · `sua` (gửi bản sửa) · `chuyen`
(người tiếp nhận, không gửi). Mọi thao tác HOÀN TÁC được (`hoan_tac` → về nháp).
Lịch sử lượt sau dùng ĐÚNG chữ khách đã nhận: bản sửa nếu có, câu tiếp nhận nếu
đã chuyển.

Gọi model KHÔNG nằm trong giao dịch (mất vài giây); chỉ lúc ghi mới khoá dòng
hội thoại và lấy số thứ tự kế tiếp. `UNIQUE (hoi_thoai_id, thu_tu)` ở Postgres
là chốt cuối nếu hai lượt ghi cùng lúc.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime
from typing import Any, Literal

import asyncpg

from clinicai.ports.mo_hinh import GoiCongCu, MoHinhPort, Tin
from clinicai.services.tro_ly_khach import bo_nao
from clinicai.services.tro_ly_khach.cong_cu import BoCongCu

HanhDong = Literal["duyet", "sua", "chuyen", "hoan_tac"]
CAU_DA_CHUYEN = "(Nhân viên phòng khám đã tiếp nhận cuộc trò chuyện.)"
#: Tin khách dài hơn thế này là dán nhầm cả trang — cắt, không gửi model.
DAI_TOI_DA = 2000


class TroLyError(ValueError):
    """Đầu vào sai (tin rỗng, hội thoại không có, hành động lạ) — router trả 4xx."""


def _goi_json(goi: Sequence[GoiCongCu]) -> str:
    return json.dumps(
        [{"ma": g.ma, "ten": g.ten, "tham_so": g.tham_so} for g in goi],
        ensure_ascii=False,
    )


def _jsonb(v: Any) -> Any:
    return json.loads(v) if isinstance(v, str) else v


def dung_lich_su(dong: Sequence[dict[str, Any]]) -> list[Tin]:
    """Dòng DB → `Tin` cho model. Nháp đã sửa/đã chuyển thay bằng chữ khách
    thật sự nhận."""
    ra: list[Tin] = []
    for d in dong:
        noi_dung = d["noi_dung"]
        if d["la_nhap"] and d["duyet"] == "sua" and d["noi_dung_gui"]:
            noi_dung = d["noi_dung_gui"]
        elif d["la_nhap"] and d["duyet"] == "chuyen":
            noi_dung = CAU_DA_CHUYEN
        goi = tuple(
            GoiCongCu(ma=g["ma"], ten=g["ten"], tham_so=g.get("tham_so") or {})
            for g in (_jsonb(d["goi_cong_cu"]) or [])
        )
        ra.append(Tin(d["vai"], noi_dung, goi, d["ma_goi"] or ""))
    return ra


def meta_nhap(kq: bo_nao.KetQuaTroLy) -> dict[str, Any]:
    return {
        "buoc": [
            {"ten": b.ten, "tham_so": b.tham_so, "ket_qua": b.ket_qua} for b in kq.buoc
        ],
        "chuyen_nguoi": kq.chuyen_nguoi,
        "ly_do_chuyen": kq.ly_do_chuyen,
        "ghi_chu_chuyen": kq.ghi_chu_chuyen,
        "chan_boi_code": kq.chan_boi_code,
        "model": kq.model,
        "phien_ban_loi_nhac": kq.phien_ban_loi_nhac,
        "token_vao": kq.token_vao,
        "token_ra": kq.token_ra,
        "thoi_gian_ms": kq.thoi_gian_ms,
        "so_vong": kq.so_vong,
        "lan_goi_ids": kq.lan_goi_ids,
        "loi": kq.loi,
    }


_COT_TIN = """
    id::text, thu_tu, vai, noi_dung, goi_cong_cu, ma_goi, la_nhap, meta,
    duyet, noi_dung_gui, duyet_luc, tao_luc
"""


def _dong_tin(r: Any) -> dict[str, Any]:
    d = dict(r)
    d["goi_cong_cu"] = _jsonb(d["goi_cong_cu"]) or []
    d["meta"] = _jsonb(d["meta"])
    return d


async def tao(
    pool: asyncpg.Pool, *, clinic_id: str, staff_id: str | None, tieu_de: str | None
) -> dict[str, Any]:
    r = await pool.fetchrow(
        """
        INSERT INTO public.tro_ly_hoi_thoai (clinic_id, tieu_de, tao_boi)
        VALUES ($1::uuid, nullif(btrim($2), ''), $3::uuid)
        RETURNING id::text, tieu_de, kenh, tao_luc, cap_nhat_luc
        """,
        clinic_id,
        (tieu_de or "")[:120],
        staff_id,
    )
    return dict(r)


async def danh_sach(
    pool: asyncpg.Pool, *, clinic_id: str, gioi_han: int = 30
) -> list[dict[str, Any]]:
    rows = await pool.fetch(
        """
        SELECT h.id::text, h.tieu_de, h.kenh, h.tao_luc, h.cap_nhat_luc,
               (SELECT count(*) FROM public.tro_ly_tin t
                 WHERE t.hoi_thoai_id = h.id AND t.vai = 'khach') AS so_tin_khach,
               (SELECT count(*) FROM public.tro_ly_tin t
                 WHERE t.hoi_thoai_id = h.id AND t.la_nhap AND t.duyet IS NULL)
                 AS so_nhap_cho
          FROM public.tro_ly_hoi_thoai h
         WHERE h.clinic_id = $1::uuid
         ORDER BY h.cap_nhat_luc DESC
         LIMIT $2
        """,
        clinic_id,
        max(1, min(gioi_han, 100)),
    )
    return [dict(r) for r in rows]


async def _doc_tin(conn: Any, hoi_thoai_id: str) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        f"SELECT {_COT_TIN} FROM public.tro_ly_tin"
        " WHERE hoi_thoai_id = $1::uuid ORDER BY thu_tu",
        hoi_thoai_id,
    )
    return [_dong_tin(r) for r in rows]


async def doc(
    pool: asyncpg.Pool, *, clinic_id: str, hoi_thoai_id: str
) -> dict[str, Any] | None:
    h = await pool.fetchrow(
        """
        SELECT id::text, tieu_de, kenh, tao_luc, cap_nhat_luc
          FROM public.tro_ly_hoi_thoai WHERE id = $1::uuid AND clinic_id = $2::uuid
        """,
        hoi_thoai_id,
        clinic_id,
    )
    if h is None:
        return None
    return {**dict(h), "tin": await _doc_tin(pool, hoi_thoai_id)}


async def gui_tin(
    pool: asyncpg.Pool,
    mo_hinh: MoHinhPort,
    bo_cong_cu: BoCongCu,
    *,
    clinic_id: str,
    hoi_thoai_id: str,
    noi_dung: str,
    luc: datetime,
) -> dict[str, Any]:
    """Một lượt: dựng lịch sử → bộ não → ghi mọi tin mới. Trả hội thoại đầy đủ."""
    noi_dung = (noi_dung or "").strip()[:DAI_TOI_DA]
    if not noi_dung:
        raise TroLyError("Tin nhắn rỗng.")
    hien_co = await doc(pool, clinic_id=clinic_id, hoi_thoai_id=hoi_thoai_id)
    if hien_co is None:
        raise TroLyError("Không có hội thoại này.")

    kq = await bo_nao.tra_loi(
        mo_hinh,
        tin_khach=noi_dung,
        lich_su=dung_lich_su(hien_co["tin"]),
        bo_cong_cu=bo_cong_cu,
        luc=luc,
    )

    async with pool.acquire() as conn, conn.transaction():
        # Khoá dòng hội thoại: hai lượt ghi cùng lúc lấy số thứ tự lần lượt.
        await conn.execute(
            "SELECT 1 FROM public.tro_ly_hoi_thoai WHERE id = $1::uuid FOR UPDATE",
            hoi_thoai_id,
        )
        ke = await conn.fetchval(
            "SELECT coalesce(max(thu_tu), 0) FROM public.tro_ly_tin"
            " WHERE hoi_thoai_id = $1::uuid",
            hoi_thoai_id,
        )
        cuoi = len(kq.tin_moi) - 1
        for i, t in enumerate(kq.tin_moi):
            la_nhap = i == cuoi
            await conn.execute(
                """
                INSERT INTO public.tro_ly_tin
                    (hoi_thoai_id, thu_tu, vai, noi_dung, goi_cong_cu, ma_goi,
                     la_nhap, meta)
                VALUES ($1::uuid, $2, $3, $4, $5::jsonb, nullif($6, ''), $7, $8::jsonb)
                """,
                hoi_thoai_id,
                ke + 1 + i,
                t.vai,
                t.noi_dung,
                _goi_json(t.goi_cong_cu),
                t.ma_goi,
                la_nhap,
                json.dumps(meta_nhap(kq), ensure_ascii=False, default=str)
                if la_nhap
                else None,
            )
        await conn.execute(
            """
            UPDATE public.tro_ly_hoi_thoai
               SET cap_nhat_luc = now(),
                   tieu_de = coalesce(tieu_de, left($2, 60))
             WHERE id = $1::uuid
            """,
            hoi_thoai_id,
            noi_dung,
        )
    ra = await doc(pool, clinic_id=clinic_id, hoi_thoai_id=hoi_thoai_id)
    assert ra is not None
    return ra


async def duyet(
    pool: asyncpg.Pool,
    *,
    clinic_id: str,
    tin_id: str,
    staff_id: str | None,
    hanh_dong: str,
    noi_dung: str | None = None,
) -> dict[str, Any]:
    if hanh_dong not in ("duyet", "sua", "chuyen", "hoan_tac"):
        raise TroLyError(f"Hành động lạ: {hanh_dong!r}")
    sua = (noi_dung or "").strip()[:DAI_TOI_DA] if hanh_dong == "sua" else None
    if hanh_dong == "sua" and not sua:
        raise TroLyError("Bản sửa rỗng.")
    r = await pool.fetchrow(
        f"""
        UPDATE public.tro_ly_tin t
           SET duyet = CASE WHEN $3 = 'hoan_tac' THEN NULL ELSE $3 END,
               noi_dung_gui = $4,
               duyet_boi = CASE WHEN $3 = 'hoan_tac' THEN NULL ELSE $5::uuid END,
               duyet_luc = CASE WHEN $3 = 'hoan_tac' THEN NULL ELSE now() END
          FROM public.tro_ly_hoi_thoai h
         WHERE t.id = $1::uuid AND t.la_nhap
           AND h.id = t.hoi_thoai_id AND h.clinic_id = $2::uuid
        RETURNING {", ".join("t." + c.strip() for c in _COT_TIN.split(","))}
        """,
        tin_id,
        clinic_id,
        hanh_dong,
        sua,
        staff_id,
    )
    if r is None:
        raise TroLyError("Không có nháp này.")
    return _dong_tin(r)


__all__ = [
    "CAU_DA_CHUYEN",
    "TroLyError",
    "danh_sach",
    "doc",
    "dung_lich_su",
    "duyet",
    "gui_tin",
    "meta_nhap",
    "tao",
]
