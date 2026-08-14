// Tên cookie phiên đăng nhập.
//
// ── VÌ SAO KHÔNG ĐỂ @supabase/ssr TỰ ĐẶT TÊN ────────────────────────────────
//
// Mặc định nó suy tên cookie ra từ hostname của URL Supabase. Mà hai phía dùng
// hai URL khác nhau, bắt buộc phải khác:
//
//   máy chủ    SUPABASE_URL             http://clinicai_supabase_gateway:8000
//   trình duyệt NEXT_PUBLIC_SUPABASE_URL http://222.255.215.219
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

// PHẢI viết nguyên văn `process.env.NEXT_PUBLIC_SUPABASE_URL` ở đây. Next chỉ
// thay giá trị vào bundle trình duyệt khi thấy đúng dạng truy cập thuộc tính
// này; gán qua biến trung gian thì phía trình duyệt nhận `undefined`, tên cookie
// hai bên lệch nhau, và ta quay lại đúng lỗi "đăng nhập xong bị đá về /login"
// mô tả ở đầu tệp.
//
// Giá trị có ở CẢ hai nơi: build arg (nung vào bundle) và env_file lúc chạy
// (cho phía máy chủ) — xem docker-compose.yml. Hai bên vì thế luôn ra cùng tên.
export const SUPABASE_COOKIE_NAME =
  "clinicai-auth" + hauToTheoCong(process.env.NEXT_PUBLIC_SUPABASE_URL);
