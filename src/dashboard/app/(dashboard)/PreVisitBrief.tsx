"use client";

// Nút "Xem tóm tắt trước khám" cho BÁC SĨ. Bấm → gọi proxy /api/brief/[id]
// (proxy này gọi tiếp FastAPI). Chỉ gọi-và-hiện, KHÔNG lưu.
// 3 trạng thái: đang tải / có kết quả / lỗi (báo lỗi tiếng Việt).

import { useState } from "react";
import { FileText, Loader2 } from "lucide-react";

type Status = "idle" | "loading" | "done" | "error";

export default function PreVisitBrief({ id }: { id: string }) {
  const [status, setStatus] = useState<Status>("idle");
  const [markdown, setMarkdown] = useState("");
  const [errorMsg, setErrorMsg] = useState("");
  const [elapsedMs, setElapsedMs] = useState<number | null>(null);

  async function load() {
    setStatus("loading");
    setErrorMsg("");
    try {
      const res = await fetch(`/api/brief/${id}`, { method: "POST" });
      const data = (await res.json()) as {
        markdown?: string;
        elapsed_ms?: number | null;
        error?: string;
      };
      if (!res.ok) {
        setErrorMsg(data.error ?? "Không tạo được tóm tắt. Thử lại sau.");
        setStatus("error");
        return;
      }
      setMarkdown(data.markdown ?? "");
      setElapsedMs(data.elapsed_ms ?? null);
      setStatus("done");
    } catch {
      setErrorMsg("Lỗi mạng — không gọi được dịch vụ tóm tắt.");
      setStatus("error");
    }
  }

  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <h3 className="text-base font-semibold text-[#171717]">
          Tóm tắt trước khám
        </h3>
        <button
          type="button"
          onClick={load}
          disabled={status === "loading"}
          className="inline-flex items-center gap-1.5 rounded-lg bg-[#6366f1] px-3 py-1.5 text-sm font-medium text-white hover:bg-[#4f46e5] disabled:cursor-not-allowed disabled:opacity-60"
        >
          {status === "loading" ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <FileText className="h-4 w-4" />
          )}
          {status === "idle"
            ? "Xem tóm tắt trước khám"
            : status === "loading"
              ? "Đang tạo tóm tắt…"
              : "Tạo lại tóm tắt"}
        </button>
        {status === "done" && elapsedMs != null && (
          <span className="text-xs text-[#a1a1aa]">
            ({(elapsedMs / 1000).toFixed(1)}s)
          </span>
        )}
      </div>

      <p className="text-sm text-[#888888]">
        Bản tổng hợp do trợ lý AI sinh từ hồ sơ bệnh nhân (tiền sử, lần khám,
        xét nghiệm). Chỉ để tham khảo trước khi khám — không tự lưu vào hồ sơ.
      </p>

      {status === "error" && (
        <div className="rounded-lg border border-[#fecaca] bg-[#fef2f2] px-4 py-3 text-sm text-[#dc2626]">
          {errorMsg}
        </div>
      )}

      {status === "done" &&
        (markdown.trim() ? (
          <pre className="whitespace-pre-wrap rounded-xl border border-[#e4e4e7] bg-white p-4 font-sans text-sm leading-relaxed text-[#171717] shadow-[0_1px_2px_rgba(0,0,0,0.05)]">
            {markdown}
          </pre>
        ) : (
          <div className="rounded-lg border border-[#e4e4e7] bg-[#fafafa] px-4 py-3 text-sm text-[#888888]">
            Chưa đủ dữ liệu để tạo tóm tắt cho bệnh nhân này.
          </div>
        ))}
    </section>
  );
}
