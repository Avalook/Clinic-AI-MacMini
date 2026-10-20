# Round 13 — Công nợ, số dư và điều hướng quầy thu

**Snapshot:** /tmp/clinicai-audit-main-956ba4f2 · SHA 956ba4f236b1c92f1280d2097018c199e90ce8c7  
**Phương pháp:** đọc tĩnh có chọn lọc trên snapshot exact-main; đối chiếu MAIN-PHAM-VI.json và PHAT-HIEN.json để biết trạng thái coverage/dedup. Không chạy test/runtime, không truy cập DB/VPS/secrets/PHI, không sửa source/migration.

## Kết quả

Có hai candidate mới. Đây là rủi ro suy ra từ code tĩnh, không phải incident production đã xác minh.

### CAND-R13-AR-01 — Khoản nợ chưa có giá bị quy thành 0 trong số dư phải thu

Hóa đơn cho phép thanh_tien=None khi chưa có giá; loc_no_dich_vu vẫn giữ khoản đó thành một dòng nợ và API nhận biết “chưa có giá”. Khi ghi nợ, NoKhiVe.tong cộng so_tien or 0, do đó cong_no.so_tien bằng 0 dù JSON chi tiết còn dòng so_tien:null. Khi tính sổ sau check-out, so_no_service lại quy None thành 0; ghi_chenh_lech bỏ chênh lệch 0 và bảng dư nợ mở chỉ lấy so_du > 0. doc_khach_con_no tổng hợp từ bảng dư nợ mở đó nên không đếm khoản chưa biết giá.

**Trigger:** một dịch vụ đã nhận nhưng chưa có giá hiện hành được đưa vào nợ; nhân viên bấm “Ghi nợ”, khách check-out, rồi quản lý xem số khách/số tiền còn nợ.

**Ảnh hưởng:** số dư tiền và danh sách dư nợ mở có thể trình bày như không còn nợ, dù bản ghi cong_no đang mở và JSON chi tiết vẫn mang khoản chưa định giá. Đây là sai lệch giữa trạng thái “còn nghĩa vụ chưa rõ số tiền” với projection chỉ đếm số dư dương. Không kết luận khoản nợ bị mất khỏi mọi màn hình hoặc không thể được cập nhật sau này; đường cập nhật giá và việc đối chiếu lại sau 48 giờ chưa được xác minh trong lát này.

**Đề xuất:** biểu diễn riêng số khoản/giá trị chưa xác định trong sổ và projection truy thu, không ép trạng thái chưa rõ thành 0 đồng có nghĩa “không còn nợ”. Quy tắc có cho check-out sau khi ghi nhận khoản chưa định giá hay không là quyết định nghiệp vụ; nếu cho phép, giao diện số dư phải giữ rõ hàng đợi chưa định giá và người chịu trách nhiệm xử lý.

**Chấp nhận khi:** test một khoản dịch vụ đã làm chưa thu, không có giá: ghi nợ và check-out phải giữ trạng thái “còn khoản chưa định giá” trong báo cáo số dư mở (không chỉ hiện tổng 0); khi giá được bổ sung, projection chuyển đúng thành số tiền phải thu mà không nhân đôi hoặc làm mất khoản. Nếu sản phẩm chọn cấm check-out khi chưa có giá, API phải từ chối nhất quán và không tạo bản ghi khiến khoản trông như dư nợ 0.

**Bằng chứng:** bill_service.py 198–220, 248–264; cong_no_service.py 126–181, 238–251, 441–476; so_no_service.py 215–267, 285–313, 451–489; cong_no_service.py 359–398. Test hiện đọc bao phủ khoản có số tiền cụ thể, chưa thấy ca giá None đi qua sổ và projection.

**Giới hạn:** không chạy test/DB; chưa truy vết toàn bộ UI hiển thị các bản ghi cong_no mở hoặc các sự kiện thay giá. Không xác nhận cấu hình giá thiếu đang xảy ra ở production.

### CAND-R13-AR-02 — Ghi nợ chỉ khớp ID nguồn nên có thể cho check-out với số tiền ghi nhận đã cũ

