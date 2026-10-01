/**
 * Dải "đây là bản THỬ" ở đầu mọi trang — CHỈ hiện ở staging (01/10/2026).
 *
 * Staging dùng chung tài khoản/mật khẩu với prod và giao diện y hệt, nên người
 * dùng rất dễ quên mình đang ở đâu: tưởng staging là thật (ghi chú cho khách
 * thật vào bản thử) hoặc tưởng prod là bản thử (bấm "nghịch" trên dữ liệu thật).
 * Dải này luôn nằm trên cùng, không bấm trúng được (pointer-events-none) để
 * không che nút của header, và không in ra giấy.
 *
 * Bật bằng NEXT_PUBLIC_APP_ENV=staging — nung vào bundle lúc dựng ảnh (compose
 * lấy từ APP_ENV của chính môi trường). Prod dựng với "production" → không hiện.
 * Màu: cặp token warning sẵn có (DESIGN.md §2), chữ bậc `meta`.
 */
export function DaiStaging() {
  if (process.env.NEXT_PUBLIC_APP_ENV !== "staging") return null;
  return (
    <div
      role="note"
      aria-label="Bản thử staging"
      className="pointer-events-none fixed inset-x-0 top-0 z-50 flex justify-center print:hidden"
    >
      <div className="h-0.5 w-full bg-warning absolute inset-x-0 top-0" />
      <span className="rounded-b-chip bg-warning-bg px-3 py-0.5 text-meta font-semibold text-warning shadow-panel">
        STAGING — bản thử, dữ liệu khách đã che
      </span>
    </div>
  );
}
