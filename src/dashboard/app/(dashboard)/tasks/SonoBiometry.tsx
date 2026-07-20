"use client";

// Số đo SIÊU ÂM THAI cho BÁC SĨ SIÊU ÂM — gắn vào visit qua /api/ultrasound
// (ultrasound_record.findings JSONB). 7 số đo chuẩn + 4 nút thao tác (theo ảnh PK).
// EFW nhập TAY — KHÔNG tự tính (chờ BS Thắng chốt công thức Hadlock).

import { useEffect, useState } from "react";
import { INPUT, LABEL } from "../form-ui";

const FIELDS: { key: string; label: string }[] = [
  { key: "crl", label: "CRL — chiều dài đầu-mông (mm)" },
  { key: "nt", label: "NT — độ mờ da gáy (mm)" },
  { key: "bpd", label: "BPD — đường kính lưỡng đỉnh (mm)" },
  { key: "hc", label: "HC — chu vi đầu (mm)" },
  { key: "ac", label: "AC — chu vi bụng (mm)" },
  { key: "fl", label: "FL — chiều dài xương đùi (mm)" },
  // TODO auto-EFW: tự tính từ BPD/HC/AC/FL khi BS Thắng xác nhận công thức. Giờ nhập tay.
  { key: "efw", label: "EFW — ước tính cân nặng thai (gram) · nhập tay" },
];
const KEYS = FIELDS.map((f) => f.key);
type Meas = Record<string, string>;
const EMPTY: Meas = Object.fromEntries(KEYS.map((k) => [k, ""]));

export default function SonoBiometry({
  appointmentId,
  clinicPatientId,
}: {
  appointmentId: string;
  clinicPatientId: string;
}) {
  const [m, setM] = useState<Meas>(EMPTY);
  const [isAbnormal, setIsAbnormal] = useState(false);
  const [status, setStatus] = useState<string>("");
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  // Nạp số đo đã lưu của lượt khám này (nếu có).
  useEffect(() => {
    let on = true;
    fetch(`/api/ultrasound?appointmentId=${encodeURIComponent(appointmentId)}`)
      .then((r) => r.json())
      .then((d) => {
        if (!on || !d.record?.findings) return;
        const f = d.record.findings as Record<string, unknown>;
        setM(
          Object.fromEntries(
            KEYS.map((k) => [k, f[k] === null || f[k] === undefined ? "" : String(f[k])]),
          ) as Meas,
        );
        setIsAbnormal(f.is_abnormal === true);
        setStatus(typeof f.status === "string" ? f.status : "");
      })
      .catch(() => {});
    return () => {
      on = false;
    };
  }, [appointmentId]);

  async function post(
    label: string,
    payload: Record<string, unknown>,
  ): Promise<Record<string, unknown> | null> {
    setBusy(label);
    setMsg(null);
    try {
      const res = await fetch("/api/ultrasound", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ appointmentId, clinicPatientId, ...payload }),
      });
      const j = await res.json();
      if (!res.ok) {
        setMsg(j.error ?? "Lỗi lưu số đo.");
        return null;
      }
      return j.findings as Record<string, unknown>;
    } finally {
      setBusy(null);
    }
  }

  const measPayload = () => ({
    measurements: Object.fromEntries(KEYS.map((k) => [k, m[k].trim()])),
  });

  async function start() {
    if (await post("start", { status: "in_progress" })) {
      setStatus("in_progress");
      setMsg("Đã bắt đầu siêu âm.");
    }
  }
  async function saveResult() {
    if (await post("save", measPayload())) setMsg("Đã lưu kết quả số đo.");
  }
  async function toggleAbnormal() {
    const next = !isAbnormal;
    if (await post("abnormal", { is_abnormal: next })) {
      setIsAbnormal(next);
      setMsg(next ? "Đã đánh dấu BẤT THƯỜNG." : "Đã bỏ đánh dấu bất thường.");
    }
  }
  async function complete() {
    if (await post("complete", { ...measPayload(), status: "completed" })) {
      setStatus("completed");
      setMsg("Đã hoàn tất siêu âm.");
    }
  }

  const set = (k: string, v: string) => setM((o) => ({ ...o, [k]: v }));

  return (
    <section className="space-y-3 rounded-xl border border-[#f3cfe0] bg-[#fdf7fb] p-4">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-[#9d2463]">Số đo siêu âm thai</h3>
        <div className="flex items-center gap-2 text-[11px]">
          {status === "completed" && (
            <span className="rounded-full bg-[#dcfce7] px-2 py-0.5 font-medium text-[#15803d]">
              Đã hoàn tất
            </span>
          )}
          {status === "in_progress" && (
            <span className="rounded-full bg-[#fef3c7] px-2 py-0.5 font-medium text-[#b45309]">
              Đang siêu âm
            </span>
          )}
          {isAbnormal && (
            <span className="rounded-full bg-[#fee2e2] px-2 py-0.5 font-medium text-[#dc2626]">
              ⚠ Bất thường
            </span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {FIELDS.map((f) => (
          <div key={f.key}>
            <label className={LABEL}>{f.label}</label>
            <input
              className={INPUT}
              inputMode="decimal"
              value={m[f.key]}
              onChange={(e) => set(f.key, e.target.value)}
              placeholder="—"
            />
          </div>
        ))}
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          onClick={start}
          disabled={busy !== null}
          className="min-h-9 rounded-md bg-[#7c3aed] px-3 text-xs font-semibold text-white hover:bg-[#6d28d9] disabled:opacity-50"
        >
          Bắt đầu siêu âm
        </button>
        <button
          onClick={saveResult}
          disabled={busy !== null}
          className="min-h-9 rounded-md bg-[#ec4899] px-3 text-xs font-semibold text-white hover:bg-[#db2777] disabled:opacity-50"
        >
          Lưu kết quả
        </button>
        <button
          onClick={toggleAbnormal}
          disabled={busy !== null}
          className="min-h-9 rounded-md border border-[#fca5a5] bg-white px-3 text-xs font-medium text-[#dc2626] hover:bg-[#fef2f2] disabled:opacity-50"
        >
          {isAbnormal ? "Bỏ đánh dấu bất thường" : "Đánh dấu bất thường"}
        </button>
        <button
          onClick={complete}
          disabled={busy !== null}
          className="min-h-9 rounded-md bg-[#16a34a] px-3 text-xs font-semibold text-white hover:bg-[#15803d] disabled:opacity-50"
        >
          Hoàn tất
        </button>
      </div>
      {msg && <p className="text-xs text-[#15803d]">{msg}</p>}
    </section>
  );
}
