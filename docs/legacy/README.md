# docs/legacy — tài liệu thời hạ tầng cũ

**Mọi file trong thư mục này KHÔNG phản ánh hệ thống hiện tại.** Chúng tả các đời
hạ tầng đã chết: Mac mini chạy prod, Vercel, Supabase cloud, VPS cũ `clinic-vps`
(222.255.215.219), staging cổng 8080, CD qua GitHub Actions, `supabase db push`.

Giữ lại chỉ để tra *vì sao* hệ thống thành ra như bây giờ. Đừng làm theo lệnh
hay địa chỉ trong đây. Sự thật hiện hành nằm ở `CLAUDE.md` (gốc repo),
`docs/SO-LUAT.md` và `docs/DANG-LAM.md`.

Chuyển vào đây ngày 27/09/2026 (dọn theo `docs/KIEM-TOAN-HE-THONG-2709.md` mục 4).

Đợt hai 01/10/2026 (theo báo cáo quét dọn 01/10, mục C): thêm 18 tài liệu `docs/*`
(sổ tay Mac mini, VPS Vietnix, Vercel, staging 8080, kế hoạch đợt đã xong, phép đo
một lần…), `CHANGELOG.md` (ngừng ghi từ 20/07), 4 tệp `context/` không ai trỏ tới,
cả thư mục `final_canon/` (canon tháng 5, đã bị thesis + ADR + SO-LUAT thay). Mỗi tệp
có dòng "LỖI THỜI" ở đầu nói lý do. Script và plist đời Mac mini (`clinic-boot`,
`clinic-backend-boot`, `launchdaemons/`, `server-status`, `check-schema-drift`,
`rehearse-data-migration`, `docker-cleanup`) và `.github/workflows/cd.yml` đã **xoá**
khỏi cây — xem lại bằng `git show 29f49827:<đường dẫn>`.
