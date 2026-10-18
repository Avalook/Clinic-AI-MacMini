"""Chạy BỘ BẤT BIẾN DỮ LIỆU và đổi kết quả thành phát hiện.

Ba đường vào, KHÔNG đường nào đi tới máy chủ thật:

* `--docker TÊN`  chạy tệp SQL chỉ-đọc trong container Postgres LOCAL (tên phải
  bắt đầu bằng `clinicai_thu`, `chung_test` hay `ci_may`). Không dùng mạng.
* `--nap TỆP`     nạp kết quả (mỗi dòng một JSON) do NGƯỜI có quyền chạy tệp SQL
  trên máy chủ rồi đưa về. Prod/staging chỉ vào được theo đường này.
* `--in-sql`      in tệp SQL ra để người chạy (xem `bat_bien.tao_tep_sql`).

Kết quả luôn gắn nhãn NGUỒN DỮ LIỆU: số liệu từ DB local là dữ liệu DEMO, không
đại diện cho prod.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .bat_bien import BAT_BIEN, BatBien, tao_tep_sql
from .khuon import DoPhu, MucBangChung, PhatHien, TrichDan
from .nguon import Nguon

TEN = "bat_bien_du_lieu"
TIEN_TO_CONTAINER_CHO_PHEP = ("clinicai_thu", "chung_test", "ci_may")
TEP_BAT_BIEN = "scripts/soat_he_thong/bat_bien.py"


def kiem_container(ten: str) -> None:
    if not ten.startswith(TIEN_TO_CONTAINER_CHO_PHEP):
        raise SystemExit(
            f"Từ chối: container `{ten}` không phải DB local "
            f"({', '.join(TIEN_TO_CONTAINER_CHO_PHEP)}…). "
            "Prod/staging chỉ nạp bằng --nap."
        )


def phan_tich_dau_ra(txt: str) -> list[dict[str, object]]:
    ra: list[dict[str, object]] = []
    for dong in txt.splitlines():
        dong = dong.strip()
        if not dong.startswith("{"):
            continue
        try:
            d = json.loads(dong)
        except json.JSONDecodeError:
            continue
        if isinstance(d, dict) and "ma" in d and "so_dong" in d:
            ra.append(d)
    return ra


def chay_qua_docker(ten: str, csdl: str = "postgres", nguoi: str = "postgres") -> str:
    kiem_container(ten)
    kq = subprocess.run(  # noqa: S603 — danh sách đối số, không shell
        ["docker", "exec", "-i", ten, "psql", "-U", nguoi, "-d", csdl]
        + ["-X", "-q", "-t", "-A"],
        input=tao_tep_sql(),
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    if kq.returncode != 0 and not kq.stdout:
        raise SystemExit(f"psql lỗi (mã {kq.returncode}): {kq.stderr[:300]}")
    return kq.stdout


def _dong_trong_bat_bien(nguon: Nguon, ma: str) -> tuple[int, str]:
    tep = nguon.goc / TEP_BAT_BIEN
    for i, d in enumerate(nguon.doc(tep).splitlines(), 1):
        if f'"{ma}"' in d:
            return i, d.strip()
    return 1, ""


def thanh_phat_hien(
    nguon: Nguon, ket_qua: list[dict[str, object]], nguon_du_lieu: str
) -> tuple[list[PhatHien], DoPhu]:
    theo_ma = {str(k["ma"]): k for k in ket_qua}
    ra: list[PhatHien] = []
    do = DoPhu(TEN)
    n_ok = n_vi_pham = 0
    for b in BAT_BIEN:
        k = theo_ma.get(b.ma)
        if k is None:
            do.khong_nhin_duoc.append(f"{b.ma} không có kết quả (lỗi/hết giờ khi chạy)")
            continue
        so = int(str(k["so_dong"]))
        if so == 0:
            n_ok += 1
            continue
        n_vi_pham += 1
        ra.append(_phat_hien(nguon, b, so, k.get("mau"), nguon_du_lieu))
    do.da_nhin = {
        "bất biến đã chạy": len(theo_ma),
        "đúng (0 dòng vi phạm)": n_ok,
        "có vi phạm": n_vi_pham,
    }
    do.ghi_chu.append(f"Nguồn dữ liệu: {nguon_du_lieu}")
    do.khong_nhin_duoc += [
        "chỉ kiểm điều SQL diễn đạt được; bất biến cần logic nghiệp vụ phức tạp "
        "(đối soát tiền theo kỳ) chưa có",
        "dữ liệu ngoài database: tệp ảnh/PDF trên ổ Viettel, log máy chủ",
    ]
    return ra, do


def _phat_hien(
    nguon: Nguon, b: BatBien, so: int, mau: object, nguon_du_lieu: str
) -> PhatHien:
    dong, doan = _dong_trong_bat_bien(nguon, b.ma)
    la_demo = "local" in nguon_du_lieu.lower() or "docker" in nguon_du_lieu.lower()
    gat = " (DỮ LIỆU DEMO LOCAL — chưa nói gì về prod)" if la_demo else ""
    mau_txt = json.dumps(mau, ensure_ascii=False)[:400]
    return PhatHien(
        bo_quet=TEN,
        khoa=b.ma,
        loai=b.loai,
        uu_tien=b.uu_tien,
        muc_bang_chung=MucBangChung.SUY_RA if b.suy_ra else MucBangChung.QUAN_SAT,
        do_chac=0.6 if b.suy_ra else 0.85,
        tinh_huong=f"{b.ten}: {so} dòng vi phạm{gat}. {b.vi_sao}",
        bang_chung=[
            f"nguồn dữ liệu: {nguon_du_lieu}",
            f"{so} dòng; mẫu (chỉ mã/số, không dữ liệu cá nhân): {mau_txt}",
            f"định nghĩa bất biến: {TEP_BAT_BIEN}:{dong}",
        ],
        rui_ro=b.rui_ro,
        de_xuat=b.de_xuat,
        nguoi_chiu_trach_nhiem="Người phụ trách mảng liên quan; Tuyền kiểm dữ liệu",
        thoi_diem="Trước khi tin báo cáo của mảng này",
        ket_qua_mong_doi="Bất biến trả 0 dòng, hoặc ngoại lệ được giải thích",
        cach_xac_nhan=f"Chạy lại bộ bất biến: {b.ma} về 0 dòng",
        trich_dan=[TrichDan(TEP_BAT_BIEN, dong, doan)],
        muc_viec=b.muc_viec,
        can_du_lieu_that=True,
    )


def doc_tep_nap(duong: Path) -> list[dict[str, object]]:
    return phan_tich_dau_ra(duong.read_text(encoding="utf8"))
