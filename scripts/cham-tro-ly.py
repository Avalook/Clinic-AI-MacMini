#!/usr/bin/env python3
"""CHẤM TRỢ LÝ AI trên bộ câu vàng — so nhiều model trên CÙNG một bảng.

    .venv/bin/python scripts/cham-tro-ly.py --mo-hinh anthropic:claude-haiku-5-5
    .venv/bin/python scripts/cham-tro-ly.py \\
        --mo-hinh anthropic:claude-haiku-5-5 --mo-hinh anthropic:claude-sonnet-5-5 \\
        --mo-hinh ollama:qwen3 --gioi-han 10

Khoá: tệp `$TRO_LY_THU_MUC_KHOA/tro_ly_khoa_<hãng>` hoặc biến
`TRO_LY_KHOA_<HÃNG>` (xem `clinicai/adapters/mo_hinh/__init__.py`).

Mặc định dùng công cụ MẪU (giá/giờ/lịch giả, không cần DB) — đo model có gọi
đúng công cụ và theo đúng kết quả không. `--db` đọc giá/giờ/lịch thật qua
`DATABASE_URL` (stack dev hoặc staging ĐÃ CHE); công cụ không đọc bảng khách.
Có `--db` thì mỗi lượt gọi ghi `llm_lan_goi` và chịu trần `LLM_TRAN_NGAY_USD`;
không có thì KHÔNG có trần — `--gioi-han` để thử ít câu trước.

Đo:  ý định = nhãn phân loại đúng · công cụ = gọi đủ công cụ bắt buộc ·
     chuyển người = chuyển đúng lúc cần, không chuyển khi không cần ·
     khẩn = câu khẩn bị code chặn (phải 100%).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

GOC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GOC / "src"))

from clinicai.adapters.mo_hinh import tao_mo_hinh  # noqa: E402
from clinicai.core.clock import now_vn  # noqa: E402
from clinicai.llm import chi_phi  # noqa: E402
from clinicai.ports.mo_hinh import MoHinhPort  # noqa: E402
from clinicai.services.tro_ly_khach import bo_nao  # noqa: E402
from clinicai.services.tro_ly_khach.cong_cu import (  # noqa: E402
    BoCongCu,
    CongCuMau,
    CongCuPhongKham,
)

CAU_VANG = GOC / "src/tests/tro_ly/cau_vang.json"


async def _bo_cong_cu_db(pool: Any) -> BoCongCu:
    clinic_id = os.environ.get("TRO_LY_CLINIC_ID") or str(
        await pool.fetchval("SELECT id FROM public.clinic ORDER BY created_at LIMIT 1")
    )
    location_id = await pool.fetchval(
        "SELECT id::text FROM public.clinic_location"
        " WHERE clinic_id = $1::uuid AND code = 'HN' AND is_active",
        clinic_id,
    )
    return CongCuPhongKham(pool, clinic_id=clinic_id, location_id=location_id)


def _usd(model: str, vao: int, ra: int) -> Decimal | None:
    ten = model.split(":", 1)[-1]
    return chi_phi.tinh_usd(ten, vao=vao, ra=ra)


async def cham_mot(
    mh_tra_loi: MoHinhPort,
    mh_phan_loai: MoHinhPort,
    cau: dict[str, Any],
    bo_cong_cu: BoCongCu,
) -> dict[str, Any]:
    luc = now_vn()
    nhan, r_pl = await bo_nao.phan_loai(mh_phan_loai, cau["tin"])
    kq = await bo_nao.tra_loi(
        mh_tra_loi, tin_khach=cau["tin"], lich_su=[], bo_cong_cu=bo_cong_cu, luc=luc
    )
    goi = [b.ten for b in kq.buoc if b.ten != "chuyen_nguoi"]
    return {
        "ma": cau["ma"],
        "tin": cau["tin"],
        "y_dinh": [cau["y_dinh"], nhan],
        "dung_y_dinh": nhan == cau["y_dinh"],
        "dung_cong_cu": set(cau["cong_cu"]) <= set(goi),
        "dung_chuyen": kq.chuyen_nguoi == cau["chuyen_nguoi"],
        "khan_bi_chan": (kq.chan_boi_code == "khan_cap")
        if cau["y_dinh"] == "khan_cap"
        else None,
        "cong_cu_da_goi": goi,
        "chuyen_nguoi": [cau["chuyen_nguoi"], kq.chuyen_nguoi, kq.ly_do_chuyen],
        "nhap": kq.nhap,
        "loi": kq.loi,
        "usd_tra_loi": _usd(mh_tra_loi.ten, kq.token_vao, kq.token_ra),
        "usd_phan_loai": _usd(mh_phan_loai.ten, r_pl.token_vao, r_pl.token_ra)
        if r_pl
        else Decimal(0),
        "token": kq.token_vao
        + kq.token_ra
        + (r_pl.token_vao + r_pl.token_ra if r_pl else 0),
        "ms": kq.thoi_gian_ms + (r_pl.thoi_gian_ms if r_pl else 0),
        "so_vong": kq.so_vong,
    }


def _pt(dung: int, tong: int) -> str:
    return f"{dung}/{tong} ({100 * dung / tong:.0f}%)" if tong else "—"


def in_bang(theo_model: dict[str, list[dict[str, Any]]]) -> None:
    cot = (
        "model",
        "ý định",
        "công cụ",
        "chuyển người",
        "khẩn chặn",
        "token",
        "USD",
        "ms/câu",
    )
    hang: list[tuple[str, ...]] = [cot]
    for ten, kq in theo_model.items():
        n = len(kq)
        khan = [k for k in kq if k["khan_bi_chan"] is not None]
        tien = [k["usd_tra_loi"] for k in kq] + [k["usd_phan_loai"] for k in kq]
        usd = "chưa có giá" if any(t is None for t in tien) else f"{sum(tien):.4f}"
        hang.append(
            (
                ten,
                _pt(sum(k["dung_y_dinh"] for k in kq), n),
                _pt(sum(k["dung_cong_cu"] for k in kq), n),
                _pt(sum(k["dung_chuyen"] for k in kq), n),
                _pt(sum(bool(k["khan_bi_chan"]) for k in khan), len(khan)),
                str(sum(k["token"] for k in kq)),
                usd,
                str(sum(k["ms"] for k in kq) // max(n, 1)),
            )
        )
    rong = [max(len(str(h[i])) for h in hang) for i in range(len(cot))]
    for i, h in enumerate(hang):
        print("  ".join(str(o).ljust(rong[j]) for j, o in enumerate(h)))
        if i == 0:
            print("  ".join("-" * r for r in rong))


def in_cau_sai(ten: str, kq: list[dict[str, Any]]) -> None:
    sai = [
        k
        for k in kq
        if not (k["dung_y_dinh"] and k["dung_cong_cu"] and k["dung_chuyen"])
    ]
    if not sai:
        return
    print(f"\n# {ten}: {len(sai)} câu sai")
    for k in sai:
        phan = []
        if not k["dung_y_dinh"]:
            phan.append(f"ý định cần {k['y_dinh'][0]} ra {k['y_dinh'][1]}")
        if not k["dung_cong_cu"]:
            phan.append(f"công cụ đã gọi {k['cong_cu_da_goi'] or '∅'}")
        if not k["dung_chuyen"]:
            c = k["chuyen_nguoi"]
            phan.append(f"chuyển người cần {c[0]} ra {c[1]} ({c[2]})")
        print(f"- {k['ma']} «{k['tin']}» — " + "; ".join(phan))
        print(
            f"    nháp: {k['nhap'][:160]}"
            + (f"  [lỗi: {k['loi']}]" if k["loi"] else "")
        )


async def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--mo-hinh", action="append", required=True, help="hãng:model, lặp được"
    )
    ap.add_argument(
        "--phan-loai", help="model phân loại riêng (mặc định = model trả lời)"
    )
    ap.add_argument("--db", action="store_true", help="công cụ đọc DB qua DATABASE_URL")
    ap.add_argument("--gioi-han", type=int, default=0, help="chỉ chấm N câu đầu")
    ap.add_argument("--chi", default="", help="chỉ các mã, vd g01,g39")
    ap.add_argument("--ra", help="ghi chi tiết JSON ra tệp")
    a = ap.parse_args()

    cau = json.loads(CAU_VANG.read_text())["cau"]
    if a.chi:
        chon = set(a.chi.split(","))
        cau = [c for c in cau if c["ma"] in chon]
    if a.gioi_han:
        cau = cau[: a.gioi_han]

    pool = None
    bo_cong_cu: BoCongCu = CongCuMau()
    if a.db:
        import asyncpg

        pool = await asyncpg.create_pool(
            os.environ["DATABASE_URL"], min_size=1, max_size=3
        )
        bo_cong_cu = await _bo_cong_cu_db(pool)

    theo_model: dict[str, list[dict[str, Any]]] = {}
    try:
        for cau_hinh in a.mo_hinh:
            mh = tao_mo_hinh(cau_hinh, pool=pool)
            mh_pl = tao_mo_hinh(a.phan_loai, pool=pool) if a.phan_loai else mh
            try:
                kq = []
                for i, c in enumerate(cau, 1):
                    print(
                        f"\r{mh.ten}: {i}/{len(cau)}",
                        end="",
                        file=sys.stderr,
                        flush=True,
                    )
                    kq.append(await cham_mot(mh, mh_pl, c, bo_cong_cu))
                print(file=sys.stderr)
                theo_model[mh.ten] = kq
            finally:
                await mh.dong()
                if mh_pl is not mh:
                    await mh_pl.dong()
    finally:
        if pool is not None:
            await pool.close()

    print(f"\nBộ câu vàng: {len(cau)} câu · công cụ {'DB' if a.db else 'MẪU'}\n")
    in_bang(theo_model)
    for ten, kq in theo_model.items():
        in_cau_sai(ten, kq)
    if a.ra:
        Path(a.ra).write_text(
            json.dumps(theo_model, ensure_ascii=False, indent=1, default=str)
        )
    khan_hong = any(
        k["khan_bi_chan"] is False for kq in theo_model.values() for k in kq
    )
    return 1 if khan_hong else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
