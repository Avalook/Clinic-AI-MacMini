# ADR-0014 — Dịch vụ khám con là tuỳ chọn, nguồn thu theo cấu hình

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-09-30 |
| **Liên quan** | ADR-0003 (bất biến đồng thời), V2 `CODEX-VIEC-3009.md` |

## Context

Hoá đơn cũ bắt buộc phải tick một dòng `loai_kham_phi`. Loại khám không có dòng
con, hoặc Sàn chậu / Thủ thuật rẽ về bác sĩ chính, vì thế bị kẹt ở quầy. Dòng
tiền khám cũng dùng duy nhất `exam-{visit_id}`, nên chốt chống thu trùng không
thể phân biệt phí mặc định đã thu với dịch vụ con được chọn sau đó.

## Decision

1. `service_type.gia_mac_dinh` là giá nguyên VND khi chưa chọn dịch vụ khám
   con; mặc định `0`, trong khoảng 0–1 tỷ, quản lý sửa ở màn Cấu trúc phòng
   khám và mọi lần sửa vào `event_log` cùng transaction.
2. Chưa chọn chỉ sinh `HoaDon.canh_bao`, không sinh `van_de`. Checkout hỏi hoá
   đơn còn nợ, không hỏi đã từng có phiếu `PAID`; vì vậy hoá đơn 0đ được đóng.
3. Ảnh chụp thu giữ nguồn mặc định `exam-{visit}`. Mỗi dịch vụ con dùng nguồn
   `exam-{visit}-selected-<service_price_id>`. Đã thu A rồi tick thêm B thì
   chỉ B còn nợ. Ảnh chụp gộp trước V2 được nhận diện bằng đúng tên và tổng để
   không thu lại lịch sử; trường hợp không khớp vẫn đi đối soát.
4. Chỉ ẩn / từ chối checkbox khi lượt thực sự có `route_decision=SERVICES`.
   Cờ loại khám `di_thang_phong` không đủ để kết luận nếu lượt đã rẽ `PRIMARY`.
5. Checkout khoá dòng `visit`, giữ ổn định dòng `service_type`, rồi dựng lại
   công nợ trong cùng transaction. Checkbox phí khám dùng cùng khoá và không
   cho đổi sau `closed_at`, loại bỏ cửa sổ đổi phí trong lúc đang đóng lượt.

## Consequences

- Lịch sử thu cũ bất biến và chốt chống thu trùng vẫn có hiệu lực.
- Tick sau khi đã thu không sửa phiếu cũ; nó tạo khoản còn nợ mới.
- Danh sách checkout phải dựng hoá đơn còn nợ cho từng lượt để dùng cùng một
  nguồn sự thật với quầy thu; đây là thêm truy vấn nhưng tránh kết luận sai từ
  một cờ “đã từng thu”.
