#!/usr/bin/env python3
"""Chép kho pgBackRest (ổ VPS) sang Viettel CFS — bản sao NGOÀI MÁY.

    sudo python3 -I scripts/may-chu/chep-kho-sao-luu.py [NGUON] [DICH]

Mặc định NGUON=/home/clinicai/pgbackrest/repo, DICH=/mnt/viettel-cfs/pgbackrest/repo.
Chạy bằng timer `clinicai-pgbackrest-chep` mỗi giờ, quyền root (tệp kho thuộc
uid 999 của postgres trong container).

VÌ SAO KHÔNG ĐỂ pgBackRest GHI THẲNG CFS: với hai kho, `archive-push` báo lỗi
cho Postgres khi chỉ một kho hỏng → WAL dồn trên ổ VPS mỗi lần CFS chập chờn.
Chép bằng tay thì CFS chậm chỉ làm chậm bản sao ngoài máy, không đụng DB.

Kết quả là ẢNH GƯƠNG của kho: tệp mới/đổi thì chép (ghi ra `.dang-chep` rồi đổi
tên — CFS rớt giữa chừng không để lại tệp cụt mang tên thật), tệp kho đã dọn
(bản cũ hết hạn giữ) thì xoá bên CFS. Kho trên CFS vì thế khôi phục được y như
kho gốc: gắn nó vào `/var/lib/pgbackrest` rồi `pgbackrest restore`.

Tệp kho pgBackRest gần như bất biến (WAL, tệp bản sao lưu); chỉ `*.info` và
`*.info.copy` ghi lại — so cỡ + thời điểm sửa là đủ.
"""

from __future__ import annotations

import os
import shutil
import sys
import time

NGUON = sys.argv[1] if len(sys.argv) > 1 else "/home/clinicai/pgbackrest/repo"
DICH = sys.argv[2] if len(sys.argv) > 2 else "/mnt/viettel-cfs/pgbackrest/repo"
GOC_CFS = os.environ.get("VIETTEL_CFS_DIR", "/mnt/viettel-cfs")


def can_chep(nguon: str, dich: str) -> bool:
    try:
        d = os.stat(dich)
    except FileNotFoundError:
        return True
    n = os.stat(nguon)
    return n.st_size != d.st_size or int(n.st_mtime) != int(d.st_mtime)


def main() -> int:
    # Chưa gắn ổ thì /mnt/viettel-cfs chỉ là thư mục trên chính ổ VPS: chép vào
    # đó là tự lừa mình có bản ngoài máy, và làm đầy ổ.
    tren_cfs = DICH.startswith(GOC_CFS)
    if tren_cfs and os.path.isdir(GOC_CFS) and not os.path.ismount(GOC_CFS):
        print(f"!! {GOC_CFS} KHÔNG được mount — dừng.", file=sys.stderr)
        return 1
    if not os.path.isdir(NGUON):
        print(f"!! không có kho nguồn {NGUON}", file=sys.stderr)
        return 1

    bat_dau = time.monotonic()
    co: set[str] = set()
    chep = byte = 0
    for goc, _thu_muc, tep in os.walk(NGUON):
        rel = os.path.relpath(goc, NGUON)
        os.makedirs(os.path.join(DICH, rel), exist_ok=True)
        for ten in tep:
            r = os.path.normpath(os.path.join(rel, ten))
            co.add(r)
            n, d = os.path.join(NGUON, r), os.path.join(DICH, r)
            if not can_chep(n, d):
                continue
            tam = d + ".dang-chep"
            shutil.copyfile(n, tam)
            st = os.stat(n)
            os.utime(tam, (st.st_atime, st.st_mtime))
            os.replace(tam, d)
            chep += 1
            byte += st.st_size

    xoa = 0
    for goc, _thu_muc, tep in os.walk(DICH, topdown=False):
        rel = os.path.relpath(goc, DICH)
        for ten in tep:
            r = os.path.normpath(os.path.join(rel, ten))
            if r not in co:
                os.remove(os.path.join(DICH, r))
                xoa += 1
        if rel != "." and not os.listdir(goc):
            os.rmdir(goc)

    print(
        f"chep-kho-sao-luu: {len(co)} tệp trong kho, chép {chep} "
        f"({byte / 1e6:.1f} MB), xoá {xoa}, {time.monotonic() - bat_dau:.0f}s"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
