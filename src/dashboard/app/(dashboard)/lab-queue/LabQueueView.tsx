"use client";

// "Hàng đợi xét nghiệm" cho ĐD/KTV. XN Dr4Women chủ yếu gửi lab ngoài → kết quả
// về dạng PDF. Mỗi việc: BÁC SĨ đã chỉ định (PENDING) → ĐD đính TÓM TẮT + LINK
// phiếu (Drive/lab) + nhà cung cấp → "Lưu kết quả". Cột phải/dưới = đã trả.

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ExternalLink, FlaskConical } from "lucide-react";
import { fmtDateTimeOrDate } from "../../../lib/datetime";
import { INPUT, LABEL } from "../form-ui";
import { toHref } from "../../../lib/url";

export interface LabRow {
  lab_result_id: string;
  test_name: string;
  result_value: string | null;
  external_ref: string | null;
  lab_provider: string | null;
  result_received_at: string | null;
  created_at: string | null;
  patient: {
    full_name: string;
    patient_code: string;
    phone_primary: string | null;
  } | null;
}

function PendingCard({ row }: { row: LabRow }) {
  const router = useRouter();
  const [summary, setSummary] = useState("");
  const [link, setLink] = useState("");
  const [provider, setProvider] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function save() {
    if (!summary.trim() && !link.trim()) {
      setErr("Nhập tóm tắt hoặc dán link phiếu.");
      return;
    }
    setBusy(true);
    setErr(null);
    const res = await fetch("/api/lab-result", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        lab_result_id: row.lab_result_id,
        result_value: summary,
        result_link: link,
        lab_provider: provider,
      }),
    });
    setBusy(false);
    if (!res.ok) {
      setErr((await res.json()).error ?? "Lỗi lưu kết quả.");
      return;
    }
    router.refresh();
  }

  return (
    <div className="rounded-xl border border-[#f3cfe0] bg-white p-3 shadow-[0_1px_3px_rgba(236,72,153,0.08)]">
      <div className="mb-2">
        <span className="block text-sm font-semibold text-[#171717]">
          {row.test_name}
        </span>
        <span className="block truncate text-xs text-[#888888]">
          {row.patient?.full_name ?? "—"} ·{" "}
          <span className="font-mono">{row.patient?.patient_code}</span>
          {row.patient?.phone_primary ? ` · ${row.patient.phone_primary}` : ""}
        </span>
      </div>
      <div className="space-y-2">
        <div>
          <label className={LABEL}>Tóm tắt kết quả</label>
          <input
            className={INPUT}
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
            placeholder="VD: HPV (-), NIPT: chưa phát hiện bất thường…"
          />
        </div>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          <div>
            <label className={LABEL}>Link phiếu (PDF/Drive)</label>
            <input
              className={INPUT}
              value={link}
              onChange={(e) => setLink(e.target.value)}
              placeholder="https://…"
              inputMode="url"
            />
          </div>
          <div>
            <label className={LABEL}>Lab (nếu gửi ngoài)</label>
            <input
              className={INPUT}
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              placeholder="VD: GreenLab, Phacogen…"
            />
          </div>
        </div>
        {err && <p className="text-xs text-[#dc2626]">{err}</p>}
        <button
          onClick={save}
          disabled={busy}
          className="min-h-10 rounded-lg bg-[#ec4899] px-4 text-sm font-semibold text-white hover:bg-[#db2777] disabled:opacity-50"
        >
          {busy ? "Đang lưu…" : "Lưu kết quả"}
        </button>
      </div>
    </div>
  );
}

export default function LabQueueView({
  pending,
  done,
}: {
  pending: LabRow[];
  done: LabRow[];
}) {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <section>
        <h2 className="mb-2 flex items-center gap-2 text-base font-semibold text-[#171717]">
          <FlaskConical size={16} className="text-[#ec4899]" /> Chờ kết quả (
          {pending.length})
        </h2>
        {pending.length === 0 ? (
          <p className="rounded-xl border border-dashed border-[#f3cfe0] bg-white px-4 py-10 text-center text-sm text-[#a1a1aa]">
            Không có xét nghiệm nào đang chờ.
          </p>
        ) : (
          <div className="space-y-3">
            {pending.map((r) => (
              <PendingCard key={r.lab_result_id} row={r} />
            ))}
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-2 text-base font-semibold text-[#171717]">
          Đã trả gần đây ({done.length})
        </h2>
        <div className="max-h-[70vh] space-y-2 overflow-y-auto rounded-xl border border-[#f3cfe0] bg-white p-2 shadow-[0_1px_3px_rgba(236,72,153,0.08)]">
          {done.length === 0 ? (
            <p className="px-2 py-10 text-center text-sm text-[#a1a1aa]">
              Chưa có kết quả nào.
            </p>
          ) : (
            done.map((r) => (
              <div
                key={r.lab_result_id}
                className="rounded-lg border border-[#e4e4e7] p-2.5"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate text-sm font-medium text-[#171717]">
                    {r.test_name}
                  </span>
                  {toHref(r.external_ref) && (
                    <a
                      href={toHref(r.external_ref)!}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex shrink-0 items-center gap-1 text-xs font-medium text-[#2563eb] hover:underline"
                    >
                      <ExternalLink size={12} /> Phiếu
                    </a>
                  )}
                </div>
                <span className="block truncate text-xs text-[#888888]">
                  {r.patient?.full_name ?? "—"} · {r.patient?.patient_code}
                </span>
                {r.result_value && (
                  <span className="mt-0.5 block text-xs text-[#52525b]">
                    {r.result_value}
                    {r.lab_provider ? ` · ${r.lab_provider}` : ""}
                  </span>
                )}
                <span className="mt-0.5 block text-[11px] text-[#a1a1aa]">
                  {fmtDateTimeOrDate(r.result_received_at)}
                </span>
              </div>
            ))
          )}
        </div>
      </section>
    </div>
  );
}
