"use client";

// "Hàng đợi dịch vụ / thủ thuật" cho ĐD/KTV. Tạo việc → Bắt đầu (ghi giờ) →
// Hoàn tất (ghi giờ + kết quả). Trái: đang làm/chờ. Phải: đã xong gần đây.

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, Play, Check } from "lucide-react";
import { fmtDateTimeOrDate, fmtTime, isVnMidnight } from "../../../lib/datetime";
import { INPUT, LABEL } from "../form-ui";

export interface ServiceRow {
  id: string;
  service_name_raw: string | null;
  status: string | null;
  result_text: string | null;
  performer_text: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string | null;
  patient: { full_name: string; patient_code: string } | null;
}

function ActiveCard({ row }: { row: ServiceRow }) {
  const router = useRouter();
  const [result, setResult] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const started = !!row.started_at;

  async function act(action: "start" | "finish") {
    setBusy(true);
    setErr(null);
    const res = await fetch("/api/service-log", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: row.id, action, result_text: result }),
    });
    setBusy(false);
    if (!res.ok) {
      setErr((await res.json()).error ?? "Lỗi cập nhật.");
      return;
    }
    router.refresh();
  }

  return (
    <div className="rounded-xl border border-[#f3cfe0] bg-white p-3 shadow-[0_1px_3px_rgba(236,72,153,0.08)]">
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-semibold text-[#171717]">
          {row.service_name_raw}
        </span>
        <span className="shrink-0 rounded-full bg-[#fce7f3] px-2 py-0.5 text-[11px] font-medium text-[#9d2463]">
          {started ? "Đang làm" : "Chờ làm"}
        </span>
      </div>
      <span className="block truncate text-xs text-[#888888]">
        {row.patient
          ? `${row.patient.full_name} · ${row.patient.patient_code}`
          : "(không gắn BN)"}
        {row.performer_text ? ` · ${row.performer_text}` : ""}
      </span>
      {started && (
        <span className="mt-0.5 block text-[11px] text-[#a1a1aa]">
          Bắt đầu: {isVnMidnight(row.started_at) ? "—" : fmtTime(row.started_at)}
        </span>
      )}

      <div className="mt-2 space-y-2">
        {started && (
          <input
            className={INPUT}
            value={result}
            onChange={(e) => setResult(e.target.value)}
            placeholder="Kết quả / ghi chú khi hoàn tất"
          />
        )}
        {err && <p className="text-xs text-[#dc2626]">{err}</p>}
        <div className="flex gap-2">
          {!started && (
            <button
              onClick={() => act("start")}
              disabled={busy}
              className="inline-flex min-h-9 items-center gap-1 rounded-lg bg-[#2563eb] px-3 text-sm font-semibold text-white hover:bg-[#1d4ed8] disabled:opacity-50"
            >
              <Play size={14} /> Bắt đầu
            </button>
          )}
          <button
            onClick={() => act("finish")}
            disabled={busy}
            className="inline-flex min-h-9 items-center gap-1 rounded-lg bg-[#16a34a] px-3 text-sm font-semibold text-white hover:bg-[#15803d] disabled:opacity-50"
          >
            <Check size={14} /> Hoàn tất
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ServiceQueueView({
  active,
  done,
}: {
  active: ServiceRow[];
  done: ServiceRow[];
}) {
  const router = useRouter();
  const [name, setName] = useState("");
  const [pcode, setPcode] = useState("");
  const [performer, setPerformer] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function create() {
    if (!name.trim()) {
      setErr("Nhập tên dịch vụ.");
      return;
    }
    setBusy(true);
    setErr(null);
    const res = await fetch("/api/service-log", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        service_name: name,
        patient_code: pcode,
        performer,
      }),
    });
    setBusy(false);
    if (!res.ok) {
      setErr((await res.json()).error ?? "Lỗi tạo việc.");
      return;
    }
    setName("");
    setPcode("");
    setPerformer("");
    router.refresh();
  }

  return (
    <div className="space-y-4">
      {/* Tạo việc dịch vụ */}
      <div className="rounded-xl border border-[#f3cfe0] bg-white p-3 shadow-[0_1px_3px_rgba(236,72,153,0.08)]">
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
          <div className="sm:col-span-1">
            <label className={LABEL}>Tên dịch vụ / thủ thuật *</label>
            <input
              className={INPUT}
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="VD: Siêu âm đầu dò, Đặt vòng…"
            />
          </div>
          <div>
            <label className={LABEL}>Mã BN (nếu có)</label>
            <input
              className={INPUT}
              value={pcode}
              onChange={(e) => setPcode(e.target.value)}
              placeholder="BN-2026-…"
            />
          </div>
          <div>
            <label className={LABEL}>Người làm</label>
            <input
              className={INPUT}
              value={performer}
              onChange={(e) => setPerformer(e.target.value)}
              placeholder="Tên ĐD/KTV"
            />
          </div>
        </div>
        {err && <p className="mt-2 text-xs text-[#dc2626]">{err}</p>}
        <button
          onClick={create}
          disabled={busy}
          className="mt-2 inline-flex min-h-9 items-center gap-1 rounded-lg bg-[#ec4899] px-4 text-sm font-semibold text-white hover:bg-[#db2777] disabled:opacity-50"
        >
          <Plus size={14} /> {busy ? "Đang tạo…" : "Thêm việc"}
        </button>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <section>
          <h2 className="mb-2 text-base font-semibold text-[#171717]">
            Đang làm / chờ ({active.length})
          </h2>
          {active.length === 0 ? (
            <p className="rounded-xl border border-dashed border-[#f3cfe0] bg-white px-4 py-10 text-center text-sm text-[#a1a1aa]">
              Không có việc dịch vụ nào đang chờ.
            </p>
          ) : (
            <div className="space-y-3">
              {active.map((r) => (
                <ActiveCard key={r.id} row={r} />
              ))}
            </div>
          )}
        </section>

        <section>
          <h2 className="mb-2 text-base font-semibold text-[#171717]">
            Đã hoàn tất gần đây ({done.length})
          </h2>
          <div className="max-h-[70vh] space-y-2 overflow-y-auto rounded-xl border border-[#f3cfe0] bg-white p-2 shadow-[0_1px_3px_rgba(236,72,153,0.08)]">
            {done.length === 0 ? (
              <p className="px-2 py-10 text-center text-sm text-[#a1a1aa]">
                Chưa có việc nào hoàn tất.
              </p>
            ) : (
              done.map((r) => (
                <div key={r.id} className="rounded-lg border border-[#e4e4e7] p-2.5">
                  <span className="block truncate text-sm font-medium text-[#171717]">
                    {r.service_name_raw}
                  </span>
                  <span className="block truncate text-xs text-[#888888]">
                    {r.patient
                      ? `${r.patient.full_name} · ${r.patient.patient_code}`
                      : "(không gắn BN)"}
                  </span>
                  {r.result_text && (
                    <span className="mt-0.5 block text-xs text-[#52525b]">
                      {r.result_text}
                    </span>
                  )}
                  <span className="mt-0.5 block text-[11px] text-[#a1a1aa]">
                    {fmtDateTimeOrDate(r.finished_at)}
                  </span>
                </div>
              ))
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
