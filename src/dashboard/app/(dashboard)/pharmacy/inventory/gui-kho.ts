// Gửi một thao tác kho qua proxy `/api/pharmacy/[action]` (danh sách trắng).
// Máy chủ quyết định quyền và luật; ở đây chỉ gửi và đọc câu trả lời.

export type KetQuaKho = { ok: true; data: unknown } | { ok: false; loi: string };

const CAN_GUI_LAI_AN_TOAN = new Set(["receive", "adjust", "discard"]);
const KHOA_CHO_GUI = "clinicai:pharmacy-pending:";
const LOI_KHONG_LUU_DUOC_KHOA =
  "Không lưu được mã chống gửi trùng — thao tác chưa được gửi. Hãy bật lưu trữ trình duyệt rồi thử lại.";
const dangTaoKhoa = new Map<
  string,
  {
    raw: string;
    promise: Promise<{ khoa: string; khoaLuu: string; khoaTrongTab: string }>;
    dangGui: number;
    coLoi: boolean;
  }
>();

function idNgauNhien(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  const bytes = new Uint8Array(16);
  if (typeof crypto !== "undefined" && typeof crypto.getRandomValues === "function") {
    crypto.getRandomValues(bytes);
  } else {
    for (let i = 0; i < bytes.length; i++) bytes[i] = Math.floor(Math.random() * 256);
  }
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

function chuanHoa(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(chuanHoa);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([k, v]) => [k, chuanHoa(v)]),
    );
  }
  return value;
}

async function bamPayload(data: Record<string, unknown>): Promise<string> {
  const raw = JSON.stringify(chuanHoa(data));
  if (typeof crypto !== "undefined" && crypto.subtle) {
    const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(raw));
    return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
  }
  // Fallback chỉ dùng để tạo khoá cục bộ; máy chủ vẫn kiểm payload SHA-256.
  let hash = 2166136261;
  for (let i = 0; i < raw.length; i++) hash = Math.imul(hash ^ raw.charCodeAt(i), 16777619);
  return (hash >>> 0).toString(16).padStart(8, "0");
}

async function khoaChoGuiLai(
  thaoTac: string,
  duLieu: Record<string, unknown>,
): Promise<{ khoa: string; khoaLuu: string; khoaTrongTab: string }> {
  const raw = JSON.stringify(chuanHoa(duLieu));
  let hashNhanh = 2166136261;
  for (let i = 0; i < raw.length; i++) {
    hashNhanh = Math.imul(hashNhanh ^ raw.charCodeAt(i), 16777619);
  }
  const goc = `${thaoTac}:${(hashNhanh >>> 0).toString(16)}:${raw.length}`;
  let khoaTrongTab = goc;
  let hauTo = 0;
  while (dangTaoKhoa.has(khoaTrongTab) && dangTaoKhoa.get(khoaTrongTab)?.raw !== raw) {
    khoaTrongTab = `${goc}:${++hauTo}`;
  }
  const truoc = dangTaoKhoa.get(khoaTrongTab);
  if (truoc?.raw === raw) return truoc.promise;

  const promise = (async () => {
    const khoaLuu = `${KHOA_CHO_GUI}${thaoTac}:${await bamPayload(duLieu)}`;
    try {
      const daLuu = window.sessionStorage.getItem(khoaLuu);
      if (daLuu) return { khoa: daLuu, khoaLuu, khoaTrongTab };
      const khoa = idNgauNhien();
      window.sessionStorage.setItem(khoaLuu, khoa);
      return { khoa, khoaLuu, khoaTrongTab };
    } catch {
      throw new Error(LOI_KHONG_LUU_DUOC_KHOA);
    }
  })();
  dangTaoKhoa.set(khoaTrongTab, { raw, promise, dangGui: 0, coLoi: false });
  try {
    return await promise;
  } catch (error) {
    dangTaoKhoa.delete(khoaTrongTab);
    throw error;
  }
}

function xoaKhoaChoGuiLai(khoaLuu: string, khoaTrongTab: string): void {
  dangTaoKhoa.delete(khoaTrongTab);
  try {
    window.sessionStorage.removeItem(khoaLuu);
  } catch {
    // Không giữ key trong bộ nhớ nếu sessionStorage bị chặn.
  }
}

function batDauGuiLai(khoaTrongTab: string): void {
  const pending = dangTaoKhoa.get(khoaTrongTab);
  if (!pending) return;
  if (pending.dangGui === 0) pending.coLoi = false;
  pending.dangGui += 1;
}

