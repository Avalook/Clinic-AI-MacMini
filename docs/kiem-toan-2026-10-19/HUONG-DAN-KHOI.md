# Hướng dẫn chung cho agent kiểm toán

Đọc BAT-DAU-TU-DAY.md, CLAUDE.md và quy tắc vùng trước. Không sửa ứng dụng.
Bạn không một mình trong repo: không revert, stash, reset hoặc sửa file của người khác.

Bạn chỉ sở hữu ba file `blocks/<khối>.md`, `.findings.json`, `.coverage.json`.
Không sửa STATE/NHAT-KY chung: gửi root trạng thái để tích hợp.
PHAM-VI.json có trường owner giúp lấy danh sách của khối. Có thể đọc chéo khối để
chứng minh đường code và phủ nhận false positive; không ghi file của khối khác.

Khởi tạo checkpoint trên đĩa NGAY và cập nhật sau mỗi cụm kiểm tra. Nếu bị ngắt,
người dùng phải tiếp tục được từ file mà không cần chat của bạn.

Phương pháp: inventory toàn khối; quét cấu trúc/pattern để chọn nguy cơ; dùng
Serena overview/find_symbol/find_referencing_symbols để đọc và truy vết đường
code thực thi. SQL/config không hỗ trợ symbol có thể đọc theo đoạn có đánh số dòng.
Không grep rồi coi là đã đọc full. Kiểm tra migration sau có thay định nghĩa cũ;
chốt chặn ở caller/callee/DB có thể phủ nhận lỗi nhìn thấy trong một hàm.

Mỗi finding theo MAU-PHAT-HIEN.json. Chỉ ghi vấn đề có giá trị, không đếm style.
Không gọi mọi cái là CRITICAL. Không khẳng định xảy ra prod nếu chỉ thấy static.
Ghi cả điểm tốt đã chứng minh và phần chưa kiểm. Có mục bàn giao với file/hàm
kế tiếp và giả thuyết chưa giải. Coverage JSON là array: path, status
(inventoried/scanned/read/traced/tested/excluded), method, note, sha256.

Có thể kiểm thử local theo scripts/test-nhanh.sh nếu cần và runtime sẵn sàng;
không tự dựng DB, không chạy CI đầy đủ song song, không đọc env/secrets, không SSH.
Nếu không chạy được, ghi rõ, không đoán kết quả. Giữ terminal output ngắn,
không trích dữ liệu bệnh nhân hay fixture credential.

Kết quả cuối khối: findings JSON + coverage JSON + báo cáo md:
hiện trạng / phát hiện / điểm mạnh / chưa xác minh / kiến nghị thiết kế / bước kế tiếp.
Gửi root 5–10 dòng gồm file kết quả, finding nghiêm trọng nhất, số file từng mức,
runtime đã/chưa chạy. Khi cần kiểm chéo, gửi rõ file+hàm+dòng và luận cứ.
