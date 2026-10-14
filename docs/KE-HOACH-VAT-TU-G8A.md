# Q1 · G8a · kế hoạch thực hiện

Nguồn quyết định: `viec-cho-codex-hang-doi-1410.md`, mục G8a trong
`viec-cho-codex-1410.md`, kế hoạch 14/10 mục 2e. Một việc tại một thời điểm.

## Lát 1 — nền sổ kho

`vat_tu_phieu` bất biến + `vat_tu_txn` chỉ thêm + `vat_tu_ton` cache do trigger
cộng. Khoá SQL theo phòng khám/cơ sở bảo vệ cấp mã, gửi lại, kiểm và đảo.
Phiếu chuyển có hai dòng đối ứng, tổng tồn không đổi. Cho tồn âm và trả cảnh
báo bắt buộc. Phòng tắt vẫn kiểm/nhận trả/hiện tồn được.

KIEM chụp tồn sổ và số đếm, không thay tồn; DIEU_CHINH là thao tác riêng,
số mới = số đếm. Lần đầu dùng điều chỉnh để đưa tồn 0 thành tồn thực tế.
Hoàn tác đảo đúng delta gốc, không ép tồn trở về số cũ khi có phiếu xen giữa.
Giá nhập trên dòng là snapshot người lập phiếu, không đọc lại giá hiện tại.

Backend kiểm UUID, số hữu hạn/độ chính xác trước khi ghi. Postgres chốt tenant,
nơi chứa, dòng đảo, append-only và chỉ sổ được thay tồn. Phiếu lưu ai/lúc/lý do.
NOTIFY là tín hiệu làm mới; dữ liệu thật vẫn đọc từ API, không dựa vào số lần
nhận tín hiệu. Ở quy mô hiện tại một khoá ngắn mỗi cơ sở đơn giản và đủ tải.

## Các lát tiếp theo trong Q1 (chưa hoàn thành ở lát 1)

Tuyền chốt tiếp: cờ “Được kinh doanh” chỉ phân loại. Giữ điều kiện bán cũ
(active + giá dương + duyệt khi mặt hàng yêu cầu), không thêm cổng chặn.
Danh mục mới giữ phân loại ban đầu theo giá đã có, lần chạy lại không đè sửa tay.

- Danh mục: loại VPP/VTYT, kinh doanh, giá nhập, mã vạch, cờ duyệt; proxy PATCH
  phải chuyển đủ cột. Backfill 84 hàng giữ nguyên, 3 hàng có giá kinh doanh.
- API và màn Kho vật tư; thêm lego riêng sau khi báo Tuyền, không gác theo vai.
  Không tự coi lego kho thuốc là quyền vật tư. Mức tối thiểu mỗi nơi chỉnh trên màn.
- Báo cáo tiêu hao phòng/kỳ và giá trị; số cuối lấy kiểm đếm đã chọn trong kỳ,
  chưa có kiểm đếm phải hiện chưa đủ dữ liệu. Không coi kiểm = điều chỉnh.
- Giữ luồng bán cũ, trigger duyệt MANAGEMENT, tiền và kho thuốc; G8b xử lý bán
  trừ tồn/duyệt. G9 chỉ mở sau khi Q1 đủ PR và CI xanh.

## Kiểm chứng

Test bất biến chạy trước code trên main: đỏ vì chưa có module kho vật tư.
Mô phỏng 40 seed × 10 bước dùng lệnh thật, kiểm tổng sổ=tồn sau mỗi bước;
chuyển/kiểm không đổi tổng, gửi lại không thêm phiếu, âm phải nhắc.
Ca biên: gửi trùng đồng thời, phiếu đảo, rác không ghi, khác cơ sở,
phòng tắt còn tồn, SQL chống sửa tay. Kiểm nhanh đúng tệp, CI máy cuối PR.
