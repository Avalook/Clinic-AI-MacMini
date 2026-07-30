# ADR-0013 — Chạy trên Mac mini bây giờ, nhưng phải bê lên VPS mà không sửa code

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-07-30 |
| **Deciders** | Quang — "xây để sẵn sàng bê lên VPS luôn, nhưng chưa thuê nên dùng tạm trên Mac mini đã" |
| **Liên quan** | ADR-0005 (không thêm hạ tầng có trạng thái), ADR-0006 (ngân sách tài nguyên Mac mini), DOD "Cloud VPS", `docs/deploy-mac-mini.md` |

## Context
DOD ghi đích là Cloud VPS. Thực tế hiện chạy Mac mini 48GB tại chỗ vì chưa thuê VPS.
Rủi ro: hạ tầng "tạm" ăn sâu vào code (đường dẫn tuyệt đối kiểu macOS, `launchd`, cổng
cứng, phụ thuộc Docker Desktop, model chạy local) rồi lúc chuyển phải viết lại.

## Decision
1. **Mac mini là một môi trường triển khai, không phải một kiến trúc.** Mọi khác biệt
   phải nằm trong compose override + `.env`, không nằm trong code ứng dụng.
2. **Ràng buộc bất di bất dịch:**
   - Không đường dẫn tuyệt đối theo máy trong code; mọi thứ qua biến môi trường.
   - Không lưu trạng thái trong container; dữ liệu ở Supabase (ADR-0005), file ở volume
     có tên rõ ràng và có trong quy trình backup.
   - Image build cho **linux/amd64 và arm64** (multi-arch), không chỉ arm64.
   - Không phụ thuộc thứ chỉ có trên macOS (Docker Desktop, `launchd`, Keychain) trong
     đường chạy của ứng dụng — `launchd` chỉ được dùng để khởi động Docker Compose.
   - Ingress qua Caddy + `SITE_ADDRESS` từ env; không cổng cứng trong code.
3. **Kiểm chứng tính di động bằng CI, không bằng niềm tin:** CI build image amd64 và
   chạy stack + smoke test `/health` trên runner Linux của GitHub. Nếu CI Linux xanh thì
   VPS chạy được.
4. **Việc chuyển VPS = 3 bước**: đổi DNS → `docker compose --env-file .env.prod up -d`
   trên VPS → chuyển Supabase connection string. Không sửa code, không sửa migration.
5. **Điểm khác biệt duy nhất được phép:** kích thước tài nguyên (ADR-0006) và
   AI chạy local vs API — cấu hình bằng env, có mặc định an toàn cho cả hai.

## Alternatives
| | Ưu | Nhược |
|---|---|---|
| **A. Container hoá trung lập, kiểm chứng bằng CI Linux (chọn)** | chuyển VPS là việc vận hành, không phải dự án | phải giữ kỷ luật multi-arch + không dùng tiện ích riêng macOS |
| B. Tối ưu hết cỡ cho Mac mini, sau này port | nhanh hơn chút lúc này | port = viết lại phần vận hành + rủi ro lúc đang có bệnh nhân thật |
| C. Thuê VPS ngay | hết chuyện | tốn tiền khi chưa có doanh thu; Mac mini đã có sẵn |

## Consequences
**Tích cực:** thời điểm thuê VPS là quyết định kinh doanh, không phải rào cản kỹ thuật;
CI Linux còn bắt sớm lỗi phụ thuộc nền tảng.
**Tiêu cực:** build multi-arch chậm hơn; không tận dụng được vài tối ưu riêng của Apple
Silicon.
**Việc kéo theo:** thêm job CI build/chạy amd64; rà `docs/deploy-mac-mini.md` tách rõ
phần "riêng Mac" và phần "chung mọi môi trường".
