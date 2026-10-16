// Gửi một thao tác Kho vật tư qua proxy `/api/vat-tu-kho/[action]` (danh sách trắng).
// Máy chủ quyết quyền và luật (số rác 422, tồn âm vẫn xuất được); ở đây chỉ gửi
// và đọc câu trả lời — không luật nghiệp vụ nào trong TSX.

export type KetQuaVatTu = { ok: true; data: unknown } | { ok: false; loi: string };

/** `khoa` = Idempotency-Key (bắt buộc cho `phieu` và `hoan`): gửi lại cùng khoá =
 *  cùng phiếu, máy chủ không ghi sổ lần hai. */
export async function guiVatTu(
  thaoTac: "phieu" | "hoan" | "muc-toi-thieu" | "nhap-duyet" | "nhap-tu-choi" | "nhap-rut-lai",
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
