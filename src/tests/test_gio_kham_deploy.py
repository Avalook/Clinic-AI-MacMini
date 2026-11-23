"""Giờ phòng khám dùng hệ thống — khoá deploy theo giờ khám (24/11/2026).

`scripts/lib/gio-kham.sh` là MỘT chỗ trả lời "đang giờ khám không" cho cả deploy
prod (`deploy-backend.sh`, test hành vi ở `scripts/tests/test-infra-safety.sh`) và
staging chung máy (`kiem_gio_kham` trong `scripts/lib/staging-chung.sh`).
Khung (Tuyền 11/11): thứ 2–6 [16h, 23h), thứ 7–CN [7h, 23h), giờ Việt Nam.

Giả giờ bằng `date` giả đứng đầu PATH — script trên VPS không có biến nào giả được
giờ hay đổi khung (một biến như thế là lối tắt bỏ qua khoá không để lại lý do).
"""

from __future__ import annotations

import os
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

REPO = Path(__file__).resolve().parents[2]
LIB = REPO / "scripts" / "lib" / "staging-chung.sh"


def _date_gia_utc(tmp_path: Path, thu_utc: int, gio_utc: int) -> str:
    """PATH có `date` giả: `date -u '+%u %H'` trả (thứ, giờ) UTC đã cho."""
    bin_ = tmp_path / "dong-ho"
    bin_.mkdir(exist_ok=True)
    (bin_ / "date").write_text(
        "#!/bin/sh\n"
        f'if [ "$*" = "-u +%u %H" ]; then echo "{thu_utc} {gio_utc:02d}"; exit 0; fi\n'
        'exec /bin/date "$@"\n'
    )
    (bin_ / "date").chmod(0o755)
    return f"{bin_}:{os.environ.get('PATH', '')}"


def _dong_ho_gia(tmp_path: Path, thu_vn: int, gio_vn: int) -> str:
    """Như `_date_gia_utc` nhưng nhận lúc theo giờ VN (UTC = VN − 7h).

    thu_vn: 1 = thứ 2 … 7 = Chủ nhật.
    """
    gio_utc, thu_utc = gio_vn - 7, thu_vn
    if gio_utc < 0:
        gio_utc += 24
        thu_utc = (thu_vn - 2) % 7 + 1
    return _date_gia_utc(tmp_path, thu_utc, gio_utc)


def _goi(ham: str, them: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "-c", f'. "{LIB}"; {ham}'],
        capture_output=True,
        text=True,
        env={**os.environ, **them},
    )


@pytest.mark.parametrize(
    ("thu", "gio"), [(1, 16), (3, 20), (5, 22), (6, 7), (6, 12), (7, 7), (7, 22)]
)
def test_staging_trong_gio_kham_khong_co_bien_cho_phep_thi_dung(
    tmp_path: Path, thu: int, gio: int
) -> None:
    r = _goi(
        "kiem_gio_kham && echo QUA",
        {"PATH": _dong_ho_gia(tmp_path, thu, gio), "CHO_PHEP_GIO_KHAM": ""},
    )
    assert r.returncode != 0
    assert "QUA" not in r.stdout
    assert "GIỜ KHÁM" in r.stderr
    # Câu thông báo phải nói được cách đi tiếp, không chỉ "cấm".
    assert "CHO_PHEP_GIO_KHAM=1" in r.stderr


@pytest.mark.parametrize(("thu", "gio"), [(2, 16), (4, 22), (7, 12)])
def test_staging_co_bien_cho_phep_thi_di_tiep_kem_canh_bao(
    tmp_path: Path, thu: int, gio: int
) -> None:
    r = _goi(
        "kiem_gio_kham && echo QUA",
        {"PATH": _dong_ho_gia(tmp_path, thu, gio), "CHO_PHEP_GIO_KHAM": "1"},
    )
    assert r.returncode == 0, r.stderr
    assert "QUA" in r.stdout
    assert "GIỜ KHÁM" in r.stderr


