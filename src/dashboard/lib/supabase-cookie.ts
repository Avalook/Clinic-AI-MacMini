// Tên cookie phiên đăng nhập.
//
// ── VÌ SAO KHÔNG ĐỂ @supabase/ssr TỰ ĐẶT TÊN ────────────────────────────────
//
// Mặc định nó suy tên cookie ra từ hostname của URL Supabase. Mà hai phía dùng
// hai URL khác nhau, bắt buộc phải khác:
//
//   máy chủ    SUPABASE_URL             http://clinicai_supabase_gateway:8000
//   trình duyệt URL công khai (PUBLIC_SUPABASE_URL) http://222.255.215.219
//
// Để mặc định thì server action đăng nhập ghi cookie
// `sb-clinicai_supabase_gateway-auth-token`, còn proxy và trình duyệt đi tìm
// `sb-222-255-215-219-auth-token`. Đăng nhập báo thành công, rồi bị đá thẳng
// về `/login` — không thông báo lỗi nào, vì không bên nào coi đó là lỗi.
//
// ── VÌ SAO PROD VÀ STAGING PHẢI KHÁC TÊN (14/08/2026) ──────────────────────
//
// Tuyền: *"chưa có tên miền nên nếu mở 2 tab thì nó bị trùng"*.
//
// COOKIE KHÔNG PHÂN BIỆT CỔNG. Đây là quy định của chính chuẩn cookie
// (RFC 6265 §8.5) và là chỗ ai cũng đoán sai: `http://IP:80` và `http://IP:8080`
// là hai ORIGIN khác nhau với mọi thứ khác — nhưng dùng CHUNG một hũ cookie.
// Hai môi trường đang nằm đúng như thế:
//
//   prod     http://222.255.215.219        (cổng 80)
//   staging  http://222.255.215.219:8080
//
// Cùng một tên cookie ghim cứng ⇒ đăng nhập staging là GHI ĐÈ phiên prod. Tệ
// hơn: hai môi trường có hai máy chủ xác thực riêng với hai khoá ký khác nhau,
// nên tab prod cầm token của staging sẽ bị từ chối — người dùng thấy mình vừa
// bị đăng xuất khỏi prod mà không hiểu vì sao.
//
// Có tên miền riêng thì hết trùng (khác host = khác hũ). Chưa có thì tách bằng
// TÊN COOKIE, và cổng là thứ duy nhất phân biệt được hai môi trường ở đây.
//
// PROD GIỮ NGUYÊN TÊN CŨ, có chủ ý: đổi tên cookie là đăng xuất tất cả mọi
// người. Prod không có cổng trong URL nên rơi vào nhánh không hậu tố, tên ra
// đúng bằng chuỗi cũ. Chỉ staging đổi tên — và ở staging thì đăng xuất một lần
// là cái giá đúng phải trả.

import { cauHinhCongKhai } from "./cau-hinh-cong-khai.ts";

/** Hậu tố phân biệt môi trường, suy từ CỔNG mà trình duyệt gọi tới.
 *
 *  Cổng mặc định (rỗng, 80, 443) → không hậu tố, giữ nguyên tên lịch sử.
 *  URL hỏng hoặc thiếu → cũng không hậu tố: thà hai môi trường trùng nhau như
 *  cũ còn hơn sinh ra một tên cookie mà phía kia không đoán được.
 */
export function hauToTheoCong(url: string | undefined): string {
  if (!url) return "";
  let cong = "";
  try {
    cong = new URL(url).port;
  } catch {
    return "";
  }
  if (!cong || cong === "80" || cong === "443") return "";
  return `-${cong}`;
}

// HAI PHÍA PHẢI RA CÙNG MỘT TÊN. Từ 01/10/2026 URL công khai không còn nung
// vào bundle lúc build mà đọc LÚC CHẠY (lib/cau-hinh-cong-khai.ts): máy chủ đọc
// env của container, trình duyệt nhận đúng giá trị ấy qua layout gốc. Một nguồn
// cho cả hai phía nên tên khớp nhau. Là HÀM (không phải hằng cấp module) vì phía
// trình duyệt module có thể được nạp trước khi cấu hình được đặt.
export function tenCookieSupabase(): string {
  return "clinicai-auth" + hauToTheoCong(cauHinhCongKhai().supabaseUrl);
}
