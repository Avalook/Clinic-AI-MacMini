"""`scripts/day-log-len-viettel.sh` — đẩy log lên Viettel CFS không hở, không trùng.

VÌ SAO (19/11/2026): journal VPS chỉ giữ ~4 ngày nên truy vụ chuyển kho bị mất
log trước 15/11. Script dựa vào `journalctl --cursor-file`; điều phải giữ: mốc chỉ
được đẩy lên SAU khi tệp đã nằm trên Viettel và mã băm khớp.

Chạy script thật bằng bash, thay `journalctl` / `mountpoint` / `findmnt` bằng bản
giả: journalctl giả đánh số dòng tăng dần và ghi mốc = số dòng cuối.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

GOC = Path(__file__).resolve().parents[3]
SCRIPT = GOC / "scripts" / "day-log-len-viettel.sh"

pytestmark = pytest.mark.skipif(
    shutil.which("zstd") is None, reason="máy chạy test không có zstd"
)

JOURNALCTL_GIA = r"""#!/usr/bin/env bash
# journalctl giả: --cursor-file=F; mốc là số dòng cuối đã xuất.
for a in "$@"; do
  case "$a" in --cursor-file=*) F="${a#--cursor-file=}";; esac
done
dau=0; [ -f "$F" ] && dau=$(cat "$F")
tong=$(cat "$NGUON_TONG")
[ -n "${JOURNAL_GOI_Y:-}" ] \
  && echo "Hint: You are currently not seeing messages from other users." >&2
i=$dau
while [ "$i" -lt "$tong" ]; do i=$((i+1)); echo "{\"MESSAGE\":\"dong $i\"}"; done
echo "$i" > "$F"
"""


def _tao_bin(thu_muc: Path, ten: str, noi_dung: str) -> Path:
    p = thu_muc / ten
    p.write_text(noi_dung)
    p.chmod(p.stat().st_mode | stat.S_IEXEC)
    return p


@pytest.fixture
def moi_truong(tmp_path: Path) -> dict[str, object]:
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    cfs = tmp_path / "cfs"
    cfs.mkdir()
    tong = tmp_path / "tong"
    tong.write_text("3")
    env = {
        **os.environ,
        "VIETTEL_CFS_DIR": str(cfs),
        "LOG_VIETTEL_STATE_DIR": str(tmp_path / "trang-thai"),
        "JOURNALCTL_BIN": str(_tao_bin(bin_, "journalctl", JOURNALCTL_GIA)),
        "MOUNTPOINT_BIN": str(_tao_bin(bin_, "mountpoint", "#!/bin/sh\nexit 0\n")),
        "FINDMNT_BIN": str(
            _tao_bin(bin_, "findmnt", "#!/bin/sh\necho rw,vers=3.1.1,seal\n")
        ),
        "NGUON_TONG": str(tong),
    }
    return {"env": env, "cfs": cfs, "tong": tong, "bin": bin_, "tmp": tmp_path}


def _chay(m: dict[str, object], **them: str) -> subprocess.CompletedProcess[str]:
    env = {**m["env"], **them}  # type: ignore[dict-item]
    return subprocess.run(
        ["bash", str(SCRIPT)], env=env, capture_output=True, text=True, check=False
    )


def _dong_da_luu(cfs: Path) -> list[str]:
    ra: list[str] = []
    for tep in sorted((cfs / "logs").rglob("*.json.zst")):
        ra += subprocess.run(
            ["zstd", "-q", "-dc", str(tep)], capture_output=True, text=True, check=True
        ).stdout.splitlines()
    return ra


def test_hai_lan_chay_khong_trung_khong_ho(moi_truong: dict[str, object]) -> None:
    m = moi_truong
    assert _chay(m).returncode == 0
    m["tong"].write_text("5")  # type: ignore[attr-defined]
    assert _chay(m).returncode == 0
    dong = _dong_da_luu(m["cfs"])  # type: ignore[arg-type]
    assert dong == [f'{{"MESSAGE":"dong {i}"}}' for i in range(1, 6)]


def test_khong_co_dong_moi_thi_khong_tao_tep(moi_truong: dict[str, object]) -> None:
    m = moi_truong
    assert _chay(m).returncode == 0
    r = _chay(m)
    assert r.returncode == 0 and "Không có dòng log mới" in r.stdout
    assert len(list((m["cfs"] / "logs").rglob("*.json.zst"))) == 1  # type: ignore[operator]


def test_o_khong_mount_thi_dung_va_khong_ghi(moi_truong: dict[str, object]) -> None:
    m = moi_truong
    khong = _tao_bin(m["bin"], "mountpoint-hong", "#!/bin/sh\nexit 1\n")  # type: ignore[arg-type]
    r = _chay(m, MOUNTPOINT_BIN=str(khong))
    assert r.returncode != 0 and "KHÔNG được mount" in r.stderr
    assert not (m["cfs"] / "logs").exists()  # type: ignore[operator]


def test_mount_thieu_seal_thi_dung(moi_truong: dict[str, object]) -> None:
    m = moi_truong
    tran = _tao_bin(m["bin"], "findmnt-tran", "#!/bin/sh\necho rw,vers=3.1.1\n")  # type: ignore[arg-type]
    r = _chay(m, FINDMNT_BIN=str(tran))
    assert r.returncode != 0 and "seal" in r.stderr


def test_chep_hong_thi_moc_dung_yen_lan_sau_xuat_bu(
    moi_truong: dict[str, object],
) -> None:
    m = moi_truong
    cfs: Path = m["cfs"]  # type: ignore[assignment]
    assert _chay(m).returncode == 0  # dòng 1–3
    m["tong"].write_text("6")  # type: ignore[attr-defined]
    cay = [cfs, *[p for p in cfs.rglob("*") if p.is_dir()]]
    for p in cay:  # Viettel "rớt": cả cây thư mục không ghi được
        p.chmod(0o500)
    try:
        assert _chay(m).returncode != 0
    finally:
        for p in cay:
            p.chmod(0o700)
    assert _chay(m).returncode == 0  # chạy lại: phải có đủ 4–6
    dong = _dong_da_luu(cfs)
    assert dong == [f'{{"MESSAGE":"dong {i}"}}' for i in range(1, 7)]


def test_khong_doc_duoc_toan_bo_journal_thi_bao_loi(
    moi_truong: dict[str, object],
) -> None:
    r = _chay(moi_truong, JOURNAL_GOI_Y="1")
    assert r.returncode != 0 and "systemd-journal" in r.stderr
    assert not (moi_truong["cfs"] / "logs").exists()  # type: ignore[operator]


def test_don_ngay_cu_hon_han(moi_truong: dict[str, object]) -> None:
    m = moi_truong
    cu = m["cfs"] / "logs" / "2020" / "01" / "02"  # type: ignore[operator]
    cu.mkdir(parents=True)
    (cu / "20200102-010700.json.zst").write_bytes(b"x")
    assert _chay(m).returncode == 0
    assert not (m["cfs"] / "logs" / "2020").exists()  # type: ignore[operator]