# Ngày thường buổi sáng/chiều (trước 16h) là lúc deploy được; mọi ngày từ 23h.
@pytest.mark.parametrize(
    ("thu", "gio"), [(1, 7), (3, 12), (5, 15), (2, 23), (6, 6), (7, 23), (4, 0), (1, 0)]
)
def test_ngoai_gio_kham_khong_doi_hanh_vi(tmp_path: Path, thu: int, gio: int) -> None:
    r = _goi(
        "kiem_gio_kham && echo QUA",
        {"PATH": _dong_ho_gia(tmp_path, thu, gio), "CHO_PHEP_GIO_KHAM": ""},
    )
    assert r.returncode == 0, r.stderr
    assert "QUA" in r.stdout
    assert r.stderr == ""


def test_staging_kieu_rieng_khong_xet_gio_kham(tmp_path: Path) -> None:
    r = _goi(
        "kiem_gio_kham && echo QUA",
        {"STAGING_KIEU": "rieng", "PATH": _dong_ho_gia(tmp_path, 6, 12)},
    )
    assert r.returncode == 0, r.stderr
    assert r.stderr == ""


# Mốc đổi ngày: 17:00 UTC là 0h VN hôm sau. Ca 20/11 (thứ 6, 16:23 VN =
# 09:23 UTC) là đúng ca deploy prod giữa giờ khám đã xảy ra.
@pytest.mark.parametrize(
    ("thu_utc", "gio_utc", "mong"),
    [
        (7, 16, "7 23"),  # CN 16h UTC = CN 23h VN
        (7, 17, "1 0"),  # CN 17h UTC = 0h thứ 2 VN
        (5, 23, "6 6"),  # thứ 6 23h UTC = 6h thứ 7 VN
        (5, 9, "5 16"),  # 20/11: thứ 6 16h VN
        (1, 0, "1 7"),
    ],
)
def test_thu_gio_vn_doi_tu_utc(
    tmp_path: Path, thu_utc: int, gio_utc: int, mong: str
) -> None:
    r = _goi("thu_gio_vn", {"PATH": _date_gia_utc(tmp_path, thu_utc, gio_utc)})
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == mong


def test_thu_gio_vn_khop_mui_gio_asia_ho_chi_minh() -> None:
    # Không giả: phải khớp đồng hồ Asia/Ho_Chi_Minh thật (tzdata của Python).
    # Đo trước và sau để không chập chờn khi lệnh chạy đúng lúc qua giờ.
    def bay_gio() -> str:
        t = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))
        return f"{t.isoweekday()} {t.hour}"

    truoc = bay_gio()
    r = _goi("thu_gio_vn", {})
    sau = bay_gio()
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() in {truoc, sau}


def test_khung_gio_kham_khong_doi_duoc_bang_bien_moi_truong(tmp_path: Path) -> None:
    # Biến khung cũ (GIO_KHAM_TU/…_DEN) không còn tác dụng: khung là luật,
    # đổi bằng PR. Thứ 6 17h VN vẫn là giờ khám dù đặt khung "rỗng".
    r = _goi(
        "kiem_gio_kham && echo QUA",
        {
            "PATH": _dong_ho_gia(tmp_path, 5, 17),
            "GIO_KHAM_TU": "23",
            "GIO_KHAM_TU_NGAY_THUONG": "23",
            "GIO_KHAM_DEN": "0",
            "CHO_PHEP_GIO_KHAM": "",
        },
    )
    assert r.returncode != 0
    assert "GIỜ KHÁM" in r.stderr


def test_deploy_staging_goi_kiem_gio_kham_sau_kiem_tai_nguyen() -> None:
    sh = (REPO / "scripts" / "deploy-staging.sh").read_text(encoding="utf-8")
    assert sh.index("kiem_tai_nguyen\n") < sh.index("kiem_gio_kham\n")
    # Phải đứng TRƯỚC bước tắt staging / dựng ảnh.
    assert sh.index("kiem_gio_kham\n") < sh.index("docker stop")
