// KIỂM PHIÊN TẠI CHỖ — không hỏi máy chủ xác thực (GoTrue) khi phiên còn hạn.
//
// ── VÌ SAO (đo prod 30/09/2026) ─────────────────────────────────────────────
// `supabase.auth.getUser()` LUÔN gọi mạng tới GoTrue `/auth/v1/user`. Mỗi request
// `/api` chạy nó tới 3 lần (proxy.ts + route + backend-proxy), mỗi lần dựng trang
// 2 lần → 53.430 lời gọi GoTrue / 24 giờ, ~20 lời gọi mỗi phút cho MỘT tab để yên.
// Nhân viên mở nhiều tab cùng tài khoản là con số ấy nhân lên theo.
//
// ── LÀM GÌ ─────────────────────────────────────────────────────────────────
// Token trong cookie là JWT ký HS256 bằng SUPABASE_JWT_SECRET. Ta tự kiểm chữ
// ký + hạn + audience — ĐÚNG như FastAPI đã làm từ trước
// (`clinicai/api/identity.py::verify_supabase_jwt`). Còn hạn → trả người dùng
// ngay, không gọi mạng. Sắp hết hạn / hết hạn / chữ ký sai / thiếu khoá → rơi về
// `getUser()` gốc: nó gọi GoTrue và đổi token mới như trước.
//
// ── CÓ YẾU HƠN KHÔNG ────────────────────────────────────────────────────────
// Không yếu hơn lớp quyết định: FastAPI — nơi mọi luật nằm — vốn chỉ kiểm chữ ký
// JWT, không hỏi GoTrue. Thoát ở tab khác thì token cũ còn đi được tới hết hạn
// (tối đa thời hạn JWT) ở cả hai lớp như nhau; muốn thu hồi tức thì phải làm ở
// FastAPI, không phải ở đây.
//
// Chỉ áp cho lời gọi `getUser()` KHÔNG tham số (đọc từ cookie). Có truyền jwt thì
// để nguyên hành vi gốc.

import type { SupabaseClient, User, UserResponse } from "@supabase/supabase-js";

/** Còn dưới ngần này giây thì để GoTrue đổi token luôn, khỏi dùng token sắp chết. */
export const DU_PHONG_HET_HAN_GIAY = 60;
/** Khớp `SUPABASE_AUDIENCE` phía FastAPI. */
const AUDIENCE = "authenticated";

type Claims = Record<string, unknown> & { sub: string; exp: number };

function tuBase64Url(s: string): Uint8Array<ArrayBuffer> {
  const b64 = s.replace(/-/g, "+").replace(/_/g, "/").padEnd(Math.ceil(s.length / 4) * 4, "=");
  const nhiPhan = atob(b64);
  const out = new Uint8Array(new ArrayBuffer(nhiPhan.length));
  for (let i = 0; i < nhiPhan.length; i++) out[i] = nhiPhan.charCodeAt(i);
  return out;
}

function docJson(phan: string): Record<string, unknown> | null {
  try {
    const v: unknown = JSON.parse(new TextDecoder().decode(tuBase64Url(phan)));
    return v && typeof v === "object" ? (v as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

const khoaDaNap = new Map<string, Promise<CryptoKey>>();
function napKhoa(biMat: string): Promise<CryptoKey> {
  let k = khoaDaNap.get(biMat);
  if (!k) {
    k = crypto.subtle.importKey(
      "raw",
      new TextEncoder().encode(biMat),
      { name: "HMAC", hash: "SHA-256" },
      false,
      ["verify"],
    );
    khoaDaNap.set(biMat, k);
  }
  return k;
}

/**
 * Kiểm một access token. Trả claims nếu chữ ký HS256 đúng, đúng audience, và còn
 * hạn quá `DU_PHONG_HET_HAN_GIAY`; ngược lại trả null. KHÔNG ném — token rác là
 * chuyện thường (cookie cũ, cookie của môi trường khác).
 */
export async function kiemToken(
  token: string,
  biMat: string,
  bayGioGiay: number = Math.floor(Date.now() / 1000),
): Promise<Claims | null> {
  try {
    const phan = token.split(".");
    if (phan.length !== 3) return null;
    const [dau, than, chuKy] = phan;
    if (docJson(dau)?.alg !== "HS256") return null;
    const dung = await crypto.subtle.verify(
      "HMAC",
      await napKhoa(biMat),
      tuBase64Url(chuKy),
      new TextEncoder().encode(`${dau}.${than}`),
    );
    if (!dung) return null;
    const c = docJson(than);
    if (!c || typeof c.sub !== "string" || !c.sub || typeof c.exp !== "number") return null;
    const aud = c.aud;
    if (!(aud === AUDIENCE || (Array.isArray(aud) && aud.includes(AUDIENCE)))) return null;
    if (c.exp - bayGioGiay <= DU_PHONG_HET_HAN_GIAY) return null;
    return c as Claims;
  } catch {
    return null;
  }
}

/** Dựng đối tượng User từ claims — code gọi chỉ đọc `user.id` (đo 30/09), phần
 *  còn lại điền cho đủ kiểu. */
export function nguoiDungTuClaims(c: Claims): User {
  const chuoi = (v: unknown) => (typeof v === "string" ? v : undefined);
  const doiTuong = (v: unknown) =>
    v && typeof v === "object" ? (v as Record<string, unknown>) : {};
  return {
    id: c.sub,
    aud: AUDIENCE,
    role: chuoi(c.role),
    email: chuoi(c.email),
    phone: chuoi(c.phone),
    app_metadata: doiTuong(c.app_metadata),
    user_metadata: doiTuong(c.user_metadata),
    is_anonymous: c.is_anonymous === true,
    created_at: "",
  } as User;
}

/**
 * Gắn kiểm-tại-chỗ vào `client.auth.getUser()`. Trả lại chính client đó.
 * Thiếu SUPABASE_JWT_SECRET (vd máy dev dùng khoá bất đối xứng) → giữ nguyên.
 */
export function ganKiemPhienTaiCho<T extends SupabaseClient>(
  client: T,
  biMat: string | undefined = process.env.SUPABASE_JWT_SECRET,
): T {
  if (!biMat) return client;
  const auth = client.auth;
  const goc = auth.getUser.bind(auth);
  auth.getUser = async (jwt?: string): Promise<UserResponse> => {
    if (jwt === undefined) {
      try {
        // Đọc token từ cookie. Token đã hết hạn thì getSession tự đổi token mới
        // (có gọi mạng) — vẫn đúng, và token mới sẽ qua được bước kiểm bên dưới.
        const { data } = await auth.getSession();
        const token = data.session?.access_token;
        const c = token ? await kiemToken(token, biMat) : null;
        if (c) return { data: { user: nguoiDungTuClaims(c) }, error: null };
      } catch {
        // rơi về đường gốc
      }
    }
    return goc(jwt);
  };
  return client;
}
