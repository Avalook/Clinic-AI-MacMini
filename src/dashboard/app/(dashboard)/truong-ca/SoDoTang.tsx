"use client";

// BỐN Ô SỐ + ĐIỀU PHỐI NHANH + SƠ ĐỒ PHÒNG THEO TẦNG (bản thiết kế Tuyền gửi
// 16/09/2026).
//
// Ba khối này đọc CHÍNH gói dữ liệu điều phối màn đã tải — không thêm một lời
// gọi nào. Riêng `alerts` thì màn vẫn gọi sẵn 30 giây một lần nhưng chưa bao
// giờ vẽ ra: khối "Điều phối nhanh" nay dùng đúng dữ liệu ấy, nên lời gọi kia
// hết là lời gọi thừa.

import { useState } from "react";
import { Activity, DoorOpen, Hourglass, Users } from "lucide-react";

import type { DispatchAlert, DispatchPatient, DispatchRoom } from "./types";
import { tenTang } from "./shared";

/** Phòng đang có người: đang khám hoặc đang có người chờ. */
function dangDung(r: DispatchRoom): boolean {
  return r.serving > 0 || r.waiting > 0;
}

export function BonOSo({
  patients,
  rooms,
}: {
  patients: DispatchPatient[];
  rooms: DispatchRoom[];
}) {
  // ĐẾM TRÊN CHÍNH DỮ LIỆU ĐANG VẼ, không hỏi thêm một endpoint nữa: con số ở
  // đầu trang mà cãi bảng ngay dưới nó thì người trực tin bảng, và ô số thành
  // trang trí. `wait_minutes`/`threshold_minutes` đều do backend tính.
  const dangCho = rooms.reduce((t, r) => t + r.waiting, 0);
  const dangKham = rooms.reduce((t, r) => t + r.serving, 0);
  const quaSla = patients.filter(
    (p) => p.threshold_minutes != null && p.wait_minutes > p.threshold_minutes,
  ).length;
  const mo = rooms.filter(dangDung).length;

  const o = [
    { nhan: "Đang chờ điều phối", so: dangCho, don: "bệnh nhân", mau: "brand", icon: <Users size={20} /> },
    { nhan: "Đang khám", so: dangKham, don: "bệnh nhân", mau: "info", icon: <Activity size={20} /> },
    { nhan: "Quá ngưỡng chờ", so: quaSla, don: "bệnh nhân", mau: "danger", icon: <Hourglass size={20} /> },
    { nhan: "Phòng hoạt động", so: mo, don: `/ ${rooms.length} phòng`, mau: "success", icon: <DoorOpen size={20} /> },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
      {o.map((x) => (
        <div
          key={x.nhan}
          className="flex items-center gap-3 rounded-card border border-line bg-surface p-3.5 shadow-card"
        >
          <span
            className={`grid size-11 shrink-0 place-items-center rounded-2xl ${
              x.mau === "brand"
                ? "bg-brand-50 text-brand-700"
                : x.mau === "info"
                  ? "bg-surface-muted text-ink-soft"
                  : x.mau === "danger"
                    ? "bg-danger-bg text-danger"
                    : "bg-success-bg text-success"
            }`}
          >
            {x.icon}
          </span>
          <span className="min-w-0">
            <span className="block truncate text-xs font-medium text-ink-muted">{x.nhan}</span>
            <span className="block text-xl font-bold tabular-nums text-ink">
              {x.so}{" "}
              <span className="text-xs font-medium text-ink-muted">{x.don}</span>
            </span>
          </span>
        </div>
      ))}
    </div>
  );
}

