// Gửi một thao tác Kho vật tư qua proxy `/api/vat-tu-kho/[action]` (danh sách trắng).
// Máy chủ quyết quyền và luật (số rác 422, tồn âm vẫn xuất được); ở đây chỉ gửi
// và đọc câu trả lời — không luật nghiệp vụ nào trong TSX.

export type KetQuaVatTu = { ok: true; data: unknown } | { ok: false; loi: string };

/** Trạng thái nút lưu theo cùng biên số lượng mà API chấp nhận. Máy chủ vẫn là
 *  nơi quyết định cuối cùng; helper này tránh cho người dùng gửi chắc chắn lỗi. */
export function soLuongPhieuHopLe(loai: string, giaTri: string): boolean {
  const so = giaTri.trim().replace(",", ".");
  if (!/^(?:\d+\.?\d*|\.\d+)$/.test(so)) return false;
  const le = (so.split(".")[1] ?? "").replace(/0+$/, "");
  if (le.length > 3) return false;
  const n = Number(so);
  if (!Number.isFinite(n) || n >= 1e15) return false;
  return n > 0 || (n === 0 && ["KIEM", "DIEU_CHINH"].includes(loai));
}

/** Giá nhập để trống nghĩa là dùng theo danh mục; nếu có thì phải hữu hạn, không âm. */
export function giaNhapPhieuHopLe(giaTri: string): boolean {
  const so = giaTri.trim().replace(",", ".");
  if (!so) return true;
  if (!/^(?:\d+\.?\d*|\.\d+)$/.test(so)) return false;
  const le = (so.split(".")[1] ?? "").replace(/0+$/, "");
  if (le.length > 3) return false;
  const n = Number(so);
  return Number.isFinite(n) && n >= 0 && n < 1e15;
}

/** `khoa` = Idempotency-Key (bắt buộc cho `phieu` và `hoan`): gửi lại cùng khoá =
 *  cùng phiếu, máy chủ không ghi sổ lần hai. */
export async function guiVatTu(
  thaoTac:
    | "phieu"
    | "hoan"
    | "muc-toi-thieu"
    | "nhap-duyet"
    | "nhap-tu-choi"
    | "nhap-rut-lai"
    | "ban-gan-phong"
    | "ban-nhan-lai"
    | "ban-khong-nhan-lai"
    | "ban-hoan-tac"
    | "ban-nhap-bu",
  duLieu: Record<string, unknown>,
  khoa?: string,
): Promise<KetQuaVatTu> {
  try {
    const r = await fetch(`/api/vat-tu-kho/${thaoTac}`, {
      method: thaoTac === "muc-toi-thieu" ? "PUT" : "POST",
      headers: {
        "Content-Type": "application/json",
        ...(khoa ? { "Idempotency-Key": khoa } : {}),
      },
      body: JSON.stringify(duLieu),
    });
    if (r.ok) return { ok: true, data: await r.json().catch(() => null) };
    const d = (await r.json().catch(() => null)) as {
      message?: string;
      detail?: unknown;
      error?: string;
    } | null;
    const chiTiet = typeof d?.detail === "string" ? d.detail : null;
    return { ok: false, loi: d?.message ?? chiTiet ?? d?.error ?? "Máy chủ từ chối." };
  } catch {
    return { ok: false, loi: "Mất kết nối — CHƯA lưu." };
  }
}

/** Số lượng vật tư (tới 3 chữ số lẻ). Máy chủ trả numeric → ép số. */
export const soVatTu = (n: number | string | null | undefined): string =>
  new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 3 }).format(Number(n ?? 0));

export const tienVatTu = (n: number | string | null | undefined): string =>
  n == null ? "—" : `${new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 0 }).format(Number(n))} đ`;

export const khoaMoi = (): string =>
  typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `vt-${Date.now()}-${Math.random().toString(36).slice(2)}`;

type KhoLuuKhoa = Pick<Storage, "getItem" | "setItem" | "removeItem">;
interface KhoaDangCho {
  duLieu: string;
  khoa: string;
  taoLuc: number;
}

const KHOA_PHIEN_PHIEU = "clinicai:kho-vat-tu:phieu-idempotency:v1";
const TTL_KHOA_PHIEN_MS = 24 * 60 * 60 * 1000;

function khoLuuKhoaMacDinh(): KhoLuuKhoa | null {
  try {
    return typeof window === "undefined" ? null : window.sessionStorage;
  } catch {
    return null;
  }
}

/** Giữ cùng key cho cùng body qua reload để retry sau mất phản hồi không ghi phiếu hai lần. */
export function khoaChongGuiTrung(
  duLieu: Record<string, unknown>,
  kho: KhoLuuKhoa | null = khoLuuKhoaMacDinh(),
  bayGio = Date.now(),
): string {
  const duLieuJson = JSON.stringify(duLieu);
  if (!kho) return khoaMoi();
  let ds: KhoaDangCho[] = [];
  try {
    const daLuu = kho.getItem(KHOA_PHIEN_PHIEU);
    const parsed: unknown = daLuu ? JSON.parse(daLuu) : [];
    if (Array.isArray(parsed)) ds = parsed as KhoaDangCho[];
  } catch {
    ds = [];
  }
  const conHan = ds.filter(
    (x) =>
      typeof x?.duLieu === "string" &&
      typeof x?.khoa === "string" &&
      Number.isFinite(x?.taoLuc) &&
      bayGio - x.taoLuc < TTL_KHOA_PHIEN_MS,
  );
  const trung = conHan.find((x) => x.duLieu === duLieuJson);
  if (trung) return trung.khoa;

  const khoa = khoaMoi();
  try {
    kho.setItem(
      KHOA_PHIEN_PHIEU,
      JSON.stringify([...conHan, { duLieu: duLieuJson, khoa, taoLuc: bayGio }].slice(-20)),
    );
  } catch {
    // Cùng phiên vẫn gửi được; API và DB là lớp chống ghi trùng cuối.
  }
  return khoa;
}

export function xoaKhoaChongGuiTrung(
  khoa: string,
  kho: KhoLuuKhoa | null = khoLuuKhoaMacDinh(),
): void {
  if (!kho) return;
  try {
    const daLuu = kho.getItem(KHOA_PHIEN_PHIEU);
    const ds: unknown = daLuu ? JSON.parse(daLuu) : [];
    if (!Array.isArray(ds)) return;
    const conLai = (ds as KhoaDangCho[]).filter((x) => x?.khoa !== khoa);
    if (conLai.length) kho.setItem(KHOA_PHIEN_PHIEU, JSON.stringify(conLai));
    else kho.removeItem(KHOA_PHIEN_PHIEU);
  } catch {
    // Không làm hỏng giao dịch đã được máy chủ xác nhận.
  }
}
