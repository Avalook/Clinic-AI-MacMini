// Gọi proxy `/api/thuoc/[action]` (gợi ý tên, nhờ kho, xoá thuốc — 26/11/2026).
// Máy chủ quyết luật và quyền; ở đây chỉ gửi và đọc câu trả lời.

export type KetQuaThuoc<T> = { ok: true; data: T } | { ok: false; loi: string };

export interface GoiYThuoc {
  drug_catalog_id: string;
  ten: string;
  biet_duoc: string | null;
}

export interface YeuCauNhoKho {
  id: string;
  ten_go: string;
  ghi_chu: string | null;
  tao_luc: string;
  nguoi_nho: string | null;
  nguoi_xong: string | null;
  xong: boolean;
}

export async function goiThuoc<T>(
  action: string,
  { query, body }: { query?: Record<string, string>; body?: unknown } = {},
): Promise<KetQuaThuoc<T>> {
  const qs = query ? `?${new URLSearchParams(query)}` : "";
  try {
    const r = await fetch(`/api/thuoc/${action}${qs}`, {
      method: body === undefined ? "GET" : "POST",
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      cache: "no-store",
    });
    const d = (await r.json().catch(() => null)) as (T & { message?: string; error?: string; detail?: unknown }) | null;
    if (r.ok && d) return { ok: true, data: d };
    const chiTiet = typeof d?.detail === "string" ? d.detail : null;
    return { ok: false, loi: d?.message ?? chiTiet ?? d?.error ?? "Máy chủ từ chối." };
  } catch {
    return { ok: false, loi: "Mất kết nối — chưa gửi được." };
  }
}
