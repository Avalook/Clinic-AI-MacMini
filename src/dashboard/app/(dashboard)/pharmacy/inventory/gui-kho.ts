// Gửi một thao tác kho qua proxy `/api/pharmacy/[action]` (danh sách trắng).
// Máy chủ quyết định quyền và luật; ở đây chỉ gửi và đọc câu trả lời.

export type KetQuaKho = { ok: true } | { ok: false; loi: string };

export async function guiKho(
  thaoTac: "luu-thuoc" | "receive" | "adjust" | "discard",
  duLieu: Record<string, unknown>,
): Promise<KetQuaKho> {
  try {
    const r = await fetch(`/api/pharmacy/${thaoTac}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(duLieu),
    });
    if (r.ok) return { ok: true };
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
