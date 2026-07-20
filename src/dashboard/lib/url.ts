// Chuẩn hoá link người dùng dán (KQ xét nghiệm…) thành href AN TOÀN.
// Lỗi hay gặp: dán "drive.google.com/..." thiếu scheme → <a href> bị hiểu là đường dẫn
// nội bộ → mở dr4women.vercel.app/drive.google.com/... → 404. Thêm "https://" khi thiếu.
export function toHref(raw?: string | null): string | null {
  const s = (raw ?? "").trim();
  if (!s) return null;
  // Đã có scheme tuyệt đối / mailto / tel / scheme-relative (//host) → giữ nguyên.
  if (/^(https?:\/\/|mailto:|tel:|\/\/)/i.test(s)) return s;
  // Đường dẫn nội bộ thật (bắt đầu bằng 1 dấu /) → giữ nguyên.
  if (s.startsWith("/")) return s;
  // Còn lại (vd "drive.google.com/...", "www.x.com/...") → coi là link ngoài, thêm https.
  return `https://${s}`;
}
