"""Tầng model của agent soát — chạy THỦ CÔNG, có trần chi tiêu, có công tắc dừng.

    chay_model.py kiem-tra   --model openai/gpt-oss-120b:novita
    chay_model.py thuoc-do   --models a,b,c --tran 6
    chay_model.py soat       --model X --tran 4 [--cac src/clinicai/services]

Dừng khẩn cấp: `touch scripts/soat_he_thong/ket-qua/DUNG` — mọi lần gọi kế tiếp bị
chặn. Chi phí ghi ở `ket-qua/chi-phi.jsonl` (không có nội dung mã).
Chỉ gửi MÃ NGUỒN đã lọc (`che_du_lieu`) tới host trong danh sách cho phép. Dữ liệu
database không bao giờ đi qua đây.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = "soat_he_thong"

from soat_he_thong.chay import KET_QUA, chay  # noqa: E402
from soat_he_thong.khuon import DoPhu  # noqa: E402
from soat_he_thong.nguon import GOC, Nguon  # noqa: E402
from soat_he_thong.tang_model import soat_toan_bo, thuoc_do  # noqa: E402
from soat_he_thong.tang_model.chi_phi import SoChiPhi, TuChoiError  # noqa: E402
from soat_he_thong.tang_model.khach import goi  # noqa: E402


def _so(tran: float) -> SoChiPhi:
    return SoChiPhi(KET_QUA / "chi-phi.jsonl", tran, KET_QUA)


def kiem_tra(a: argparse.Namespace) -> int:
    so = _so(0.5)
    kq = goi(
        a.model,
        [{"role": "user", "content": "Trả lời đúng một từ: ok"}],
        so=so,
        max_tokens=64,
        nhan="kiem-tra",
    )
    print(
        f"{a.model}: {kq.van_ban.strip()[:40]!r} · vào {kq.token_vao} ra {kq.token_ra} "
        f"· ${kq.usd:.5f} · {kq.giay:.1f}s"
    )
    return 0


def do_thuoc(a: argparse.Namespace) -> int:
    so = _so(a.tran)
    gio = time.strftime("%Y%m%d-%H%M%S")
    thu_muc = KET_QUA / f"thuoc-do-{gio}-{os.getpid()}"
    thu_muc.mkdir(parents=True, exist_ok=True)
    kq: list[dict[str, object]] = []
    for mo_hinh in [m for m in a.models.split(",") if m]:
        print(f"\n▶ {mo_hinh} (đã tiêu ${so.da_tieu:.2f}/{a.tran})", flush=True)
        try:
            k = thuoc_do.chay_mot_mo_hinh(
                GOC, mo_hinh, so, thu_muc, song_song=a.song_song
            )
        except TuChoiError as e:
            print(f"  dừng: {e}")
            break
        kq.append(k)
        canh_bao = f" · ⚠ {k['dung_vi']}" if k["dung_vi"] else ""
        print(
            f"  trúng {k['so_trung']}/{k['tong_loi']} · ứng viên "
            f"{k['tong_ung_vien']} · ${k['usd']} · {k['giay']}s{canh_bao}"
        )
        (thu_muc / "ket-qua.json").write_text(
            json.dumps(kq, ensure_ascii=False, indent=1), encoding="utf8"
        )
        if k["dung_vi"]:
            break
    (thu_muc / "tom-tat.md").write_text(thuoc_do.tom_tat(kq), encoding="utf8")
    print(f"\nTổng ${so.da_tieu:.2f} · {thu_muc}/tom-tat.md")
    return 0


def soat(a: argparse.Namespace) -> int:
    nguon = Nguon()
    so = _so(a.tran)
    thu_muc = (
        Path(a.thu_muc)
        if a.thu_muc
        else KET_QUA / f"model-{time.strftime('%Y%m%d-%H%M%S')}"
    )
    thu_muc.mkdir(parents=True, exist_ok=True)
    tien_to = tuple(x for x in (a.tien_to or "").split(",") if x) or None
    cac_tep = soat_toan_bo.chon_tep(nguon, tien_to)[: a.toi_da_tep or None]
    models = [m for m in a.models.split(",") if m]
    print(
        f"Đọc {len(cac_tep)} tệp × {len(models)} model · trần ${a.tran} "
        f"· {thu_muc.name}"
    )
    _, dung = soat_toan_bo.doc_tat_ca(nguon, cac_tep, models, so, thu_muc, a.song_song)
    if dung:
        print(f"  ⚠ dừng khi đọc: {dung}")
    ung = soat_toan_bo.doc_lai_tho(thu_muc / "ung-vien-tho.jsonl")
    nhoms, bia = soat_toan_bo.gom(nguon, ung)
    nhoms.sort(
        key=lambda n: -max(x[0].do_chac for x in n)
        * (1 + 0.3 * len({x[0].mo_hinh for x in n}))
    )
    nhoms = nhoms[: a.toi_da_nhom]
    print(
        f"  {len(ung)} ứng viên → {len(nhoms)} nhóm giữ lại "
        f"· {bia} bị loại (trích dẫn bịa)"
    )
    kl = soat_toan_bo.bac_bo_tat_ca(nguon, nhoms, a.xac_nhan, so, a.song_song)
    giu, loai_sai = [], 0
    with (thu_muc / "bi-bac-bo.jsonl").open("w", encoding="utf8") as f:
        for n, k in zip(nhoms, kl, strict=True):
            if k.get("ket_luan") == "sai":
                loai_sai += 1
                u = max(n, key=lambda x: x[0].do_chac)[0]
                f.write(
                    json.dumps(
                        {
                            "tep": u.tep,
                            "dong": u.dong_tu,
                            "co_che": u.co_che,
                            "ly_do_bac_bo": k.get("ly_do"),
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                continue
            giu.append(soat_toan_bo.thanh_phat_hien(n, k))
    print(
        f"  bác bỏ: {loai_sai} nhóm bị loại · {len(giu)} nhóm đến người duyệt "
        f"· ${so.da_tieu:.2f}"
    )
    do = DoPhu(
        "model",
        da_nhin={
            "tệp đã đọc": len(cac_tep),
            "model đọc": len(models),
            "ứng viên thô": len(ung),
            "bị loại vì trích dẫn bịa": bia,
            "bị bác bỏ ở bước kiểm": loai_sai,
            "chi phí (xu USD)": round(so.da_tieu * 100),
        },
        khong_nhin_duoc=[
            "model hay bỏ sót lỗi cần hiểu nghiệp vụ nhiều tệp (xem thước đo recall)",
            "lỗi chỉ lộ khi chạy thật (tranh chấp, dữ liệu lớn) — cần bài test/giả lập",
            "tệp chưa đọc: ngoài phạm vi chọn hoặc bị bộ lọc cấm",
        ],
    )
    chay(None, None, a.docker, None, giu, [do])
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Tầng model của agent soát")
    sp = ap.add_subparsers(dest="lenh", required=True)
    k = sp.add_parser("kiem-tra")
    k.add_argument("--model", required=True)
    t = sp.add_parser("thuoc-do")
    t.add_argument("--models", required=True)
    t.add_argument("--tran", type=float, default=6.0, help="trần USD cả lượt đo")
    t.add_argument("--song-song", type=int, default=4)
    q = sp.add_parser("soat")
    q.add_argument("--models", required=True, help="model đọc, cách nhau dấu phẩy")
    q.add_argument("--xac-nhan", required=True, help="model bác bỏ (mạnh hơn)")
    q.add_argument("--tran", type=float, default=4.0)
    q.add_argument("--tien-to", help="chỉ đọc tệp bắt đầu bằng các tiền tố này")
    q.add_argument("--toi-da-tep", type=int, default=0)
    q.add_argument("--toi-da-nhom", type=int, default=120)
    q.add_argument("--song-song", type=int, default=4)
    q.add_argument("--thu-muc", help="thư mục đợt cũ để chạy tiếp (bỏ qua tệp đã đọc)")
    q.add_argument("--docker", help="kèm bất biến dữ liệu trong container DB local")
    a = ap.parse_args(argv)
    try:
        return {"kiem-tra": kiem_tra, "thuoc-do": do_thuoc, "soat": soat}[a.lenh](a)
    except TuChoiError as e:
        print(f"Từ chối: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
