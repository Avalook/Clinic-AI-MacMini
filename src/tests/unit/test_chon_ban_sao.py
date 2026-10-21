"""Chọn 'bản sao lưu mới nhất' phải ra TỆP CHÍNH, không ra tệp đi kèm.

VÌ SAO CÓ BÀI NÀY (bản đồ code đọc kỹ 21/10/2026). Mỗi lần `backup-db.sh` chạy
ghi ba tệp cùng mốc giờ: `X.sql.gz` (chính), `X_auth.sql.gz`, rồi SAU CÙNG
`X_lich_su_notion.sql.gz`. Năm script chọn "bản mới nhất" chỉ loại `_auth` → chọn
nhầm tệp notion: đẩy Viettel dừng vì "thiếu tệp auth đi kèm" (systemd `ExecStart=-`
nuốt lỗi), kiểm bản sao / diễn tập khôi phục đọc nhầm tệp. Giờ một hàm chung
`scripts/lib/chon-ban-sao.sh`.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

GOC = Path(__file__).resolve().parents[3]
LIB = GOC / "scripts" / "lib" / "chon-ban-sao.sh"
DUNG_HAM = [
    "scripts/day-sao-luu-len-viettel-storage.sh",
    "scripts/day-sao-luu-len-viettel.sh",
    "scripts/verify-backup.sh",
    "scripts/restore-drill.sh",
    "scripts/staging-tu-ban-sao.sh",
]


def _chon(thu_muc: Path, tien_to: str = "clinicai_") -> str:
    r = subprocess.run(
        [
            "bash",
            "-c",
            f'. "{LIB}"; chon_ban_chinh_moi_nhat "$1" "$2"',
            "_",
            str(thu_muc),
            tien_to,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return r.stdout.strip()


def _dem(thu_muc: Path, ten: str, giay: int) -> None:
    p = thu_muc / ten
    p.write_bytes(b"x")
    os.utime(p, (giay, giay))


def test_ra_tep_chinh_khi_tep_notion_ghi_sau_cung(tmp_path: Path) -> None:
    cu = "clinicai_production_clinicai-db_20261020_021539"
    moi = "clinicai_production_clinicai-db_20261021_021539"
    for i, ten in enumerate(
        [
            f"{cu}.sql.gz",
            f"{cu}_auth.sql.gz",
            f"{cu}_lich_su_notion.sql.gz",
            f"{moi}.sql.gz",
            f"{moi}_auth.sql.gz",
            f"{moi}_lich_su_notion.sql.gz",
        ]
    ):
        _dem(tmp_path, ten, 1_000_000 + i * 60)
    assert Path(_chon(tmp_path)).name == f"{moi}.sql.gz"
    assert Path(_chon(tmp_path, "clinicai_production_")).name == f"{moi}.sql.gz"


def test_thu_muc_rong_thi_ra_rong(tmp_path: Path) -> None:
    assert _chon(tmp_path) == ""


def test_moi_script_chon_ban_sao_dung_ham_chung() -> None:
    for s in DUNG_HAM:
        noi_dung = (GOC / s).read_text(encoding="utf-8")
        assert "chon_ban_chinh_moi_nhat" in noi_dung, f"{s} còn tự chọn bản mới nhất"
