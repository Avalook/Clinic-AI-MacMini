"""Luật thứ tự gọi không được quay lại trình duyệt.

Trước 06/08/2026 luật này có HAI bản: `src/clinicai/services/queue_order.py` và
một bản chép bằng TypeScript ở `src/dashboard/lib/queue.ts` mà ba màn nhân viên
dùng. Hai bản giống nhau ở thời điểm đó — nhưng không có gì giữ chúng giống
nhau. Sửa cửa sổ "đến đúng giờ" ở một bên là bảng của Lễ tân và bảng của bác sĩ
gọi bệnh nhân theo hai thứ tự khác nhau, im lặng.

Bản TypeScript đã xoá. Bài này canh để nó không mọc lại — và canh bằng cách quét
CHUỖI chứ không cần dựng server hay database, nên nó chạy được ở mọi PR.

Nếu một ngày nào đó thật sự cần xếp lại ở trình duyệt (ví dụ sắp xếp cục bộ theo
cột người dùng bấm), hãy đặt tên khác và ghi rõ vì sao — danh sách dưới đây chỉ
cấm những cái tên mang LUẬT NGHIỆP VỤ.
"""

from __future__ import annotations

import pathlib
import re

DASHBOARD = pathlib.Path(__file__).resolve().parents[1] / "dashboard"

# Tên các hàm/hằng của luật gọi. Có mặt trong .ts/.tsx = luật đã bị chép lại.
CAM = ("compareQueue", "callRank", "queueRank", "LATE_GRACE")

BO_QUA = ("node_modules", ".next", "dist", "build")


def _cac_file_nguon() -> list[pathlib.Path]:
    out = []
    for p in DASHBOARD.rglob("*"):
        if p.suffix not in (".ts", ".tsx"):
            continue
        if any(phan in p.parts for phan in BO_QUA):
            continue
        out.append(p)
    return out


_KHOI_CHU_THICH = re.compile(r"/\*.*?\*/", re.DOTALL)


def _bo_chu_thich(nguon: str) -> list[str]:
    """Giữ nguyên SỐ DÒNG, chỉ xoá phần chú thích.

    Phải xoá cả khối `/* … */` chứ không chỉ `//`: chú thích JSDoc nhiều dòng có
    dạng ` * …`, không mang dấu hiệu nào ở đầu dòng để nhận ra. Bản đầu của bài
    kiểm này chỉ cắt `//` nên nó báo vi phạm ngay trên chú thích GIẢI THÍCH việc
    đã bỏ luật — một bài canh bắt nhầm là một bài canh sẽ bị người ta tắt đi.
    """
    da_bo = _KHOI_CHU_THICH.sub(
        lambda m: "\n" * m.group(0).count("\n"),
        nguon,
    )
    return [dong.split("//")[0] for dong in da_bo.splitlines()]


def test_khong_con_ban_sao_luat_thu_tu_goi_o_trinh_duyet() -> None:
    vi_pham: list[str] = []
    for p in _cac_file_nguon():
        noi_dung = p.read_text(encoding="utf-8", errors="ignore")
        # Chú thích được phép NHẮC tới cái tên (để giải thích lịch sử);
        # cấm là cấm GỌI nó.
        for dong_so, thuc_thi in enumerate(_bo_chu_thich(noi_dung), 1):
            for ten in CAM:
                if ten in thuc_thi:
                    vi_pham.append(f"{p.relative_to(DASHBOARD)}:{dong_so}: {ten}")

    assert not vi_pham, (
        "Luật thứ tự gọi đã quay lại trình duyệt. Nó phải sống DUY NHẤT ở "
        "src/clinicai/services/queue_order.py, và màn hình chỉ đọc `call_order` "
        "mà backend trả về:\n  " + "\n  ".join(vi_pham)
    )


def test_bai_canh_nay_that_su_co_quet_file() -> None:
    """Chống xanh giả: nếu đường dẫn sai thì bài trên luôn xanh vì không quét gì.

    Ngưỡng cố ý đặt thấp và chỉ để bắt trường hợp danh sách RỖNG hoặc gần rỗng —
    không phải để đếm số file của dashboard.
    """
    assert len(_cac_file_nguon()) > 50


def test_bo_chu_thich_van_giu_lai_ma_thuc_thi() -> None:
    """Chống xanh giả kiểu thứ hai: nếu bộ bóc chú thích ăn luôn cả mã, bài canh
    trên sẽ luôn xanh vì chẳng còn gì để soi."""
    mau = "\n".join(
        [
            "/** compareQueue() đã bỏ — chú thích, KHÔNG tính là vi phạm */",
            "const x = compareQueue(a, b); // đây mới là vi phạm",
            "/*",
            " * callRank nhắc trong khối nhiều dòng",
            " */",
            "const y = 1;",
        ]
    )
    dong = _bo_chu_thich(mau)

    assert len(dong) == 6, "số dòng phải giữ nguyên để báo đúng vị trí"
    assert "compareQueue" not in dong[0]
    assert "compareQueue" in dong[1], "mã thực thi không được bị ăn mất"
    assert "callRank" not in dong[3]
    assert "const y = 1;" in dong[5]
