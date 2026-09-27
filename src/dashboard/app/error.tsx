"use client"; // Error boundary bắt buộc là Client Component.

// LƯỚI Ở GỐC — bắt lỗi ném từ LAYOUT của khu (dashboard).
//
// `(dashboard)/error.tsx` chỉ bọc TRANG, không bọc `(dashboard)/layout.tsx` cùng
// cấp. Từ 27/09/2026 layout ném lỗi khi máy chủ bận (429 / 5xx lúc deploy, DB
// treo) thay vì đá người dùng về /login giữa ca — lỗi ấy rơi lên đây. Không có
// file này thì Next hiện trang lỗi mặc định tiếng Anh nền tối.
//
// Next 16: prop thử lại tên `unstable_retry` (xem `(dashboard)/error.tsx`).

import { useEffect } from "react";

import Button, { buttonClass } from "@/components/ui/Button";

export default function GocError({
  error,
  unstable_retry,
}: {
  error: Error & { digest?: string };
  unstable_retry: () => void;
}) {
  useEffect(() => {
    console.error("[goc] lỗi khi dựng trang:", error);
    // Gửi về KHO LỖI (27/09/2026) — /ops tab "Lỗi & cảnh báo". Hỏng thì im.
    void fetch("/api/loi", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        vi_tri: window.location.pathname,
        kieu: error.name || "Error",
        thong_diep: `${error.message}${error.digest ? ` (digest ${error.digest})` : ""}`,
      }),
    }).catch(() => undefined);
  }, [error]);

  return (
    <main className="mx-auto max-w-lg px-4 py-16">
      <div className="space-y-4 rounded-card border border-line bg-surface p-6 shadow-card">
        <h1 className="text-title font-semibold text-ink">Máy chủ đang bận</h1>
        <p className="text-body text-ink-muted">
          Bạn vẫn đang đăng nhập. Hệ thống đang cập nhật hoặc quá tải trong giây lát — bấm
          “Thử lại” sau vài giây. Thao tác vừa rồi có thể đã được lưu, kiểm tra trước khi làm
          lại.
        </p>
        {error.digest ? (
          <p className="text-meta text-ink-faint">Mã lỗi: {error.digest.slice(0, 8)}</p>
        ) : null}
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="primary" onClick={() => unstable_retry()}>
            Thử lại
          </Button>
          <a href="/login" className={buttonClass("ghost", "md")}>
            Đăng nhập lại
          </a>
        </div>
      </div>
    </main>
  );
}
