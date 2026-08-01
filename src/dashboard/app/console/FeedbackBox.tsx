"use client";

/**
 * Khung báo lỗi: dán ảnh + viết một câu.
 *
 * Vòng phản hồi trước đây là: thấy sai → mô tả bằng chữ trong khung chat → tôi
 * đoán lại ngữ cảnh. Mất ngữ cảnh ở mỗi bước: không biết đang ở màn nào, đăng
 * nhập vai gì, lúc đó hệ ra sao.
 *
 * Ở đây URL và vai được thu TỰ ĐỘNG, và ảnh dán thẳng bằng Ctrl+V — thao tác
 * duy nhất còn lại là gõ một câu. Mỗi ô bắt người dùng gõ thêm là một ô họ sẽ
 * bỏ trống lúc đang vội, và lúc đang vội mới là lúc lỗi hay xảy ra nhất.
 */

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, useTransition } from "react";

const MUC_DO = [
  { v: "chan_dung", label: "Chặn đứng", hint: "không dùng tiếp được" },
  { v: "lam_sai", label: "Làm sai", hint: "chạy nhưng kết quả sai" },
  { v: "kho_hieu", label: "Khó hiểu", hint: "nhìn không hiểu màn này nói gì" },
  { v: "nhan_xet", label: "Góp ý", hint: "không phải lỗi" },
];

export default function FeedbackBox({ role }: { role: string | null }) {
  const [comment, setComment] = useState("");
  const [severity, setSeverity] = useState("kho_hieu");
  const [image, setImage] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [state, setState] = useState<"idle" | "sending" | "done" | "error">("idle");
  const [msg, setMsg] = useState<string | null>(null);
  const areaRef = useRef<HTMLTextAreaElement>(null);
  const router = useRouter();
  const [, startTransition] = useTransition();

  // Dán ảnh ở bất kỳ đâu trên trang, không phải bấm vào đúng một ô nào.
  useEffect(() => {
    const onPaste = (e: ClipboardEvent) => {
      const item = [...(e.clipboardData?.items ?? [])].find((i) =>
        i.type.startsWith("image/"),
      );
      if (!item) return;
      const f = item.getAsFile();
      if (!f) return;
      setImage(f);
      setPreview(URL.createObjectURL(f));
      areaRef.current?.focus();
    };
    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
  }, []);

  async function send() {
    if (!comment.trim()) {
      setMsg("Viết một câu mô tả đã.");
      setState("error");
      return;
    }
    setState("sending");
    setMsg(null);
    const fd = new FormData();
    fd.set("comment", comment);
    fd.set("severity", severity);
    // Ngữ cảnh tự thu — người dùng không phải nhớ mình đang ở đâu.
    fd.set("page_url", typeof window !== "undefined" ? window.location.pathname : "");
    fd.set("role_at_time", role ?? "");
    if (image) fd.set("image", image);

    const res = await fetch("/api/console/feedback", { method: "POST", body: fd });
    if (!res.ok) {
      const b = (await res.json().catch(() => null)) as { error?: string } | null;
      setMsg(b?.error ?? `Không gửi được (HTTP ${res.status})`);
      setState("error");
      return;
    }
    setComment("");
    setImage(null);
    setPreview(null);
    setState("done");
    setMsg("Đã ghi lại. Lần sau tôi đọc từ đây.");
    // Danh sách "Đã báo" ngay bên dưới render phía server, nên phải bảo trang
    // đọc lại — không thì vừa gửi xong đã thấy "chưa có phản hồi nào", và người
    // gửi sẽ tưởng nó rơi mất.
    startTransition(() => router.refresh());
  }

  return (
    <section className="rounded-card border border-line bg-surface p-5 shadow-card">
      <h2 className="font-medium text-ink">Báo cho tôi</h2>
      <p className="mt-0.5 text-sm text-ink-muted">
        Dán ảnh bằng <kbd className="rounded bg-surface-sunken px-1">Ctrl+V</kbd>{" "}
        ở bất kỳ đâu trên trang, viết một câu, gửi. URL và vai tự ghi kèm.
      </p>

      <div className="mt-3 flex flex-wrap gap-2">
        {MUC_DO.map((m) => (
          <button
            key={m.v}
            type="button"
            onClick={() => setSeverity(m.v)}
            title={m.hint}
            className={`rounded-chip px-3 py-1.5 text-sm font-medium transition-colors ${
              severity === m.v
                ? "bg-brand-600 text-white"
                : "bg-surface-sunken text-ink-soft hover:bg-line"
            }`}
          >
            {m.label}
          </button>
        ))}
      </div>

      <textarea
        ref={areaRef}
        value={comment}
        onChange={(e) => setComment(e.target.value)}
        rows={3}
        placeholder="Ví dụ: bấm Hoàn tất ở Bàn thu ngân, người bệnh không biến khỏi danh sách, F5 vẫn còn."
        className="mt-3 w-full rounded-control border border-line bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-faint focus:border-brand-500 focus:outline-none"
      />

      {preview ? (
        <div className="mt-2 flex items-start gap-3">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={preview}
            alt="Ảnh sẽ gửi kèm"
            className="max-h-40 rounded-control border border-line"
          />
          <button
            type="button"
            onClick={() => {
              setImage(null);
              setPreview(null);
            }}
            className="text-sm text-ink-muted underline"
          >
            bỏ ảnh
          </button>
        </div>
      ) : null}

      <div className="mt-3 flex items-center gap-3">
        <button
          type="button"
          onClick={send}
          disabled={state === "sending"}
          className="rounded-control bg-brand-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
        >
          {state === "sending" ? "Đang gửi…" : "Gửi"}
        </button>
        {msg ? (
          <span
            className={`text-sm ${state === "error" ? "text-danger" : "text-status-completed"}`}
          >
            {msg}
          </span>
        ) : null}
      </div>
    </section>
  );
}
