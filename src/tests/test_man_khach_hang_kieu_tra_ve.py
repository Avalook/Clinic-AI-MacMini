"""Khối `tuan_cong_bo` là danh sách CHUỖI — chú thích kiểu phải chịu được nó.

Bài này tồn tại vì một lỗi ngủ đông đã nổ trên bản chạy thật ngày 16/09/2026.

`/cskh/man-khach-hang` khai kiểu trả về `dict[str, list[dict[str, object]]]`,
và FastAPI KIỂM kiểu ấy trước khi trả lời. Nhưng một trong mười một khối —
`tuan_cong_bo` — là danh sách mã tuần, tức danh sách chuỗi.

Lỗi ngủ suốt nhiều tháng vì khi CHƯA tuần lịch trực nào được công bố thì danh
sách rỗng, và danh sách rỗng hợp lệ với mọi kiểu phần tử. Đúng hôm dựng lịch
trực thật, cả màn Quản lý khách hàng trả 500 cho MỌI vai, và trên màn chỉ hiện
một câu "Không đọc được dữ liệu chăm sóc — backend không trả lời". Không ai
đoán được thủ phạm là một chú thích kiểu.

Nên bài này dựng một phản hồi CÓ tuần công bố — trạng thái mà bài kiểm cũ
không bao giờ chạm tới.
"""

from __future__ import annotations

from typing import Any, get_args, get_origin, get_type_hints


def test_kieu_tra_ve_chiu_duoc_khoi_danh_sach_chuoi() -> None:
    from clinicai.api.v1.routers.cskh import man_khach_hang

    kieu = get_type_hints(man_khach_hang)["return"]
    assert get_origin(kieu) is dict, kieu
    _, gia_tri = get_args(kieu)
    assert get_origin(gia_tri) is list, gia_tri
    (phan_tu,) = get_args(gia_tri)
    assert phan_tu is Any, (
        "Phần tử của mỗi khối phải là `Any`. Khai hẹp hơn (ví dụ "
        "`dict[str, object]`) là FastAPI ném 500 ngay khi khối `tuan_cong_bo` "
        "có dữ liệu — xem chú thích đầu tệp."
    )


def test_phan_hoi_that_qua_duoc_cua_kiem_kieu() -> None:
    """Dựng đúng hình dạng service trả về, CÓ tuần công bố, rồi ép kiểm kiểu."""
    from pydantic import TypeAdapter

    from clinicai.api.v1.routers.cskh import man_khach_hang

    kieu = get_type_hints(man_khach_hang)["return"]
    phan_hoi: dict[str, list[Any]] = {
        "appts": [{"id": "a1"}],
        "ca_truc": [{"staff_id": "s1"}],
        # ĐÂY là khối làm nổ bản chạy thật.
        "tuan_cong_bo": ["2026-09-14", "2026-09-21"],
        "trang_thai": [],
        "viec_mo": [],
        "tep": [],
        "phan_hoi": [],
        "hen_goi_lai": [],
        "tuong_tac": [],
        "cskh": [],
        "visits": [],
    }
    # Không gọi qua HTTP: FastAPI dựng bộ kiểm từ CHÍNH chú thích này, nên kiểm
    # thẳng chú thích là kiểm đúng thứ đã ném 500 — và không cần cả một ứng dụng.
    TypeAdapter(kieu).validate_python(phan_hoi)