function ketThucGuiLai(
  khoaLuu: string,
  khoaTrongTab: string,
  thanhCong: boolean,
): void {
  const pending = dangTaoKhoa.get(khoaTrongTab);
  if (!pending) return;
  if (!thanhCong) pending.coLoi = true;
  pending.dangGui = Math.max(0, pending.dangGui - 1);
  if (pending.dangGui === 0 && !pending.coLoi) {
    xoaKhoaChoGuiLai(khoaLuu, khoaTrongTab);
  }
}

/** `khoa` = Idempotency-Key (phiếu nhập / kiểm kho bắt buộc): gửi lại cùng khoá
 *  = cùng phiếu, máy chủ không ghi sổ lần hai. */
export async function guiKho(
  thaoTac: "luu-thuoc" | "receive" | "adjust" | "discard" | "gan-lo" | "phieu-nhap" | "kiem-kho" | "sua-lo" | "huy-lo-het-han" | "hoan-huy-lo" | "so-ngay-canh-bao" | "gan-ma-vach" | "go-ma-vach" | "chuyen-kho" | "hoan-tac-chuyen-kho" | "tach-kho-quay",
  duLieu: Record<string, unknown>,
  khoa?: string,
): Promise<KetQuaKho> {
  let khoaGui = khoa;
  let khoaLuu: string | undefined;
  let khoaTrongTab: string | undefined;
  let daBatDauGui = false;
  let guiThanhCong = false;
  try {
    if (!khoaGui && CAN_GUI_LAI_AN_TOAN.has(thaoTac)) {
      const pending = await khoaChoGuiLai(thaoTac, duLieu);
      khoaGui = pending.khoa;
      khoaLuu = pending.khoaLuu;
      khoaTrongTab = pending.khoaTrongTab;
      batDauGuiLai(khoaTrongTab);
      daBatDauGui = true;
    }
    const r = await fetch(`/api/pharmacy/${thaoTac}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(khoaGui ? { "Idempotency-Key": khoaGui } : {}),
      },
      body: JSON.stringify(duLieu),
    });
    if (r.ok) {
      const data = await r.json();
      guiThanhCong = true;
      return { ok: true, data };
    }
    const d = (await r.json().catch(() => null)) as {
      message?: string;
      detail?: unknown;
      error?: string;
    } | null;
    const chiTiet = typeof d?.detail === "string" ? d.detail : null;
    return { ok: false, loi: d?.message ?? chiTiet ?? d?.error ?? "Máy chủ từ chối." };
  } catch (error) {
    if (error instanceof Error && error.message === LOI_KHONG_LUU_DUOC_KHOA) {
      return { ok: false, loi: error.message };
    }
    return { ok: false, loi: "Mất kết nối — CHƯA lưu." };
  } finally {
    if (daBatDauGui && khoaLuu && khoaTrongTab) {
      ketThucGuiLai(khoaLuu, khoaTrongTab, guiThanhCong);
    }
  }
}

/** Đọc một đường GET của proxy `/api/pharmacy/[action]` (quét mã, dữ liệu tem). */
export async function docKho<T>(
  thaoTac: "tra-ma" | "tem-lo",
  thamSo: Record<string, string>,
): Promise<{ ok: true; data: T } | { ok: false; loi: string }> {
  try {
    const r = await fetch(`/api/pharmacy/${thaoTac}?${new URLSearchParams(thamSo)}`, {
      cache: "no-store",
    });
    if (r.ok) return { ok: true, data: (await r.json()) as T };
    const d = (await r.json().catch(() => null)) as { message?: string; error?: string } | null;
    return { ok: false, loi: d?.message ?? d?.error ?? "Máy chủ từ chối." };
  } catch {
    return { ok: false, loi: "Mất kết nối — chưa tra được mã." };
  }
}

export const tienVnd = (n: number | null | undefined): string =>
  n == null ? "—" : `${new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 0 }).format(n)} đ`;

/** Tồn tách theo đơn vị lô — "20 hộp · 48 viên" (máy chủ không cộng hộp với
 *  viên, 29/09/2026). Rỗng → "0". */
export const tonTheoDonVi = (
  ds: { don_vi: string | null; ton: number | string }[] | null | undefined,
): string =>
  ds && ds.length > 0
    ? ds.map((x) => `${soKho(x.ton)} ${x.don_vi ?? ""}`.trim()).join(" · ")
    : "0";

/** Số lượng kho (tới 3 chữ số lẻ). Máy chủ trả numeric dạng chuỗi → ép số. */
export const soKho = (n: number | string | null | undefined): string =>
  new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 3 }).format(Number(n ?? 0));
