"use client";

// HÀNG ĐỢI THEO TRẠM — XEM + ĐIỀU PHỐI TRÊN CÙNG MỘT TRANG (Tuyền 27/09/2026:
// "trang điều phối ca đang xấu quá, khó làm… muốn cùng 1 trang để theo dõi
// được tổng thể hơn").
//
// Mỗi phòng một thẻ; khách chờ QUÁ NGƯỠNG của phòng tô đỏ và đứng đầu. Bấm một
// khách → khung bên phải liệt kê từng chỉ định của khách với ô đổi phòng
// (`ChiDinhCuaBacSi` → `DoiPhong`): danh sách phòng làm được đúng dịch vụ ấy và
// số người chờ do MÁY CHỦ trả — màn không tự đoán phòng nào làm được gì.
// Mỗi phòng có nút mở TV riêng (`/display?phong=<mã phòng>` — cùng màn TV đã lọc danh tính).

import Link from "next/link";
import { Tv, X } from "lucide-react";
import { useMemo, useState } from "react";

import Chip from "@/components/ui/Chip";
import StatCard, { StatRow } from "@/components/ui/StatCard";
import ChiDinhCuaBacSi from "./ChiDinhCuaBacSi";
import type { DispatchPatient, DispatchRoom } from "./types";
import { LiveBadge, ReadFailed, tenPhong, useDispatchLive } from "./shared";

const quaNguong = (p: DispatchPatient) => p.wait_minutes > p.threshold_minutes;

export default function QueuesClient({
  initial,
}: {
  initial: { patients: DispatchPatient[]; rooms: DispatchRoom[]; ok: boolean };
}) {
  const live = useDispatchLive({ ...initial, alerts: [] });
  const [chon, setChon] = useState<string | null>(null);
  const khach = live.patients.find((p) => p.visit_id === chon) ?? null;

  const soDo = live.patients.filter(quaNguong).length;
  const phongDay = live.rooms.filter((r) => r.state === "critical").length;
  const tongCho = live.rooms.reduce((s, r) => s + r.waiting, 0);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <StatRow>
          <StatCard label="Đang chờ" value={tongCho} tone="brand" />
          <StatCard label="Chờ quá ngưỡng" value={soDo} tone={soDo ? "danger" : "neutral"} />
          <StatCard label="Phòng quá tải" value={phongDay} tone={phongDay ? "warning" : "neutral"} />
        </StatRow>
        <LiveBadge seconds={live.staleSeconds} ok={live.ok} />
      </div>
      <ReadFailed ok={live.ok} />

      <div className={`grid items-start gap-3 ${khach ? "lg:grid-cols-[minmax(0,1fr)_380px]" : ""}`}>
        <div className="grid grid-cols-[repeat(auto-fill,minmax(260px,1fr))] gap-3">
          {live.rooms.map((r) => (
            <ThePhong key={r.id} phong={r} ds={live.patients} chon={chon} onChon={setChon} />
          ))}
        </div>

        {khach ? (
          <aside
            aria-label="Điều phối khách"
            className="rounded-card border border-line bg-surface p-4 shadow-card lg:sticky lg:top-4"
          >
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="truncate text-emph font-semibold text-ink">{khach.patient_name ?? "—"}</p>
                <p className="text-meta text-ink-muted">
                  {khach.patient_code ?? ""}
                  {khach.doctor_name ? ` · ${khach.doctor_name}` : ""}
                </p>
              </div>
              <button
                type="button"
                aria-label="Đóng"
                onClick={() => setChon(null)}
                className="rounded-control p-1.5 text-ink-muted hover:bg-surface-sunken"
              >
                <X className="size-4" aria-hidden="true" />
              </button>
            </div>
            <p className={`mt-2 text-meta ${quaNguong(khach) ? "font-semibold text-danger" : "text-ink-soft"}`}>
              {khach.current_node_name ?? khach.current_node_code ?? "—"}
              {khach.room_name ? ` · ${tenPhong(khach.room_name)}` : ""} — chờ {khach.wait_minutes}′
              {quaNguong(khach) ? ` (ngưỡng ${khach.threshold_minutes}′)` : ""}
            </p>
            <p className="mt-3 text-label font-semibold uppercase text-ink-muted">
              Chuyển sang phòng làm được việc này
            </p>
            <ChiDinhCuaBacSi key={khach.visit_id} visitId={khach.visit_id} />
          </aside>
        ) : null}
      </div>
    </div>
  );
}

function ThePhong({
  phong: r,
  ds,
  chon,
  onChon,
}: {
  phong: DispatchRoom;
  ds: DispatchPatient[];
  chon: string | null;
  onChon: (id: string) => void;
}) {
  const o = useMemo(
    () =>
      ds
        .filter((p) => p.room_code === r.code)
        .sort((a, b) => Number(quaNguong(b)) - Number(quaNguong(a)) || b.wait_minutes - a.wait_minutes),
    [ds, r.code],
  );
  const tone = r.state === "critical" ? "danger" : r.state === "warning" ? "warning" : "success";
  return (
    <section
      className={`rounded-card border bg-surface shadow-card ${
        r.state === "critical" ? "border-danger/40" : "border-line"
      }`}
    >
      <header className="flex items-center justify-between gap-2 border-b border-line px-3 py-2">
        <div className="min-w-0">
          <h2 className="truncate text-body font-semibold text-ink">{tenPhong(r.name)}</h2>
          <p className="text-label text-ink-muted">
            {o.length} khách · {r.serving} đang làm
            {r.accepting ? "" : " · tạm ngưng nhận"}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <Chip tone={tone}>{r.state === "critical" ? "Quá tải" : r.state === "warning" ? "Đông" : "Ổn"}</Chip>
          <Link
            href={`/display?phong=${encodeURIComponent(r.code)}&ten=${encodeURIComponent(tenPhong(r.name))}`}
            target="_blank"
            title="Mở TV của phòng này"
            aria-label={`Mở TV ${tenPhong(r.name)}`}
            className="rounded-control p-1.5 text-ink-muted hover:bg-surface-sunken hover:text-ink"
          >
            <Tv className="size-4" aria-hidden="true" />
          </Link>
        </div>
      </header>
      {o.length === 0 ? (
        <p className="px-3 py-3 text-meta text-ink-faint">Không có ai đang chờ</p>
      ) : (
        <ul>
          {o.map((p) => {
            const do_ = quaNguong(p);
            const dang = p.visit_id === chon;
            return (
              <li key={p.visit_id} className="border-b border-line last:border-b-0">
                <button
                  type="button"
                  onClick={() => onChon(p.visit_id)}
                  aria-current={dang ? "true" : undefined}
                  title={do_ ? "Chờ quá ngưỡng — bấm để chuyển phòng" : "Bấm để xem / chuyển phòng"}
                  className={`flex w-full items-center gap-2 border-l-3 px-3 py-2 text-left text-meta ${
                    dang
                      ? "border-l-brand-500 bg-surface-selected"
                      : do_
                        ? "border-l-danger bg-danger-bg/50 hover:bg-danger-bg"
                        : "border-l-transparent hover:bg-surface-sunken"
                  }`}
                >
                  <span className="w-8 shrink-0 font-semibold tabular-nums text-ink-soft">
                    {p.so_tiep_don ?? p.queue_number ?? ""}
                  </span>
                  <span className="min-w-0 flex-1 truncate text-ink">{p.patient_name ?? "—"}</span>
                  <span className={`shrink-0 tabular-nums ${do_ ? "font-semibold text-danger" : "text-ink-muted"}`}>
                    {p.wait_minutes}′
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
