# Hướng dẫn TEST Dashboard — ClinicAI / Dr4Women (nội bộ)

> Dành cho team nội bộ test luồng **CSKH/Lễ tân ghi khách + lịch → Bác sĩ xem lịch + xác nhận/từ chối**.
> Cập nhật: 01/06/2026.

---

## 0. Trước khi test (đọc kỹ)

| Mục | Thông tin |
|---|---|
| **Link** | https://clinic-ai-dr4-women.vercel.app |
| **Mật khẩu phòng khám** Dr4Women@2026
| **Trình duyệt** | Chrome / Edge bản mới, máy đặt **múi giờ Việt Nam** |

> ⚠️ **Đây là DỮ LIỆU THẬT (import từ phòng khám).** Khi test tạo BN/lịch:
> - Đặt tên dễ nhận biết, ví dụ **"TEST – Nguyễn Thị A"**.
> - **Không xóa được**: BN và lịch đã tạo KHÔNG có nút xóa (Cơ chế Append-only) → data test sẽ nằm lại, cứ để vậy, báo dev dọn sau.
> - Đừng sửa/đụng vào BN thật của phòng khám.

---

## 1. Đăng nhập & chọn vai trò

1. Mở link → trang **"Nhập mật khẩu phòng khám"** → nhập mật khẩu chung → **Vào**.
2. Trang **"Chọn vai trò"**:
   - **Bác sĩ** → chọn **tên bác sĩ** trong ô dropdown → bấm **Vào**.
   - **CSKH / Lễ tân / Quản lý** → bấm thẳng vào ô đó.
3. Trong app: sidebar trái dưới cùng có **"Đổi vai trò"** (đổi role bất kỳ lúc nào) và **"Thoát"**.

**Mỗi vai trò sẽ:**

| Vai trò | Menu chính | Làm được |
|---|---|---|
| **Bác sĩ** | Trang chủ, Lịch hẹn, Bệnh nhân | Xem "Lịch của tôi", **Xác nhận / Từ chối** lịch của mình |
| **Lễ tân** | + Nhập BN mới | Tạo BN, đặt lịch, nhận thông báo lịch bị từ chối |
| **CSKH** | + Nhập BN mới, Công việc | Như Lễ tân + Công việc |
| **Quản lý** | Tất cả (+ Ca trực, Báo cáo, Cài đặt) | Toàn quyền |

---

## 2. Các kịch bản test (tick khi xong)

### KB-A — Tạo bệnh nhân mới + đặt lịch  ·  *vai trò: CSKH / Lễ tân / Quản lý*
- [ ] Vào **"Nhập BN mới"**.
- [ ] Điền **Họ tên** (bắt buộc) + chọn **Cơ sở** (bắt buộc); các ô khác (SĐT, ngày sinh, CCCD…) tùy ý.
- [ ] **Test trùng SĐT:** nhập một SĐT đã tồn tại → phải hiện cảnh báo *"Đã có bệnh nhân dùng SĐT này"* → chọn **"Dùng BN này"** hoặc **"Vẫn tạo bệnh nhân mới"**.
- [ ] Bấm **Tạo bệnh nhân** → chuyển sang **bước Đặt lịch**: chọn **Dịch vụ + Ngày + Giờ + Cơ sở** (Bác sĩ tùy chọn) → **Đặt lịch hẹn**. (Hoặc **"Bỏ qua, chỉ tạo BN"**.)
- ✅ **Mong đợi:** hiện *"Đã tạo bệnh nhân … và đặt lịch hẹn"*.

### KB-B — Đặt lịch cho bệnh nhân CÓ SẴN  ·  *vai trò: CSKH / Lễ tân / Quản lý*
- [ ] Vào **"Bệnh nhân"** → mở **một hồ sơ BN** bất kỳ.
- [ ] Bấm **"+ Đặt lịch hẹn"** → điền Dịch vụ/Ngày/Giờ → **Đặt lịch hẹn**.
- ✅ **Mong đợi:** hiện *"Đã đặt lịch hẹn"*; bảng **"Lịch sử lịch hẹn"** của BN cập nhật ngay.

### KB-C — Bác sĩ Xác nhận / Từ chối lịch  ·  *vai trò: Bác sĩ*
- [ ] Đăng nhập **Bác sĩ** (chọn đúng tên) → vào **"Lịch hẹn"** (mặc định **"Lịch của tôi"**) → tab **"Chờ xác nhận"**.
  - *Nếu trống:* nhờ một người role **CSKH** đặt trước 1 lịch cho **đúng bác sĩ này** (KB-A/B, ô "Bác sĩ" chọn tên đó).
- [ ] Bấm **"Xác nhận"** (xanh) → lịch chuyển sang tab **"Đã xác nhận"**.
- [ ] Bấm **"Từ chối"** (đỏ) ở một lịch khác → lịch chuyển sang tab **"Đã từ chối"** (vẫn nằm trong lịch sử của bác sĩ).
- ✅ **Mong đợi:** trạng thái đổi đúng, lịch nhảy đúng tab.
- ⚠️ Nếu **"Từ chối"** báo lỗi đỏ → **migration 034 chưa chạy** trên DB → báo dev (nút "Xác nhận" vẫn chạy bình thường).

### KB-D — Thông báo "lịch bị từ chối"  ·  *vai trò: CSKH / Lễ tân / Quản lý*
- [ ] Sau khi một bác sĩ **Từ chối** (KB-C) → đăng nhập role **CSKH / Lễ tân / Quản lý** → **reload (F5)**.
- ✅ **Mong đợi:** **toast góc trên–phải**: *"🔔 N lịch bị bác sĩ từ chối"* + danh sách (tên BN · giờ · bác sĩ). Bấm **✕** để tắt thông báo.
- [ ] Vào **"Lịch hẹn" → tab "Đã từ chối"** → cũng liệt kê các lịch này.


### KB-E — Phân quyền menu
- [ ] Đăng nhập **lần lượt từng vai trò**, kiểm tra menu trái khớp bảng ở Mục 1 (ví dụ: **Bác sĩ KHÔNG có "Nhập BN mới"**; chỉ **Quản lý** thấy Báo cáo/Cài đặt/Ca trực).

---

## 3. Giới hạn hiện tại (ĐÃ BIẾT — đừng báo là lỗi)

- **Phân lại bác sĩ khác** khi bị từ chối: **chưa có** (đang làm sau). Hiện lịch từ chối chỉ hiển thị ở tab "Đã từ chối" + thông báo.
- Trang **Lịch hẹn chỉ hiện lịch HÔM NAY**.
- Không xóa được BN/lịch đã tạo (chủ ý — chống mất dữ liệu).
- Các module khác (Voice/AI, Báo cáo chi tiết, Ca trực…) **chưa nằm trong đợt test này**.

---

## 4. Cách báo lỗi

Khi gặp bất thường, ghi đủ 5 ý gửi vào nhóm [điền kênh chat]:
1. **Vai trò** đang dùng (Bác sĩ tên gì / CSKH / Lễ tân / Quản lý).
2. **Bước làm** (kịch bản KB nào, bấm gì).
3. **Mong đợi vs Thực tế**.
4. **Ảnh chụp màn hình** (kèm thông báo lỗi nếu có).
5. **Giờ gặp lỗi + trình duyệt/thiết bị**.
