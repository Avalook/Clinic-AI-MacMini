"""Bảy phiếu khám (form profile) chạy trên Form Template Engine.

    NT · HMVS · PK · SK · NK · THU_THUAT · SAN_CHAU

Mỗi phiếu là DỮ LIỆU (`dinh_nghia/<form_id>.json`), trích bằng máy từ tài liệu
đã chốt `ClinicAI-7-phieu-v5-final-review.html` — xem
`scripts/phieu-kham/trich-tu-html.py`. Không phiếu nào được viết bằng TSX.

Gói này KHÔNG có engine thứ hai: khung dùng hình `form_definition` của Form
Template Engine. Chỗ LƯU một lần điền phiếu khám thì chưa có — phiếu khám gắn
vào consultation/visit, còn `form_instance` hiện chỉ gắn được `service_order`
(INTEGRATION_BLOCKER, xem `docs/phieu-kham/TICH-HOP.md`).

    khung.py            nạp khung, kiểm khung, kiểm dữ liệu theo KHOÁ ỔN ĐỊNH
    che_do.py           editable / finalized_locked / amendment_mode — nhận
                        từ clinical shell, không tự quyết
    mang_sang.py        dải hành chính + sinh hiệu + ghi chú bác sĩ tư vấn
    ket_qua_chi_dinh.py kết quả CLS gắn theo `service_order_id`, không theo tên
    nap.py              nạp bảy khung v1 vào `form_definition` (hiện chỉ test)
"""
