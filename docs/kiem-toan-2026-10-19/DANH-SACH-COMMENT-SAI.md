# Danh sách comment nói khác code (bản prod 956ba4f2)

Nguồn: rút từ 554 mục của báo cáo kiểm toán, những mục mà người đọc ghi rõ một comment, docstring, chú thích hoặc tài liệu trong code **không khớp hành vi thật**. Lọc bằng một lượt đọc của mô hình, mỗi dòng đã được máy kiểm tệp có tồn tại ở bản ghim. **Cần người kiểm lại** trước khi sửa: tệp ở cột 2 là tệp bằng chứng đầu tiên của mục, vị trí chính xác của comment nằm trong thẻ mục tương ứng ở BAO-CAO-DAY-DU.html.

Vì sao quan trọng: comment sai che lỗi. Ví dụ OPS-014: comment hứa "chốt sẽ xét lại khi đã có người", code không có lần xét lại nào.

Tổng: **34 chỗ**. 7 chỗ chỉ cần sửa comment, 26 chỗ comment đang ghi *điều nên đúng* còn code chưa làm (thực chất là lỗi code), 1 chỗ cần chủ sản phẩm quyết nghĩa đúng.

## A. Chỉ cần sửa comment cho khớp code (7 chỗ, làm được ngay, rủi ro thấp)

| Mục | Tệp bằng chứng đầu tiên | Comment đang nói | Code thật làm |
|---|---|---|---|
| INF-006 | `scripts/backup-db.sh` | Comment về backup manifest và restore-drill vẫn nhắc Supabase Cloud PITR/auth backup. | Hệ thống đang chạy self-hosted, không dùng Supabase Cloud. |
| OPS-007 | `supabase/config.toml` | Chú thích hướng dẫn link project ref và chạy supabase db push; các comment khác nói DB là Supabase Cloud/Vercel/Mac mini (docker-compose.supabase.yml, Dockerfile.api, .env.example). | Hệ thống hiện self-hosted trên VPS, cấm db push và phải qua backup, rehearsal, apply-pending-migrations.sh. |
| INF-029 | `docker-compose.supabase.yml` | Chú thích nói các dịch vụ tuỳ chọn 'kept current by deploy + self-heal'. | Repo không có thành phần self-heal/autoheal nào; self-heal cũ chỉ ở LaunchDaemon của Mac mini. |
| TEST-027 | `scripts/test-nhanh.sh` | Comment nói 'sửa migration là lượt sau thấy ngay'. | Script chỉ so version migration, không so checksum, nên sửa nội dung migration đã vào khuôn không được áp lại. |
| API-011 | `src/clinicai/api/v1/routers/phieu_kham.py` | Docstring và comment main.py nói router chưa dùng được, chặn tất, chỉ đọc, không có đường ghi. | Router có PUT /phieu, PUT /don-thuoc, PUT /ke-don-tu-van, POST /lich-tai-kham và lay_kiem_quyen trả kiem_quyen_core. |
| CLIN-072 | `src/clinicai/services/chuyen_luot_that.py` | Docstring nói Hoàn tất khám không khoá hồ sơ và chú thích tham chiếu LuotKhamService._khoa_ho_so_khi_hoan_tat. | Hàm đó không còn trong mã; release() không gắn revision nên hồ sơ đã cho phép gửi vẫn sửa được mà không thu hồi quyền gửi. |
| SEC-088 | `supabase/fixtures/clinic_roster.sql` | clinic_roster.sql ghi 'KHÔNG chứa PII nhân sự'. | Tệp liệt kê 35 người bằng tên gọi thật, các tệp liên quan chứa họ tên, học hàm, địa chỉ đăng nhập và mật khẩu chung. |

## B. Comment đang ghi điều nên đúng, code chưa làm (26 chỗ)

Đây không phải việc gọt comment. Sửa code cho đúng điều comment hứa, hoặc nếu quyết không làm thì sửa cả comment lẫn kỳ vọng. Mỗi dòng trùng với một mục trong báo cáo (cùng mã), đi theo mức ưu tiên của mục đó.

