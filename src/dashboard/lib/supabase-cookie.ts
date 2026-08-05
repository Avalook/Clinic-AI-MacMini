// Tên cookie phiên đăng nhập — GHIM CỨNG, cố ý.
//
// `@supabase/ssr` mặc định suy tên cookie ra từ hostname của URL Supabase. Mà
// hai phía dùng hai URL khác nhau, bắt buộc phải khác:
//
//   máy chủ    SUPABASE_URL             http://clinicai_supabase_gateway:8000
//   trình duyệt NEXT_PUBLIC_SUPABASE_URL http://222.255.215.219
//
// Để mặc định thì server action đăng nhập ghi cookie
// `sb-clinicai_supabase_gateway-auth-token`, còn proxy và trình duyệt đi tìm
// `sb-222-255-215-219-auth-token`. Đăng nhập báo thành công, rồi bị đá thẳng
// về `/login` — không thông báo lỗi nào, vì không bên nào coi đó là lỗi.
//
// Ghim tên thì tên cookie không còn phụ thuộc vào chuyện mạng nữa. Đổi IP, thêm
// tên miền, hay đổi cổng nội bộ đều không đụng tới phiên đang mở.
//
// ĐỔI GIÁ TRỊ NÀY LÀ ĐĂNG XUẤT TẤT CẢ MỌI NGƯỜI — cookie cũ thành vô danh.
export const SUPABASE_COOKIE_NAME = "clinicai-auth";
