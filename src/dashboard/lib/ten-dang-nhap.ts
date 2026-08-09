// TÊN ĐĂNG NHẬP — người dùng gõ tên trần, hệ thống tự gắn đuôi.
//
// Quang, 09/08/2026: *"tạm thời cứ bỏ @ đuôi mail đã, để tên đăng nhập sửa như
// nào cũng được"*.
//
// VÌ SAO KHÔNG BỎ HẲN ĐUÔI. GoTrue (tầng đăng nhập) lưu danh tính trong cột
// `email` và tự kiểm định dạng email — gửi "cskhdieuhoa" lên là nó trả 422, dù
// ta có bỏ mọi kiểm ở phía mình. Nên đuôi vẫn còn, chỉ là KHÔNG AI PHẢI GÕ NÓ
// NỮA: màn quản trị và màn đăng nhập cùng gọi `emailTuTenDangNhap`, nên "cskh
// dieuhoa" ở ô đổi tên và "cskhdieuhoa" ở ô đăng nhập ra cùng một địa chỉ.
//
// MỘT HÀM CHO CẢ HAI ĐẦU là điều kiện để chuyện này đúng. Nếu chỉ nới ở màn
// quản trị, quản lý đặt được nick trần rồi nhân viên gõ đúng nick ấy vào màn
// đăng nhập và bị từ chối — tệ hơn hẳn so với trước khi nới.

/** Đuôi gắn thêm khi người dùng gõ tên trần. Đổi được bằng biến môi trường để
 *  phòng khám khác không phải sửa code; mặc định theo Dr4Women. */
export const DUOI_TEN_DANG_NHAP =
  process.env.NEXT_PUBLIC_DUOI_TEN_DANG_NHAP?.trim() || "dr4women.vn";

/** Tên đăng nhập → địa chỉ GoTrue thật.
 *
 *  Có sẵn "@" thì GIỮ NGUYÊN: trên prod đang có cả `@dr4women.vn` lẫn
 *  `@dr4women.local`, và ép mọi thứ về một đuôi là khoá cửa những tài khoản
 *  đuôi kia. Trả "" khi rỗng để nơi gọi tự báo lỗi. */
export function emailTuTenDangNhap(nick: string): string {
  const s = (nick ?? "").trim().toLowerCase();
  if (!s) return "";
  return s.includes("@") ? s : `${s}@${DUOI_TEN_DANG_NHAP}`;
}

/** Tên đăng nhập có hợp lệ không (sau khi đã gắn đuôi). `null` = hợp lệ.
 *
 *  Chỉ chặn những thứ GoTrue chắc chắn từ chối, không chặn theo "trông giống
 *  email hay không" — đó đúng là cái luật vừa bỏ. */
export function loiTenDangNhap(nick: string): string | null {
  const s = (nick ?? "").trim();
  if (!s) return "Nhập tên đăng nhập.";
  if (/\s/.test(s)) return "Tên đăng nhập không được có dấu cách.";
  const email = emailTuTenDangNhap(s);
  // Phần trước "@" phải có gì đó, và chỉ được có ĐÚNG một "@".
  if (email.split("@").length !== 2 || email.startsWith("@")) {
    return "Tên đăng nhập không hợp lệ.";
  }
  return null;
}