| Mục | Tệp bằng chứng đầu tiên | Comment đang nói | Code thật làm |
|---|---|---|---|
| SEC-005 | `src/clinicai/api/v1/routers/staff.py` | Nhãn giao diện ghi 'Số CCCD (chỉ Quản lý & Trưởng ca xem được)'. | GET /staff và /staff/{id} chỉ yêu cầu đăng nhập và trả CCCD cho mọi nhân viên cùng clinic. |
| SEC-017 | `supabase/migrations/20260730000015_patient_summary_security_invoker.sql` | Migration giải thích dùng security_invoker để RLS chạy theo người gọi. | View cuối (v_quyen_thuc_te) thiếu security_invoker, không lọc clinic ở roster và vẫn cấp SELECT cho authenticated. |
| SEC-018 | `caddy/Caddyfile` | Comment migration nói kênh liên hệ và thân nhân dành cho nhu cầu Reception/CSKH. | RLS chỉ lọc theo clinic, nên mọi vai authenticated cùng clinic đọc được qua PostgREST. |
| INF-020 | `docker-compose.staging.yml` | Comment giả định ngân sách 100 kết nối Postgres đủ cho các pool. | Với API=60 trần đã biết là 112, mặc định API=20 là 72; compose prod không ghim max_connections=100. |
| OPS-014 | `src/clinicai/api/v1/routers/dispatch.py` | Comment hứa 'chốt sẽ xét lại khi đã có người'. | Hai endpoint ghi không có người đích, không truyền target_staff_id và không có lần kiểm lại nào, nên luật không bao giờ chặn. |
| FE-032 | `src/clinicai/services/luot_kham_service.py` | Chú thích các lệnh ghi 'Khoá gửi lại bắt buộc' và nguyên tắc khoá không sinh mới mỗi lần bấm. | guiThaoTac gọi khoaGuiLai() trong mỗi lần gọi, nên mỗi lần bấm hoặc Thử lại có khoá mới. |
| FE-059 | `src/dashboard/app/(dashboard)/customers/HanhDongTrangThai.tsx` | Comment nói lỗi mạng/5xx giữ khóa để bấm lại sẽ không ghi trùng. | Khóa chỉ nằm trong Map bộ nhớ tab; ghi() không bắt lỗi mạng và ghiMotCham không dọn trạng thái 'đang ghi'. |
| CLIN-115 | `src/clinicai/api/v1/routers/dispatch.py` | Docstring nói 'Bấm lại khi chưa ai xử lý: không nhân đôi'. | Chỉ mục duy nhất chỉ áp khi nguon_id IS NOT NULL, mà nguon_id là tuỳ chọn. |
| SEC-041 | `docker-compose.yml` | Dịch vụ dashboard ghi 'Frontend (Next.js standalone) — UI only'. | Dashboard nhận nguyên .env.prod gồm service-role key, JWT secret và DATABASE_URL superuser, và dùng chúng trong tiến trình Next. |
| SEC-042 | `docker-compose.supabase.yml` | Chú thích nói backend chạy bằng vai service_role BYPASSRLS theo giao kèo tenant-scope-audit. | DATABASE_URL nối bằng vai postgres (superuser) và các vai khác dùng chung mật khẩu superuser. |
| ARCH-001 | `.env.example` | Comment nói Zalo OA là cấu hình từng phòng khám, và POS cấu hình trong clinic.settings->'pos'. | Token và mã template Zalo/Telegram đặt ở env toàn cục, cổng bật POS là POS_ADAPTER env. |
| INF-036 | `.env.prod.example` | Chú thích cảnh báo OOM và nói prod nên bỏ trống NEXT_WORKERS, DASHBOARD_MEMORY_LIMIT=1g. | Mẫu .env.prod đặt DASHBOARD_MEMORY_LIMIT=512m và không đặt NEXT_WORKERS. |
| OPS-026 | `scripts/xoa-du-lieu-test.sh` | Bản xem trước hứa 'CHÍNH XÁC số dòng sẽ xoá'. | Chỉ liệt kê 15 bảng; nhiều bảng bị xoá ngầm qua CASCADE, còn bảng ON DELETE RESTRICT không được xoá làm DELETE patient lỗi. |
| SEC-048 | `src/clinicai/events/catalogue.py` | Docstring nói payload sổ sự kiện 'không bao giờ có nội dung lâm sàng, tên khách, số điện thoại'. | Nhiều payload có trường chuỗi tự do (ly_do, ghi_chu, ket_qua) và emit_event ghi nguyên model_dump không làm sạch. |
| FIN-025 | `src/clinicai/services/checkout_service.py` | Docstring nói 'Một truy vấn cho cả danh sách… không vòng mạng cho mỗi bệnh nhân'. | _gan_doi_tac_tu_thu duyệt tuần tự từng lượt, mỗi lượt gọi nhiều truy vấn (tới ~300 lượt × hàng chục truy vấn). |
| CLIN-119 | `src/clinicai/services/capacity_service.py` | Docstring quote() nói trigger enforce_slot_capacity đếm mọi cơ sở. | bang_tuan gọi quote(location_id=cơ sở đang đứng) nên chỉ đếm ghế của một cơ sở. |
| CLIN-094 | `src/clinicai/api/v1/routers/luot_kham.py` | Docstring router ghi 'Huỷ bắt đầu nhầm' chỉ khi chưa điền phiếu kết quả. | Code và test xoá cả phiếu revision=1 về mặc định, không kiểm người bấm hay nội dung đã nhập. |
| CLIN-100 | `src/clinicai/services/lieu_trinh_service.py` | Docstring nói hoàn tác là của 'người bấm' lần sửa vừa làm. | Chỉ kiểm revision khớp và hành động thuộc nhóm hoàn tác được, không so người sửa, và UI lấy dòng SUA đầu tiên hoàn tác được. |
| CLIN-124 | `src/clinicai/services/hen_tai_kham_service.py` | Chú thích nói cuộc gọi cũ nằm ở cskh_log. | Việc đóng không bắt buộc ghi cskh_log, còn UPDATE xoá ket_qua, goi_luc, nguoi_goi_staff_id về NULL khi đổi ngày hẹn. |
| OPS-035 | `supabase/fixtures/ngay_dieu_phoi_demo.sql` | Comment dòng 90 nói 'Lượt của bệnh nhân THẬT không bị đụng'. | Phần trên đóng mọi visit/work_item/appointment ngày cũ của clinic và xoá service_order không lọc DEMO-%. |
| OPS-036 | `supabase/fixtures/lich_lam_viec_tuan_mau.sql` | Comment nói có phòng khám thứ hai thì phải truyền vào, không đoán. | Lấy phòng khám bằng ORDER BY created_at LIMIT 1, tức vẫn đoán. |
| DB-010 | `scripts/dev-up.sh` | Migration ghi seed đã được sửa nên không bị ghi đè kết quả migration trước. | Seed hiện vẫn nạp 14 loại khám cũ và không chứa sửa đổi đó. |
| PHAR-019 | `src/clinicai/services/kiem_ke_ca_service.py` | Docstring chot() nói 'bán giữa lúc đếm không làm lệch'; bất biến (4) nói điều chỉnh xong thì tồn quầy = số đếm. | Chỉ ghi ADJUST bằng độ lệch đã lưu lên tồn hiện tại; test chỉ kiểm sau = trước + lech. |
| TEST-021 | `src/tests/services/test_quyen_cache_db.py` | Docstring và thông báo skip dặn đặt DATABASE_URL_TEST. | Bốn tệp test thực tế đọc DATABASE_URL. |
| TEST-042 | `src/tests/unit/test_patient_service.py` | Docstring hứa câu báo lỗi phải nêu tên cơ sở. | Assert dùng regex 'Hào Nam\|đã ngừng hoạt động' trong khi fixture trả 'Kim Ngưu', nên thực chỉ kiểm cụm 'đã ngừng hoạt động'. |
| CLIN-085 | `src/clinicai/services/mau_ket_qua_service.py` | Docstring nói gắn nhầm mẫu là thay đổi lâm sàng nên mỗi lần phải truy được. | gan/go/tao_mau chỉ INSERT/DELETE, không có record_event/emit_event/audit; gỡ còn xoá luôn dòng chứa ai gắn. |

## C. Cần chủ sản phẩm quyết nghĩa đúng (1 chỗ)

| Mục | Tệp bằng chứng đầu tiên | Comment đang nói | Code thật làm |
|---|---|---|---|
| SEC-023 | `src/clinicai/api/v1/routers/cskh.py` | Comment nói thu ngân chỉ xem, không gọi chăm sóc. | Preset thu ngân có crm.manage, nên ghi được tương tác, follow-up và phản hồi CSKH. |

## Cách làm gợi ý
1. Nhóm A: một PR nhỏ, đổi chữ trong comment, CI chạy một lần.
2. Nhóm B: làm cùng lúc với việc sửa mục tương ứng; đừng làm PR riêng.
3. Khi đụng tới một tệp, gọt luôn comment chỉ kể lịch sử (ngày đổi) của tệp đó. Không xoá hàng loạt.
