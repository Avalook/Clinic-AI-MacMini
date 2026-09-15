"use client";

// THỨ TỰ KHÁM — lễ tân kéo thả (Tuyền chốt 15/09/2026).
//
// Khám theo thứ tự check-in; hôm nào cần thì lễ tân kéo một khách lên trước ai
// đó theo chỉ đạo trưởng ca. Màn này KHÔNG tự xếp: thứ tự và mốc mới đều do
// FastAPI tính (GET /queue, POST /queue/keo). Nút ↑/↓ cho màn cảm ứng, nơi kéo
// thả không dùng được.

import { useCallback, useEffect, useMemo, useState } from "react";

import PriorityChip from "@/components/ui/PriorityChip";
import { homNayVn } from "@/lib/validation";

interface DongHang {
  id: string;
  queue_number: string | null;
  patient: { full_name: string | null; patient_code: string | null };
  doctor: { full_name: string | null };
  checked_in_at: string | null;
  call_order: number;
  uu_tien: boolean;
  uu_tien_ly_do: string | null;
}

const LAM_MOI_MS = 30_000;

function gioPhut(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Ho_Chi_Minh",
  });
}

export default function ThuTuKham() {
  const [hang, setHang] = useState<DongHang[] | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [dangKeo, setDangKeo] = useState<string | null>(null);
  const [dangGhi, setDangGhi] = useState(false);

  const tai = useCallback(async () => {
    const res = await fetch(`/api/queue?date=${homNayVn()}`, { cache: "no-store" });
    const json = await res.json().catch(() => ({}));
    if (!res.ok) {
      setLoi(json.error ?? "Không tải được thứ tự khám.");
      return;
    }
    setLoi(null);
    setHang((json.rows ?? []) as DongHang[]);
  }, []);

  useEffect(() => {
    let huy = false;
    const chay = () => {
      if (!huy) void tai();
    };
    chay();
    const t = setInterval(chay, LAM_MOI_MS);
    return () => {
      huy = true;
      clearInterval(t);
    };
  }, [tai]);

  const nhom = useMemo(() => {
    const out = new Map<string, DongHang[]>();
    for (const d of [...(hang ?? [])].sort((a, b) => a.call_order - b.call_order)) {
      const bs = d.doctor.full_name ?? "Chưa xếp bác sĩ";
      out.set(bs, [...(out.get(bs) ?? []), d]);
    }
    return [...out.entries()];
  }, [hang]);

  async function dat(id: string, sau: string | null, truoc: string | null) {
    if (sau === id || truoc === id) return;
    setDangGhi(true);
    const res = await fetch("/api/queue/keo", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        appointment_id: id,
        sau_appointment_id: sau,
        truoc_appointment_id: truoc,
      }),
    });
    const json = await res.json().catch(() => ({}));
    setDangGhi(false);
    if (!res.ok) setLoi(json.error ?? "Không đổi được thứ tự.");
    await tai();
  }

  /** Thả `id` ngay TRƯỚC `dich` trong cùng nhóm (dich = null → xuống cuối). */
  function thaTruoc(ds: DongHang[], id: string, dich: string | null) {
    const con = ds.filter((d) => d.id !== id);
    if (dich === null) {
      void dat(id, con.at(-1)?.id ?? null, null);
      return;
    }
    const i = con.findIndex((d) => d.id === dich);
    if (i < 0) return;
    void dat(id, i > 0 ? con[i - 1].id : null, con[i].id);
  }

  if (hang === null && !loi) return null;

  return (
    <section className="rounded-card border border-line bg-surface p-3">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-sm font-semibold text-ink">Thứ tự khám hôm nay</h2>
        <p className="text-label text-ink-muted">
          Theo giờ check-in. Kéo thả (hoặc ↑/↓) để đưa khách lên trước theo chỉ
          đạo trưởng ca.
        </p>
      </header>
      {loi && <p className="mt-2 text-sm text-danger">{loi}</p>}
      {nhom.length === 0 && !loi && (
        <p className="mt-2 text-sm text-ink-muted">Chưa có khách nào check-in.</p>
      )}
      <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {nhom.map(([bs, ds]) => (
          <div key={bs} className="min-w-0 rounded-control border border-line p-2">
            <h3 className="truncate text-xs font-semibold text-ink-soft">{bs}</h3>
            <ol className="mt-2 space-y-1">
              {ds.map((d, i) => (
                <li
                  key={d.id}
                  draggable={!dangGhi}
                  onDragStart={() => setDangKeo(d.id)}
                  onDragEnd={() => setDangKeo(null)}
                  onDragOver={(e) => {
                    if (dangKeo && ds.some((x) => x.id === dangKeo)) e.preventDefault();
                  }}
                  onDrop={(e) => {
                    e.preventDefault();
                    if (dangKeo) thaTruoc(ds, dangKeo, d.id);
                    setDangKeo(null);
                  }}
                  className={`flex min-w-0 items-center gap-2 rounded-control border px-2 py-1.5 text-sm ${
                    dangKeo === d.id
                      ? "border-brand-600 opacity-60"
                      : "border-line bg-surface-sunken"
                  } cursor-grab`}
                >
                  <span className="w-6 shrink-0 text-center text-label text-ink-muted">
                    {i + 1}
                  </span>
                  <span className="w-10 shrink-0 font-semibold text-ink">
                    {d.queue_number ?? "—"}
                  </span>
                  <span className="min-w-0 flex-1 truncate text-ink">
                    {d.patient.full_name ?? "Chưa rõ tên"}
                  </span>
                  {d.uu_tien && (
                    <span title={d.uu_tien_ly_do ?? undefined}>
                      <PriorityChip priority="P0" />
                    </span>
                  )}
                  <span className="shrink-0 text-label text-ink-muted">
                    {gioPhut(d.checked_in_at)}
                  </span>
                  <span className="flex shrink-0 gap-0.5">
                    <button
                      type="button"
                      aria-label="Lên trước"
                      disabled={dangGhi || i === 0}
                      onClick={() => thaTruoc(ds, d.id, ds[i - 1].id)}
                      className="rounded-control px-1.5 text-ink-muted hover:bg-surface disabled:opacity-30"
                    >
                      ↑
                    </button>
                    <button
                      type="button"
                      aria-label="Xuống sau"
                      disabled={dangGhi || i === ds.length - 1}
                      onClick={() => thaTruoc(ds, d.id, ds[i + 2]?.id ?? null)}
                      className="rounded-control px-1.5 text-ink-muted hover:bg-surface disabled:opacity-30"
                    >
                      ↓
                    </button>
                  </span>
                </li>
              ))}
            </ol>
            <div
              onDragOver={(e) => {
                if (dangKeo && ds.some((x) => x.id === dangKeo)) e.preventDefault();
              }}
              onDrop={(e) => {
                e.preventDefault();
                if (dangKeo) thaTruoc(ds, dangKeo, null);
                setDangKeo(null);
              }}
              className="mt-1 h-3 rounded-control"
              aria-hidden
            />
          </div>
        ))}
      </div>
    </section>
  );
}