export function DieuPhoiNhanh({ alerts }: { alerts: DispatchAlert[] }) {
  return (
    <section className="rounded-card border border-line bg-surface p-3.5 shadow-card">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold text-ink">Điều phối nhanh</h2>
          <p className="text-label text-ink-muted">Các vấn đề cần xử lý ngay</p>
        </div>
        {alerts.length > 0 && (
          <span className="rounded-chip bg-danger-bg px-2 py-0.5 text-label font-semibold text-danger">
            {alerts.length} việc cần xử lý
          </span>
        )}
      </div>
      {alerts.length === 0 ? (
        <p className="mt-3 rounded-control bg-success-bg px-3 py-2 text-body text-success">
          Mọi trạm đang trong ngưỡng.
        </p>
      ) : (
        <ul className="mt-3 space-y-2">
          {alerts.slice(0, 6).map((a, i) => (
            <li
              key={`${a.type}-${a.room_code ?? i}`}
              className={`rounded-control border-l-3 px-3 py-2 ${
                a.severity === "critical"
                  ? "border-danger bg-danger-bg"
                  : "border-warning bg-warning-bg"
              }`}
            >
              <p
                className={`text-body font-semibold ${
                  a.severity === "critical" ? "text-danger" : "text-warning"
                }`}
              >
                {a.message}
              </p>
              {a.patients.length > 0 && (
                <p className="mt-0.5 truncate text-label text-ink-soft">
                  {a.patients
                    .slice(0, 4)
                    .map((p) => p.name ?? p.code ?? "—")
                    .join(" · ")}
                  {a.patients.length > 4 ? ` +${a.patients.length - 4}` : ""}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function SoDoPhong({ rooms }: { rooms: DispatchRoom[] }) {
  // TẦNG "CHƯA KHAI" LÀ MỘT TẦNG THẬT trong danh sách này, không bị giấu: một
  // phòng không khai tầng vẫn nhận bệnh nhân, và giấu nó đi là giấu luôn chỗ
  // đang quá tải.
  const tang = [...new Set(rooms.map((r) => r.floor ?? ""))].sort();
  const [chon, setChon] = useState<string | null>(null);
  const dangXem = chon ?? tang[0] ?? "";
  const cua = rooms.filter((r) => (r.floor ?? "") === dangXem);

  const mau = (r: DispatchRoom) =>
    !r.accepting
      ? "border-line bg-surface-muted text-ink-faint"
      : r.state === "critical"
        ? "border-danger/40 bg-danger-bg text-danger"
        : r.state === "warning"
          ? "border-warning/40 bg-warning-bg text-warning"
          : r.serving > 0
            ? "border-success/40 bg-success-bg text-success"
            : "border-line bg-surface text-ink-muted";

  return (
    <section className="rounded-card border border-line bg-surface p-3.5 shadow-card">
      <h2 className="text-sm font-semibold text-ink">Sơ đồ phòng đang dùng</h2>
      <div className="mt-2 flex flex-wrap items-center gap-3 text-label text-ink-muted">
        {[
          ["bg-surface border border-line", "Đang trống"],
          ["bg-success-bg", "Đang sử dụng"],
          ["bg-warning-bg", "Sắp trống"],
          ["bg-danger-bg", "Quá tải"],
        ].map(([cls, nhan]) => (
          <span key={nhan} className="inline-flex items-center gap-1.5">
            <span className={`size-2.5 rounded-full ${cls}`} /> {nhan}
          </span>
        ))}
      </div>

      <div className="mt-3 flex flex-wrap gap-1">
        {tang.map((t) => (
          <button
            key={t || "chua-khai"}
            type="button"
            onClick={() => setChon(t)}
            aria-pressed={t === dangXem}
            className={`rounded-chip px-2.5 py-1 text-xs font-semibold ${
              t === dangXem
                ? "bg-brand-600 text-white"
                : "bg-surface-muted text-ink-soft hover:bg-brand-50"
            }`}
          >
            {t ? tenTang(t) : "Chưa khai tầng"}
          </button>
        ))}
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-2">
        {cua.map((r) => (
          <div key={r.id} className={`rounded-control border px-2.5 py-2 ${mau(r)}`}>
            <p className="truncate text-xs font-bold text-ink">{r.name}</p>
            <p className="truncate text-label font-medium">
              {!r.accepting
                ? "Ngừng nhận"
                : r.serving > 0
                  ? `Đang khám${r.waiting > 0 ? ` · chờ ${r.waiting}` : ""}`
                  : r.waiting > 0
                    ? `Có ${r.waiting} đang chờ`
                    : "Trống"}
            </p>
            <p className="truncate text-label text-ink-muted">
              {r.node_name ?? r.node_code} · tối đa {r.capacity}
            </p>
          </div>
        ))}
        {cua.length === 0 && (
          <p className="col-span-full py-4 text-center text-body text-ink-muted">
            Tầng này chưa có phòng nào.
          </p>
        )}
      </div>
    </section>
  );
}
