// Gửi một thao tác kho qua proxy `/api/pharmacy/[action]` (danh sách trắng).
// Máy chủ quyết định quyền và luật; ở đây chỉ gửi và đọc câu trả lời.

export type KetQuaKho = { ok: true; data: unknown } | { ok: false; loi: string };

/** `khoa` = Idempotency-Key (phiếu nhập / kiểm kho bắt buộc): gửi lại cùng khoá
 *  = cùng phiếu, máy chủ không ghi sổ lần hai. */
export async function guiKho(
  thaoTac: "luu-thuoc" | "receive" | "adjust" | "discard" | "gan-lo" | "phieu-nhap" | "kiem-kho",
  duLieu: Record<string, unknown>,
  khoa?: string,
): Promise<KetQuaKho> {
  try {
    const r = await fetch(`/api/pharmacy/${thaoTac}`, {
      method: "POST",
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

export const tienVnd = (n: number | null | undefined): string =>
  n == null ? "—" : `${new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 0 }).format(n)} đ`;

/** Số lượng kho (tới 3 chữ số lẻ). Máy chủ trả numeric dạng chuỗi → ép số. */
export const soKho = (n: number | string | null | undefined): string =>
  new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 3 }).format(Number(n ?? 0));
