# Round 15 — Thu hồi session sau đổi mật khẩu

Nguồn: exact main `956ba4f236b1c92f1280d2097018c199e90ce8c7`.

Trong `DoiMatKhauModal.tsx`, `updateUser` có kiểm tra lỗi, nhưng `signOut({ scope: "others" })` không đọc `error`. Sau đó component luôn báo thiết bị khác đã đăng xuất. Lỗi được resolve thành error object không đi vào `catch`; đây là điểm bất đối xứng trong thông báo trạng thái.

`SEC-025` — LOW / `confirmed_static`. Tác động được giữ hẹp: thông báo thành công có thể sai và việc thu hồi phiên chưa được xác nhận. Không khẳng định session khác chắc chắn sống sót, vì password change có thể chấm dứt session tùy cấu hình Auth. Tài liệu Supabase mô tả `signOut` trả `error` và `others` thu hồi các phiên khác; xem [API reference](https://supabase.com/docs/reference/javascript/auth-signout) và [session guide](https://supabase.com/docs/guides/auth/sessions).

Test liên quan hiện có chỉ kiểm tra layout/field; chưa có test trả `{ error }` từ signOut. Bổ sung test UI cho resolved error và success trước khi triển khai sửa. Không chạy Auth provider hoặc production.
