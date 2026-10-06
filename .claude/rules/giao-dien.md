---
paths:
  - "src/dashboard/**"
  - "DESIGN.md"
  - "docs/SITEMAP.md"
---

# Sửa giao diện — quy trình bắt buộc (Tuyền chốt 18/09/2026)

Vì sao có mục này: các lần sửa giao diện trước hay **sửa nhầm bản cũ** hoặc
**sửa một lối, sót lối khác**. Ví dụ có thật ngày 17/09: nút QR được gỡ ở màn
thu ngân cũ (`/tasks`), trong khi màn đang dùng là `/thu-ngan/*`.

1. **Trước khi sửa, tra `docs/SITEMAP.md`.** Mục A cho biết route nào là màn
   chuẩn. Mục B liệt kê mọi lối vào của cùng một chức năng. Phải sửa **đủ mọi
   lối** trong hàng đó, hoặc ghi rõ lối nào cố ý bỏ và vì sao. Không có trong
   bảng thì grep theo **component và API**, không grep theo tên màn.
2. **Không sửa màn đã đánh dấu GỘP hay ĐÃ CHUYỂN HƯỚNG.** Sửa ở màn chuẩn.
3. **Không tự chế giao diện.**
   - Màu, cỡ và bo góc lấy từ thang trong **`DESIGN.md`** (hiến pháp giao diện,
     chốt 15/08/2026) và token trong `globals.css`. "To ra" = nhích một bậc thang.
   - Nút và thành phần lấy từ `src/dashboard/components/ui`. Thiếu thì thêm vào
     đó trước, rồi mới dùng.
   - Không viết hex, px tự chế hay `style={{}}` mới.
   - Không thêm `window.confirm` mới.
   - `<button>` luôn có `type=`.
   - **Không luật nghiệp vụ nào trong TSX** — TSX chỉ vẽ và gửi lệnh; route
     `app/api/**/route.ts` chỉ chuyển tiếp (`docs/SO-LUAT.md` Phần 3).
4. **Thêm, xoá hay đổi một route, một mục thanh bên, hoặc quyền trong
   `NAV_ROLES`:** sửa `docs/SITEMAP.md` trong **cùng commit**, rồi chạy
   `python3 scripts/ban-do-code.py` và commit `docs/BAN-DO-CODE.md`.
5. **Báo cáo sau khi sửa phải có bảng "nút/link đã đụng"**, gồm: màn → nút →
   đi đâu hoặc gọi API nào → vai nào thấy.
6. **Chưa bấm thật thì không báo "xong".** Ghi rõ đã kiểm ở lớp nào:
   - test;
   - API;
   - bấm trên trình duyệt, ở cỡ 375 và 1280 (nghiệm thu đủ 375/768/1280 khi đổi cỡ).

   Kiểm bằng API không chứng minh được giao diện.

Worktree mới chưa có `src/dashboard/node_modules` → LSP TypeScript báo mọi import
là không tìm thấy. Sửa TSX trong worktree thì chạy `(cd src/dashboard && npm ci)` trước.
