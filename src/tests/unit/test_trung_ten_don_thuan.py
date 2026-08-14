"""Trùng TÊN đơn thuần phải được nhắc — tách khỏi luật khớp mạnh.

Tuyền 14/08/2026: gõ tên đã có trong hệ thống mà không có cảnh báo nào.

VÌ SAO KHÔNG CÓ. `MPIService.find_candidates` đòi tên VÀ năm sinh khớp cùng
lúc (xem mpi_service.py). "Lương Thị Như" sinh 1990 gõ vào khi hệ thống đã có
"Lương Thị Như" sinh 2026 thì không nhánh nào bắt.

VÌ SAO TÁCH RIÊNG, KHÔNG GỘP VÀO `matches`. Danh sách ấy phải khớp ĐÚNG những
gì đường LƯU coi là trùng — đó là toàn bộ lý do endpoint check-duplicate tồn
tại (bản cũ dùng một truy vấn riêng, và hai luật lệch nhau khiến Lễ tân được
báo "không trùng" rồi hồ sơ rơi vào hàng chờ gộp). Nhét tín hiệu yếu vào đó là
dựng lại chính cái lệch ấy.
"""

from __future__ import annotations

import inspect


def test_trung_ten_tra_ve_o_truong_rieng() -> None:
    from clinicai.api.v1 import patients

    src = inspect.getsource(patients.check_duplicate)
    assert '"trung_ten"' in src, "endpoint phải trả về danh sách trùng tên riêng"
    assert "full_name_unaccent" in src, (
        "so tên phải dùng cột GENERATED `full_name_unaccent` — tự gọi unaccent() "
        "ở vế trái sẽ bỏ qua chỉ mục và mở đường cho hai công thức chuẩn hoá "
        "lệch nhau"
    )


def test_khong_lap_lai_ho_so_da_co_trong_matches() -> None:
    """Một hồ sơ khớp mạnh KHÔNG được hiện lại ở khối tín hiệu yếu.

    Hiện hai lần cùng một người ở hai khối khác nhau thì người trực phải tự đối
    chiếu mã bệnh nhân để biết đó là một hay hai hồ sơ — đúng việc mà màn hình
    sinh ra để làm hộ.
    """
    from clinicai.api.v1 import patients

    src = inspect.getsource(patients.check_duplicate)
    assert "da_co = {p.patient_code for p in found}" in src
    assert 'if r["patient_code"] not in da_co' in src


def test_luat_khop_manh_khong_bi_dong_vao() -> None:
    """`matches` vẫn phải là ĐÚNG kết quả của MPIService.find_candidates.

    Đây là chốt giữ lời hứa "cùng một luật với lúc lưu". Thêm điều kiện vào đó
    thì màn hình cảnh báo nhiều hơn đường lưu — và người trực học cách bỏ qua.
    """
    from clinicai.api.v1 import patients

    src = inspect.getsource(patients.check_duplicate)
    assert "found = await MPIService.find_candidates(" in src
    dau = src.index("return {")
    assert '"matches": [' in src[dau:]
    khoi = src[src.index('"matches": [', dau) : src.index('"exists"', dau) + 4000]
    assert "trung_ten" not in khoi.split('"matches"')[1][:400], (
        "trung_ten không được trộn vào matches"
    )
