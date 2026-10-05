# Nhập lịch sử khám cũ từ Notion

Viết ngày 05/10/2026, khi phòng khám bỏ Notion. Phòng khám đã dùng Notion từ 04/2025 đến 10/2026.

## Dữ liệu nằm ở đâu

- **Lịch sử** nằm ở schema `lich_su_notion`, chỉ đọc. Các bảng: `nguoi`, `luot_kham`,
  `dich_vu`, `ket_qua`, `xet_nghiem`, `ke_thuoc`, `lich_hen`, `bat_thuong` (sổ bất
  thường) và `lan_nhap`. Migration tạo schema: `20261005100000_lich_su_notion.sql`.
- **Không đổ vào** `visit`, `appointment`, `prescription`. Đó là các bảng đang chạy luồng
  việc (có trigger báo realtime, cấp số, kiểm sức chứa, quầy thuốc lọc đơn "chưa phát",
  khoá chặn xoá cứng). Nếu đổ vào thì sinh việc ma và không gỡ ra được.
- **Khách:**
  - Khách đã có trên hệ thống (khớp 9 số cuối SĐT + họ tên bỏ dấu) thì chỉ gắn lịch sử
    vào hồ sơ đó.
  - Khách chưa có thì tạo hồ sơ mới, gắn `patient.nguon_nhap = 'notion'`, mã hồ sơ =
    mã Notion (`KHACH-n` / `LAMSANG-n`).
- **Thời gian:** chỉ lưu NGÀY khám, vì Notion không có giờ check-in/check-out.
  - Lượt nhập hàng loạt vào Notion ngày 14/11/2025 lấy ngày thật ở dòng đầu ô
    "Khám – Tư vấn".
  - "Lần N" tính trên dữ liệu có từ 04/2025. Cùng một ngày có nhiều lượt thì đánh dấu
    `thu_tu_khong_chac`.
- **Tệp PDF xét nghiệm** chép vào kho CFS tại
  `<clinic_id>/lich-su-notion/xet-nghiem/…` và mở qua `/api/lich-su-notion/tep`.
- **Ảnh/video siêu âm** (~10 TB trên Google Drive): chỉ lưu link thư mục của từng khách.
- **Sao lưu:**
  - Bản 15 phút chỉ lấy `public`, nên không phình.
  - Bản đêm lấy thêm `*_lich_su_notion.sql.gz` (khoảng 10 MB).
  - Gói nhập trên Mac / CFS cũng đủ để dựng lại toàn bộ.

## Dựng gói (trên Mac)

Làm trong thư mục `~/Projects/ClinicAI-Backups/notion-import-20261005/claude/`:

1. `dien_tap.sh`: chuẩn hoá snapshot, định danh người, ghép danh mục, nạp vào bản sao
   prod `notion_dien_tap`.
2. `cap_nhat_than.py`: bổ sung nội dung tờ kết quả siêu âm đã tải thêm.
3. `dong_goi.py <ngày>`: xuất ra `goi/<ngày>/`, gồm các tệp `*.jsonl`, `manifest.json` và
   thư mục `tep/`.

## Nạp (trên VPS, NGOÀI GIỜ ĐÓN KHÁCH, sao lưu trước)

1. Chép gói lên `/home/clinicai/lich-su-notion/goi-<ngày>/`.
2. Thử khô (không ghi gì):
   `./scripts/nhap-lich-su-notion.sh prod /home/clinicai/lich-su-notion/goi-<ngày>`
3. Ghi thật: thêm `--that` vào lệnh trên. Lệnh chạy trong một giao dịch: lỗi giữa chừng
   thì DB quay về như cũ. Tệp chỉ được chép vào kho sau khi giao dịch xong.
4. **Chạy lại an toàn:** người đã nạp giữ nguyên hồ sơ, chỉ thêm phần mới và cập nhật nội
   dung. Dùng cách này cho phần Notion phát sinh sau ảnh chụp, và cho tờ kết quả tải
   thêm.

## Gỡ

Chạy `docker exec -i clinicai_db psql -U postgres -v ON_ERROR_STOP=1 < scripts/hoan-tac-lich-su-notion.sql`.

Script này:
- Xoá sạch lịch sử.
- **Ẩn** các hồ sơ tạo từ Notion chưa có hoạt động nào trên hệ thống.
- **Giữ** các hồ sơ đã có lịch hẹn hoặc lượt khám trên hệ thống.

Nạp lại sau khi gỡ sẽ nhận lại đúng các hồ sơ đã ẩn, không tạo thêm hồ sơ mới.

## Đã kiểm (05/10, bản sao prod 05/10 02:15 trên Mac)

- Thử khô và ghi thật mỗi lần mất khoảng 40 giây.
  - Tạo mới 8.592 hồ sơ, ghép vào khách đã có 123.
  - Nhập được 14.310 lượt khám, 30.726 dịch vụ, 22.353 tờ kết quả, 10.677 xét nghiệm,
    35.036 dòng thuốc, 18.946 lịch hẹn.
- Dữ liệu hệ thống mới không đổi: `visit` 109, `appointment` 133, `payment` 135.
- Nạp lại lần hai: 0 hồ sơ mới.
- Gỡ rồi nạp lại: 0 hồ sơ mới, các hồ sơ đã ẩn được bật lại.
