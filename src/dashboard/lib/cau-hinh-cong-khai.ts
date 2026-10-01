// CẤU HÌNH CÔNG KHAI — nạp LÚC CHẠY, không nung vào ảnh (01/10/2026).
//
// ── VÌ SAO ──────────────────────────────────────────────────────────────────
//
// Trước đây năm giá trị dưới đây là `NEXT_PUBLIC_*`: Next thay chúng thành chuỗi
// cố định TRONG LÚC `next build`. Hệ quả: ảnh dashboard của staging khác ảnh của
// prod (URL Supabase, khoá anon, dải STAGING), nên mỗi nơi phải tự dựng lại
// 3–4 phút — và ảnh chạy cho khách KHÔNG phải ảnh đã thử trên staging.
//
// Giờ: một ảnh, chạy mọi nơi. Máy chủ đọc biến môi trường của container lúc
// chạy; trình duyệt nhận đúng các giá trị ấy qua `window.__CAU_HINH_CONG_KHAI__`
// do layout gốc in ra (app/layout.tsx) + `NapCauHinhCongKhai` đặt lúc render.
//
// ── CHỈ GIÁ TRỊ CÔNG KHAI ──────────────────────────────────────────────────
//
// Mọi thứ ở đây đi thẳng vào HTML của MỌI trang, kể cả /login chưa đăng nhập.
// Kiểu `CauHinhCongKhai` liệt kê TỪNG trường; không bao giờ trải cả
// `process.env` ra. Khoá anon là khoá công khai theo thiết kế của Supabase (RLS
// gác) — khoá service_role, JWT secret, khoá API backend KHÔNG BAO GIỜ vào đây.
// Bài kiểm: tests/cau-hinh-luc-chay-boundary.test.mts.
//
// ── KHÔNG VIẾT `process.env.NEXT_PUBLIC_…` NGUYÊN VĂN ───────────────────────
//
// Next thay mọi chỗ viết nguyên văn dạng ấy (cả phía máy chủ) bằng giá trị lúc
// build. Đọc qua `docEnv(ten)` (khoá động) thì Next không đụng tới, giá trị là
// của container đang chạy. Tên NEXT_PUBLIC_* cũ vẫn được đọc làm đường lùi
// (máy dev / .env.prod hiện có), nhưng chỉ qua khoá động.

export type CauHinhCongKhai = {
  /** Địa chỉ Supabase TRÌNH DUYỆT gọi (khác SUPABASE_URL nội bộ của container). */
  supabaseUrl: string;
  /** Khoá anon (công khai, RLS gác). */
  supabaseAnonKey: string;
  /** "production" | "staging" | … — "staging" thì hiện dải STAGING. */
  appEnv: string;
  /** Công tắc mở quyền tạm thời — nửa giao diện; cùng biến với máy chủ. */
  moQuyenTamThoi: boolean;
  /** Đuôi gắn vào tên đăng nhập trần. */
  duoiTenDangNhap: string;
};

export const KHOA_WINDOW_CAU_HINH = "__CAU_HINH_CONG_KHAI__";

const DUOI_MAC_DINH = "dr4women.vn";

function docEnv(...ten: string[]): string | undefined {
  // Khoá động — Next không thay được lúc build (xem đầu tệp).
  const env: Record<string, string | undefined> =
    typeof process !== "undefined" && process.env ? process.env : {};
  for (const t of ten) {
    const v = env[t];
    if (v !== undefined && v.trim() !== "") return v.trim();
  }
  return undefined;
}

/** Bật/tắt từ chuỗi biến môi trường. Thiếu biến thì TẮT (hỏng thì đóng). */
export function laBat(v: string | undefined): boolean {
  return ["1", "true", "yes"].includes((v ?? "0").trim().toLowerCase());
}

/** Đọc cấu hình từ biến môi trường LÚC GỌI (phía máy chủ). */
export function cauHinhTuMoiTruong(): CauHinhCongKhai {
  return {
    // Thứ tự như build arg cũ trong docker-compose.yml: tên công khai trước,
    // SUPABASE_URL (địa chỉ nội bộ) chỉ là đường lùi khi chạy ngoài container.
    supabaseUrl:
      docEnv("PUBLIC_SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_URL", "SUPABASE_URL") ?? "",
    supabaseAnonKey:
      docEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "SUPABASE_ANON_KEY") ?? "",
    appEnv: docEnv("APP_ENV", "NEXT_PUBLIC_APP_ENV") ?? "production",
    moQuyenTamThoi: laBat(
      docEnv("MO_QUYEN_TAM_THOI", "NEXT_PUBLIC_MO_QUYEN_TAM_THOI") ?? "0",
    ),
    duoiTenDangNhap:
      docEnv("DUOI_TEN_DANG_NHAP", "NEXT_PUBLIC_DUOI_TEN_DANG_NHAP") ?? DUOI_MAC_DINH,
  };
}

let daNap: CauHinhCongKhai | null = null;

/** Phía trình duyệt: ghi nhận cấu hình máy chủ gửi xuống (NapCauHinhCongKhai). */
export function datCauHinhCongKhai(c: CauHinhCongKhai): void {
  if (typeof window === "undefined") return; // máy chủ luôn đọc env lúc gọi
  daNap = c;
}

/** Cấu hình công khai hiện hành — gọi LÚC DÙNG, đừng chụp vào hằng cấp module.
 *
 *  Máy chủ: đọc env mỗi lần gọi. Trình duyệt: giá trị NapCauHinhCongKhai đã đặt,
 *  hoặc `window.__CAU_HINH_CONG_KHAI__` do layout gốc in vào <head>. */
export function cauHinhCongKhai(): CauHinhCongKhai {
  if (typeof window === "undefined") return cauHinhTuMoiTruong();
  if (daNap) return daNap;
  const w = (window as unknown as Record<string, unknown>)[KHOA_WINDOW_CAU_HINH];
  if (w && typeof w === "object") {
    daNap = w as CauHinhCongKhai;
    return daNap;
  }
  // Không có (trang lỗi tĩnh, bài kiểm) — giá trị rỗng, không bịa.
  return cauHinhTuMoiTruong();
}

/** Mã JS đặt cấu hình lên window — an toàn để nhúng trong <script>.
 *
 *  `JSON.stringify` không thoát `<`: một giá trị chứa `</script>` sẽ đóng thẻ
 *  sớm. Thoát `<`, `>`, `&` và hai ký tự xuống dòng mà JS cũ không chấp nhận
 *  trong chuỗi. Chỉ nhận đúng kiểu CauHinhCongKhai, chép TỪNG trường. */
export function maScriptCauHinh(c: CauHinhCongKhai): string {
  const chiCongKhai: CauHinhCongKhai = {
    supabaseUrl: c.supabaseUrl,
    supabaseAnonKey: c.supabaseAnonKey,
    appEnv: c.appEnv,
    moQuyenTamThoi: c.moQuyenTamThoi,
    duoiTenDangNhap: c.duoiTenDangNhap,
  };
  const json = JSON.stringify(chiCongKhai)
    .replace(/</g, "\\u003c")
    .replace(/>/g, "\\u003e")
    .replace(/&/g, "\\u0026")
    .replace(/ /g, "\\u2028")
    .replace(/ /g, "\\u2029");
  return `window.${KHOA_WINDOW_CAU_HINH}=${json};`;
}
