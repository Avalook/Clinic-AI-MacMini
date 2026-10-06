---
paths:
  - "supabase/migrations/**"
  - "scripts/apply-pending-migrations.sh"
---

# Database — chỉ qua migration

- Lược đồ = `supabase/migrations/*.sql` (theo git). Đổi database = **migration
  MỚI**; không sửa migration cũ, **không bao giờ** sửa lược đồ bằng tay.
- Mỗi việc chạy song song dùng **một dải giờ migration riêng** để tên tệp không đè nhau.
- Áp bằng **`scripts/apply-pending-migrations.sh`** — nó so thư mục với sổ ghi và
  áp mỗi migration cùng dòng ghi sổ trong một giao dịch. **Không dùng `supabase db push`.**
  Test: `CLINIC_DB_CONTAINER=chung_test_db ./scripts/apply-pending-migrations.sh --apply`.
- Áp xong: `NOTIFY pgrst, 'reload schema'` để PostgREST thấy cột/bảng mới.
- **Không chạy migration trong lúc deploy** — đó là một bước riêng, có người xem
  (diễn tập trên bản sao trước: skill `len-prod`).
- Bất biến có tranh chấp ép ở đây (ràng buộc/khoá SQL), không ở Python
  (`docs/SO-LUAT.md` Phần 6).
- Bảng mới mà màn cần thấy tức thời → migration tạo trigger `trg_notify_<bảng>`
  gọi `notify_row_change` (mẫu: `20260927000002_notify_realtime_con_lai.sql`) **và**
  thêm tên bảng vào `LIVE_TABLES` (`RealtimeRefresher.tsx`). Supabase Realtime /
  publication `supabase_realtime` đã bỏ từ 27/09 — không dùng.
