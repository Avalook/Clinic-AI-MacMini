"""Chạy agent soát hệ thống (tầng 0: bộ quét tĩnh, không token, không chạm prod).

    .venv/bin/python scripts/soat_he_thong/chay.py            # chạy hết
    .venv/bin/python scripts/soat_he_thong/chay.py --chi cua_route,su_kien

Chỉ ĐỌC repo. Chỉ GHI vào `scripts/soat_he_thong/ket-qua/` (đã gitignore):
    <giờ>/phat-hien.jsonl   mỗi dòng một phát hiện (đủ 10 mục hiến pháp §13)
    <giờ>/do-phu.json       sổ độ phủ: bộ quét nhìn gì, MÙ ở đâu
    <giờ>/bi-loai.jsonl     phát hiện bị cửa trích dẫn loại, kèm lý do
    <giờ>/bao-cao.html      báo cáo cho người duyệt
    so-duyet.jsonl          quyết định của NGƯỜI (may_xem.py ghi), mọi lần quét
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

# Chạy được cả bằng `python scripts/soat_he_thong/chay.py` lẫn `-m`.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = "soat_he_thong"

from soat_he_thong import bao_cao, bat_bien, doc_du_lieu, kiem_trich_dan  # noqa: E402
from soat_he_thong.bo_quet import DANH_SACH, nap  # noqa: E402
from soat_he_thong.khuon import DoPhu, PhatHien  # noqa: E402
from soat_he_thong.nguon import Nguon  # noqa: E402

KET_QUA = Path(__file__).resolve().parent / "ket-qua"


def doc_so_duyet(duong: Path) -> dict[str, dict[str, str]]:
    """Quyết định mới nhất của người cho từng id phát hiện."""
    ra: dict[str, dict[str, str]] = {}
    if not duong.is_file():
        return ra
    for dong in duong.read_text(encoding="utf8").splitlines():
        try:
            d = json.loads(dong)
        except json.JSONDecodeError:
            continue
        if isinstance(d, dict) and "id" in d:
            ra[str(d["id"])] = d
    return ra


def chay(
    chi: list[str] | None = None,
    ra: Path | None = None,
    docker: str | None = None,
    tep_nap: Path | None = None,
) -> Path:
    nguon = Nguon()
    thu_muc = ra or KET_QUA / time.strftime("%Y%m%d-%H%M%S")
    thu_muc.mkdir(parents=True, exist_ok=True)

    tat_ca: list[PhatHien] = []
    do_phu: list[DoPhu] = []
    for ten in chi or list(DANH_SACH):
        t0 = time.time()
        ds, do = nap(ten)(nguon)
        print(f"  {ten:<22} {len(ds):>4} phát hiện · {time.time() - t0:.1f}s")
        tat_ca += ds
        do_phu.append(do)

    if docker or tep_nap:
        if docker:
            kq = doc_du_lieu.phan_tich_dau_ra(doc_du_lieu.chay_qua_docker(docker))
            nd = f"DB local trong container {docker} (dữ liệu DEMO)"
        else:
            assert tep_nap is not None
            kq = doc_du_lieu.doc_tep_nap(tep_nap)
            nd = f"tệp kết quả do người chạy trên máy chủ nạp về: {tep_nap.name}"
        ds, do = doc_du_lieu.thanh_phat_hien(nguon, kq, nd)
        print(f"  {'bat_bien_du_lieu':<22} {len(ds):>4} phát hiện · {len(kq)} bất biến")
        tat_ca += ds
        do_phu.append(do)
    else:
        do_phu.append(
            DoPhu(
                "bat_bien_du_lieu",
                khong_nhin_duoc=[
                    "CHƯA CHẠY — cần --docker <container local> hoặc --nap <tệp>"
                ],
            )
        )

    giu, loai = kiem_trich_dan.loc(nguon, tat_ca)
    so_duyet = doc_so_duyet(KET_QUA / "so-duyet.jsonl")

    (thu_muc / "phat-hien.jsonl").write_text(
        "".join(json.dumps(p.dict(), ensure_ascii=False) + "\n" for p in giu),
        encoding="utf8",
    )
    (thu_muc / "bi-loai.jsonl").write_text(
        "".join(
            json.dumps({"id": p.id, "ly_do": ly, "khoa": p.khoa}, ensure_ascii=False)
            + "\n"
            for p, ly in loai
        ),
        encoding="utf8",
    )
    (thu_muc / "do-phu.json").write_text(
        json.dumps([asdict(d) for d in do_phu], ensure_ascii=False, indent=2),
        encoding="utf8",
    )
    (thu_muc / "bao-cao.html").write_text(
        bao_cao.html(giu, do_phu, loai, so_duyet), encoding="utf8"
    )
    print(
        f"\n{len(giu)} phát hiện giữ · {len(loai)} bị loại (trích dẫn sai) · "
        f"đã có {len(so_duyet)} quyết định của người\n→ {thu_muc}/bao-cao.html"
    )
    return thu_muc


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Agent soát hệ thống ClinicAI (chỉ đọc)")
    ap.add_argument("--chi", help="chỉ chạy các bộ quét này, cách nhau dấu phẩy")
    ap.add_argument("--ra", type=Path, help="thư mục kết quả (mặc định: ket-qua/<giờ>)")
    ap.add_argument("--docker", help="chạy bất biến dữ liệu trong container DB local")
    ap.add_argument(
        "--nap", type=Path, help="nạp kết quả bất biến do người chạy trên máy chủ"
    )
    ap.add_argument(
        "--in-sql", action="store_true", help="in tệp SQL chỉ-đọc rồi thoát"
    )
    a = ap.parse_args(argv)
    if a.in_sql:
        sys.stdout.write(bat_bien.tao_tep_sql())
        return 0
    chay([x for x in a.chi.split(",") if x] if a.chi else None, a.ra, a.docker, a.nap)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
