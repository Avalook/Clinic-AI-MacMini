"use client"; // Error boundary bắt buộc là Client Component.

// LƯỚI CUỐI CÙNG CHO CẢ KHU (dashboard).
//
// Trước file này, một lỗi ném ra giữa lúc render server component đi thẳng tới
// trang lỗi mặc định của Next: nền tối, chữ tiếng Anh, một nút "Try again".
// Nhân viên phòng khám gặp nó ngay sau khi bấm "Đặt lịch hẹn" — trong khi lịch
// ĐÃ được lưu — nên đọc màn hình đó là hiểu "đặt hỏng rồi", bấm lại, và chỉ có
// khoá idempotency phía backend chặn được lịch thứ hai.
//
// Nguyên nhân gốc của lần đó đã vá ở `lib/backend-proxy.ts` (xoay refresh
// token). File này là lớp thứ hai: từ nay BẤT KỲ lỗi nào cũng hiện ra bằng
// tiếng Việt, nói rõ việc vừa làm có thể đã lưu, và cho một nút thử lại không
// mất trang.
//
// NEXT 16 ĐỔI TÊN PROP: `reset` → `unstable_retry`
// (node_modules/next/dist/docs/01-app/03-api-reference/03-file-conventions/error.md).
// Viết `reset` thì nút bấm không làm gì cả mà TypeScript vẫn qua, vì prop thừa
// chỉ đơn giản là undefined.

import { useEffect } from "react";
import { AlertTriangle, RotateCw, Home } from "lucide-react";

export default function DashboardError({
  error,
  unstable_retry,
}: {
  error: Error & { digest?: string };
  unstable_retry: () => void;
}) {
  useEffect(() => {
    // Vào log container — nơi duy nhất còn nhìn được, vì Sentry chưa cài
    // (`sentry-sdk` thiếu trong pyproject.toml, xem docs/DANG-LAM.md §4).
    console.error("[dashboard] lỗi khi dựng trang:", error);
  }, [error]);

  return (
    <div className="mx-auto max-w-lg py-10">
      <div className="space-y-4 rounded-2xl border border-line bg-surface p-6 shadow-card">
        <div className="flex items-start gap-3.5">
          <div className="grid size-11 shrink-0 place-items-center rounded-2xl bg-danger-bg text-danger">
            <AlertTriangle className="size-5" />
          </div>
          <div className="space-y-1">
            <h2 className="text-base font-bold text-ink">
              Màn hình gặp trục trặc
            </h2>
            <p className="text-sm text-ink-muted">
              Thao tác vừa rồi có thể <strong>đã được lưu</strong>. Bấm “Thử
              lại” để tải lại màn hình và kiểm tra trước khi làm lần nữa.
            </p>
          </div>
        </div>

        <div className="flex flex-wrap gap-2.5">
          <button
            type="button"
            onClick={() => unstable_retry()}
            className="inline-flex items-center gap-2 rounded-2xl bg-brand-600 py-2.5 px-4 text-xs font-bold text-white shadow-xs transition-all hover:bg-brand-700"
          >
            <RotateCw className="size-4" />
            Thử lại
          </button>
          <a
            href="/home"
            className="inline-flex items-center gap-2 rounded-2xl border border-line bg-surface py-2.5 px-4 text-xs font-bold text-ink transition-all hover:bg-brand-50"
          >
            <Home className="size-4" />
            Về trang chủ
          </a>
        </div>

        {/* Mã lỗi để đối chiếu với log máy chủ. KHÔNG in `error.message`: trên
            bản dựng production Next đã thay nó bằng chuỗi chung, còn ở môi
            trường khác nó có thể mang theo dữ liệu bệnh nhân. */}
        {error.digest ? (
          <p className="border-t border-line pt-3 text-[11px] text-ink-muted">
            Mã lỗi: <code className="font-mono">{error.digest}</code> — đọc cho
            người hỗ trợ kỹ thuật để tra đúng dòng log.
          </p>
        ) : null}
      </div>
    </div>
  );
}
