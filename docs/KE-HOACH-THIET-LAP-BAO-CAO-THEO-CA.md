# Thiết lập báo cáo theo ca

Ngày 12/10/2026. Người dùng đã duyệt yêu cầu và xác nhận ca sáng/chiều/tối/cả
ngày theo lịch phân công. Không triển khai prod trong phiên này.

## Kết quả thực hiện và kịch bản PM

- Cài đặt → Thiết lập báo cáo: ba công tắc nhân viên theo ca, trưởng ca theo
  ngày, tài chính đầy đủ. Chỉ quản lý lưu được, có nhật ký cập nhật.
- Doanh thu dùng số hiệu lực mới nhất sau sửa/huỷ/hoàn; không chốt ca.
- Mặc định Hào Nam nếu có; bộ lọc luôn hiện, bỏ ngày đứng riêng, dòng mô tả
  thừa và nút Tải lại. In và CSV chỉ xuất số đang thấy cùng phạm vi.
- Giảm giá chưa có nguồn ghi nhận: hiển thị Chưa có dữ liệu, không suy ra
  từ huỷ/hoàn hoặc giả thành 0. Doanh thu hiện trên dòng bán đã thu, chưa
  đại diện doanh thu bán chịu. Hoàn theo cohort ngày tạo của báo cáo cũ.
- PM thử bật công tắc, đăng nhập nhân viên có lịch APPROVED: chỉ bán hàng
  ca/cơ sở đó. Đổi ca bằng URL và gọi CSV ngoài phạm vi phải bị từ chối.
- Thử lịch PENDING, FULL, trưởng ca ngày cũ, đổi người trong ca; thử in/CSV,
  điện thoại 375 và desktop 1280. Tắt công tắc trở lại nếu chưa triển khai.
- Nút/link đã đụng: menu Báo cáo, tab bán hàng/tài chính, ngày/ca/cơ sở,
  In, Xuất Excel và Lưu thiết lập. Không nút ghi tiền hoặc lịch mới.

Không có migration mới. Dữ liệu local chỉ DEMO; không ghi VPS. CI xanh rồi
đưa staging và PM duyệt đúng SHA; Tuyền chạy lệnh lên prod theo CLAUDE.md.

## Phạm vi và quyết định

- Quản lý chỉnh thiết lập trong Cài đặt; dùng clinic.settings, không tạo hệ
  thống quyền song song hay tự sửa lịch nhân viên.
- Nhân viên chỉ xem bán hàng của ngày/ca APPROVED được phân công. FULL là
  cả ngày; làm một ca không được truy vấn cả ngày. Trưởng ca xem cả ngày
  được phân công làm trưởng ca; quản lý xem toàn bộ.
- Lịch ngày đang hỏi là nguồn sự thật, không lấy vai hôm nay để mở ngày cũ.
- Chính sách mới bật qua quản lý; chưa bật giữ quyền hiện hành. Không mở
  báo cáo vận hành/toàn cảnh cho người chỉ được xem bán hàng.
- Backend kiểm phạm vi cho JSON và CSV; giao diện dùng lựa chọn backend trả
  về. Bán hàng không trả tên khách, công nợ/tồn tiền toàn lịch sử hay số
  tiền ngoài ca/cơ sở. Không có lịch hoặc dữ liệu quyền lỗi thì từ chối.
- Nhân viên chọn một ngày/ca cụ thể; khoảng nhiều ngày chỉ quản lý. Trưởng
  ca được xem cả ngày làm trưởng ca, không mặc định mọi ngày lịch sử.

## Chỉ số

Giữ hợp đồng cũ cho người có quyền hiện hành. Báo cáo tài chính mới phân
biệt doanh thu trên các dòng bán đã thu với dòng tiền thực thu; hoàn tiền
đã chuyển theo completed_at, không dùng ngày tạo yêu cầu hoàn để diễn giải
tiền chuyển trong ca. Nợ theo ca là nợ ghi nhận trong ca còn chưa thu.
Không gọi phiếu thu là hoá đơn pháp lý.

Repo chưa có nguồn giảm giá; đang hỏi lựa chọn ghi Chưa có dữ liệu hay bổ
sung nghiệp vụ riêng. Không giả giảm giá bằng 0, không gọi doanh thu trên
phiếu đã thu là toàn bộ doanh thu bao gồm bán chịu.

## API, an toàn và kiểm

Mở API thiết lập chỉ cho quản lý; ghi JSONB cập nhật nguyên tử, có kiểm
kiểu và nhật ký theo cơ chế dự án. API phạm vi trả ca/ngày/cơ sở hợp lệ và
quyền xem bán hàng/tài chính. Giữ khóa clinic_id ở mọi query. Không cache
quyền khiến lịch vừa sửa còn mở ca cũ.

Test người có/không lịch, APPROVED/PENDING, FULL/ca, trưởng ca ngày cũ,
tenant/cơ sở, đổi URL/API/CSV, quyền sửa thiết lập, payload sales không chứa
financial/PII; bấm local 375/1280; CI một lần cuối và kịch bản PM. Thiết kế
ở quy mô 40 nhân viên, 50–80 lượt/ngày: query Postgres trực tiếp, không
cache/queue/service mới. Settings lỗi thì giữ đường quản lý, không mở staff.

## ADR — phạm vi quyền nằm ở backend

Chọn lớp kiểm báo cáo riêng dựa trên lịch, bổ sung vào quyền lego hiện có.
Không cấp report.view rộng cho nhân viên: sẽ mở các báo cáo vận hành không
thuộc yêu cầu. Giao diện chỉ vẽ lựa chọn; thay đổi ca trong URL không mở
rộng tập dữ liệu. Đánh đổi: thêm một lần đọc settings/lịch khi tải báo cáo
để không giữ quyền cũ sau đổi lịch.
