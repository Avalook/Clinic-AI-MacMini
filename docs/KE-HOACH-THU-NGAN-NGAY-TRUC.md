# Xem quầy thu theo ngày trực — local

Người dùng duyệt ngày 12/10/2026: danh sách ngày trực ở cả quầy thuốc và
dịch vụ, giới hạn xem/xuất theo ca; quyền thu/huỷ/hoàn hiện có giữ nguyên.
Chỉ làm và thử local 3100, không staging/prod trong phạm vi này.

Nguồn lịch là work_roster APPROVED của đúng tenant/nhân viên, đúng quầy.
Danh sách gom ngày trùng, có các ca và cơ sở; phân trang lịch sử, không dùng
200 dòng thông báo ca làm lịch đầy đủ. Nhân viên không xem ngày/ca ngoài
lịch; quản lý giữ phạm vi đầy đủ, trưởng ca cả ngày được phân công.

Backend kiểm board, giao dịch, lịch sử và CSV. Không chỉ kiểm ngày rồi
trả dữ liệu cả ngày: phải lọc giờ theo khung ca và cơ sở được phép. Chọn
ngày trên URL không cấp quyền mới. Lỗi quyền không giữ số của ngày trước.
Đọc phiếu/in phải rà cùng ranh giới, tránh lách qua ID; các màn in phục vụ
CSKH hiện có cần giữ riêng quyền của luồng đó.

Quầy đang chờ thu là dữ liệu công việc còn mở, khác sổ giao dịch đã thu.
Giữ khả năng thu khoản cũ theo quyền nghiệp vụ; timestamp giao dịch vẫn là
giờ thực tế khi thu, không ghi lùi ngày/ca đang xem. Không sửa endpoint ghi
tiền hoặc schema để thực hiện danh sách ngày.

Kiểm: thuốc/dịch vụ, nhiều ca/FULL, APPROVED/PENDING, ngày cũ, tenant/cơ sở,
đổi URL/CSV và giờ biên ca. Kiểm không đổi quyền thao tác tiền; bấm DEMO
375/1280 trên local, CI cuối nếu toàn bộ phần sửa đã ổn.

## Phạm vi bổ sung đã duyệt 12/10/2026

- Lễ tân và thu ngân Quầy tiếp đón đều được thu dịch vụ; thu ngân tầng 2/3
  cũng thuộc dịch vụ, quầy thuốc thuộc thuốc. Quyền theo lịch APPROVED.
- Ngoài ca chặn nghiệp vụ tiền cả API, ẩn lối vào quầy thao tác; lịch sử ca
  đã trực vẫn mở chỉ đọc. Nhân viên xem giao dịch mình thực hiện trong ca.
- Trưởng ca (Quản lý ca khám) đủ nghiệp vụ tiền cả hai quầy trong ngày và
  cơ sở trực; báo cáo cuối ngày/Hàng hoá cả ngày trực. Không cấp quản trị.
- Hàng chờ không lọc ngày tạo lượt hoặc người thu: khách tồn ca/ngày trước
  vẫn xử lý tại quầy đúng. Ghi tiền theo giờ thực tế, không ngày đang xem.
- Log giữ người thu gốc và người điều chỉnh; trưởng ca xử lý thay thay đổi
  dữ liệu thật, nhân viên vẫn xem được giao dịch gốc và điều chỉnh liên quan.
- Đồng bộ lịch sử thuốc với dịch vụ, tổng và CSV cùng phạm vi dữ liệu.

Quyết định: dùng work_roster và khung giờ ca hiện có tại backend, không
thêm bảng quyền song song. Bộ lọc áp trước aggregate/CSV. Phạm vi bổ sung
thay yêu cầu giữ nguyên endpoint tiền ở bản kế hoạch đầu.

Kiểm bổ sung: khách sáng thu chiều, khách hôm trước trả hôm nay, hai người
cùng ca, thu trùng, hết ca khi đang mở trang, trưởng ca xử lý thay + log.

## Kịch bản duyệt local/staging

1. Quản lý phân lịch DEMO: A lễ tân ca sáng, B thu ngân dịch vụ ca chiều,
   C quầy thuốc ca sáng, D trưởng ca ca tối; cùng cơ sở. Duyệt lịch.
2. A mở quầy dịch vụ trong ca: có hàng chờ tồn từ hôm trước; thu một khách.
   B cùng loại quầy không thấy khoản A thu trong lịch sử cá nhân.
3. Ngoài ca A: nút vào quầy thao tác ẩn; lịch sử dịch vụ vẫn mở đúng ca sáng.
   Sửa URL sang chiều/ngày khác, CSV hoặc API trực tiếp đều không vượt quyền.
4. D ngày được phân trưởng ca: xem cả ngày báo cáo cuối ngày và Hàng hoá;
   xử lý thu/hoàn thay khi đang trực. Kiểm người thực hiện trong log là D,
   người thu ban đầu vẫn A; A thấy điều chỉnh liên quan phiếu của mình.
5. C mở lịch sử thuốc: cùng khung tổng/danh sách/Excel như dịch vụ.
6. Rút lịch đang mở trang: request tiền tiếp theo bị chặn, không ghi tiền.
7. Kiểm màn 375px và 1280px, không tràn ngang, không còn số từ lần xem trước
   khi API từ chối. Không sửa dữ liệu thật và không deploy trong lượt local.

### Dấu vết phiếu chờ chuyển khoản qua ca

Nếu A lập phiếu chờ ở ca sáng và B xác minh ca chiều, A xem phiếu theo
thời điểm mình lập, B xem theo thời điểm xác minh. Phiếu giữ cả created_by
và confirmed_by. Báo cáo tài chính trưởng ca/quản lý vẫn dùng giờ thu thực
tế; lịch sử cá nhân phản ánh trạng thái mới nhất và điều chỉnh liên quan.