NoKhiVe.phu_boi_ghi_no so tập hiện tại với lần ghi nợ bằng mỗi source_id; phép phủ không so source_type, số tiền, hay dấu chưa định giá. Trong khi đó ghi nợ lưu tổng và JSON chi tiết hiện tại. Với service_order, hóa đơn giữ source_id là ID chỉ định nhưng lấy giá từ dòng service_price đang active; nếu giá/giá trị hóa đơn của cùng nguồn đổi giữa lần “Ghi nợ” và check-out, phu_du vẫn có thể là true, chan_no là false, và blocker check-out không chặn. Số tiền trong bản ghi cong_no khi ấy vẫn là snapshot trước thay đổi.

**Trigger:** một nguồn nợ đã được ghi nhận; trước check-out, cùng source ID có số tiền mới do thay đổi cấu hình giá đang có hiệu lực hoặc dữ liệu giá trị hóa đơn; luồng checkout dựng lại hóa đơn nhưng coverage chỉ so source ID.

**Ảnh hưởng:** nhân viên có thể check-out sau khi xác nhận một số tiền khác với nghĩa vụ hiện tại; snapshot cong_no.so_tien/dong và no_khi_ve hiện tại không còn khớp. Không kết luận đây là đường sửa giá được dùng trong production hay có người đã bị thu sai; cũng không suy ra số dư sổ cuối cùng sai vì phép tính sổ được dựng lại từ nghĩa vụ hiện tại.

**Đề xuất:** định nghĩa khóa phủ nghĩa vụ gồm tối thiểu (source_type, source_id, amount, unresolved-price marker) và so sánh với snapshot còn hiệu lực. Khi tuple thay đổi, yêu cầu ghi nợ lại/xác nhận lại theo chính sách phòng khám; ghi nhận rõ phần nào đã thay đổi để chủ sở hữu xử lý.

**Chấp nhận khi:** ghi nợ service_order với giá A, thay đổi giá trị hiện hành cùng source ID thành B trước check-out: API phải báo bản ghi không còn phủ đủ và chặn checkout cho tới khi ghi nợ được cập nhật/xác nhận; sau cập nhật, tổng cong_no.so_tien và các dòng chi tiết phải bằng B. Cần thêm ca đổi loại nguồn/trùng ID nếu hệ thống có thể phát sinh.

**Bằng chứng:** cong_no_service.py 126–171, 441–476; bill_service.py 433–445, 663–685; checkout_service.py 1110–1128; test_cong_no_check_out_db.py 295–331. Test hiện chứng minh một source ID mới sau ghi nợ làm checkout bị chặn và ghi nợ lại cập nhật tổng; không kiểm tra thay đổi giá trị trên cùng source ID.

**Giới hạn:** cơ chế sai lệch theo ID là static; chưa kiểm tra API sửa bảng giá, transaction thực tế, quyền sửa giá hoặc dữ liệu production. Việc mọi thay đổi giá có bắt buộc xác nhận lại hay không cần chốt theo chính sách nghiệp vụ.

## Kiểm tra phạm vi và dedup

- cashier_navigation_service.py, cashier_scope_service.py, cashier_board_service.py, route liên quan và finance_gate.py cùng các caller được rà trong những đoạn ghi ở coverage. Không thấy candidate riêng về điều hướng cashier hoặc gate tiền; authorization vẫn được kiểm tại service/endpoint, còn navigation là projection theo roster/capabilities.
- Đối chiếu PHAT-HIEN.json: không lặp DB-007 (FK bệnh nhân–lượt), PHAR-001 (trả thuốc khi phiếu đã void), các finding FIN-* về giảm giá, lịch sử/giới hạn báo cáo, snapshot chốt ca, đối tác và tiền thừa, hoặc INF-007 về idempotency lease. Hai candidate Round 13 khác trigger: biểu diễn nợ chưa định giá và kiểm tra số tiền của snapshot nợ.
- Phạm vi là lát công nợ/số dư/điều hướng cashier nêu trong coverage, không phải đọc hết module hay toàn repository.
