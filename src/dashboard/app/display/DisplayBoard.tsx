"use client";

// Bảng gọi số của phòng chờ — dựng theo đúng bản thiết kế Quang gửi 06/08:
// nền sáng, sáu khu, mỗi khu có ĐANG GỌI (số to + tên phòng) → TIẾP THEO →
// ĐANG CHỜ (lưới số nhỏ), và một dải hướng dẫn cho khách ở dưới.
//
// Màn này CHỈ HIỂN THỊ. Thứ tự, khu vực, ai đang được gọi và câu giải thích
// "được ưu tiên vì đã đặt lịch trước" đều do backend quyết
// (services/display_board_service.py + services/queue_order.py).
//
// KHÔNG có tên bệnh nhân ở đây, và cũng không TẢI VỀ tên bệnh nhân — màn này
// treo giữa phòng chờ, nên thứ gì trình duyệt nhận được là thứ công khai. Ràng
// buộc đó có bài kiểm canh ở phía backend.

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { VN_TZ } from "../../lib/datetime";

export interface DisplayZone {
  key: string;
  label: string;
  /** Tiền tố số của khu: C007, SA025, X012, T005. */
  prefix?: string;
}

export interface DisplayItem {
  queue_number: string | null;
  zone_key: string | null;
  call_order: number | null;
  call_reason: string | null;
  /** Đang trong phòng khám (visit.status = IN_PROGRESS). */
  is_current: boolean;
  /** Đã đến và chưa khám xong. */
  waiting: boolean;
  promoted: boolean;
  promoted_note: string | null;
  /** Tên PHÒNG, để chỉ đường cho người vừa được gọi. */
  room_name: string | null;
}

interface Props {
  zones: DisplayZone[];
  items: DisplayItem[];
  clinicName?: string;
  footerText?: string;
  footerInfo?: string;
}

const LAM_MOI_MS = 30_000;

/** "994" + tiền tố "C" → "C994"; giữ ba chữ số cho dễ đọc từ xa. */
function soHienThi(queueNumber: string | null, prefix?: string): string {
  const so = (queueNumber ?? "").trim();
  if (!so) return "—";
  if (!prefix) return so;
  return /^\d+$/.test(so) ? `${prefix}${so.padStart(3, "0")}` : `${prefix}${so}`;
}

export default function DisplayBoard({
  zones,
  items,
  clinicName,
  footerText,
  footerInfo,
}: Props) {
  const router = useRouter();
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const t = setInterval(() => {
      setNow(new Date());
      // Đây mới là phần "tự làm mới" thật. Bản trước chỉ gọi setNow() — nhích
      // cái đồng hồ trên góc màn hình trong khi bảng số đứng im cả buổi.
      router.refresh();
    }, LAM_MOI_MS);
    return () => clearInterval(t);
  }, [router]);

  const dangCho = items.filter((m) => m.waiting);
  const theoKhu = (key: string) => dangCho.filter((m) => m.zone_key === key);

  const gio = now.toLocaleTimeString("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: VN_TZ,
  });
  const thu = now.toLocaleDateString("vi-VN", {
    weekday: "long",
    timeZone: VN_TZ,
  });
  const ngay = now.toLocaleDateString("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    timeZone: VN_TZ,
  });

  return (
    <div className="flex min-h-screen flex-col bg-slate-50 text-slate-900">
      <header className="flex items-center justify-between gap-6 border-b border-slate-200 bg-white px-8 py-4">
        <div className="text-2xl font-bold tracking-tight text-teal-700">
          {clinicName || "ClinicAI"}
        </div>
        <div className="text-center">
          <h1 className="text-2xl font-bold tracking-wide text-slate-800 xl:text-3xl">
            PHÒNG CHỜ — THÔNG BÁO LƯỢT KHÁM
          </h1>
          <p className="mt-0.5 text-sm text-slate-500">
            Kính chào Quý khách! {clinicName || "ClinicAI"} luôn đồng hành cùng
            sức khoẻ của bạn.
          </p>
        </div>
        <div className="flex items-center gap-4">
          <div className="text-4xl font-bold tabular-nums text-teal-700">
            {gio}
          </div>
          <div className="border-l border-slate-200 pl-4 text-sm leading-tight text-slate-500">
            <div className="capitalize">{thu}</div>
            <div className="tabular-nums">{ngay}</div>
          </div>
        </div>
      </header>

      <main className="grid flex-1 grid-cols-2 gap-4 p-5 md:grid-cols-3 xl:grid-cols-6">
        {zones.map((z) => {
          const rows = theoKhu(z.key);
          const dangGoi = rows.find((m) => m.is_current) ?? rows[0] ?? null;
          const conLai = rows.filter((m) => m !== dangGoi);
          const tiepTheo = conLai[0] ?? null;
          const xepHang = conLai.slice(1, 10);

          return (
            <section
              key={z.key}
              className="flex flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"
            >
              <h2 className="border-b border-slate-100 px-3 py-2.5 text-center text-sm font-bold uppercase tracking-wide text-teal-700">
                {z.label}
              </h2>

              {/* ĐANG GỌI — phần duy nhất người ngồi xa cần đọc được. */}
              <div className="bg-teal-50/60 px-3 py-4 text-center">
                <div className="text-[11px] font-semibold tracking-widest text-slate-500">
                  ĐANG GỌI
                </div>
                <div className="mt-1 text-4xl font-bold tabular-nums leading-none text-teal-700 xl:text-5xl">
                  {dangGoi ? soHienThi(dangGoi.queue_number, z.prefix) : "—"}
                </div>
                {dangGoi?.room_name ? (
                  <div className="mt-1 text-[11px] font-semibold uppercase text-slate-500">
                    {dangGoi.room_name}
                  </div>
                ) : null}
                {/* Câu trả lời cho "vì sao người kia vào trước tôi?" */}
                {dangGoi?.promoted_note ? (
                  <div className="mt-1 text-[10px] leading-tight text-teal-600">
                    {dangGoi.promoted_note}
                  </div>
                ) : null}
              </div>

              <div className="border-t border-slate-100 px-3 py-3 text-center">
                <div className="text-[11px] font-semibold tracking-widest text-slate-400">
                  TIẾP THEO
                </div>
                <div className="mt-0.5 text-2xl font-bold tabular-nums text-slate-700">
                  {tiepTheo ? soHienThi(tiepTheo.queue_number, z.prefix) : "—"}
                </div>
              </div>

              <div className="flex-1 border-t border-slate-100 px-2.5 py-2.5">
                <div className="text-center text-[11px] font-semibold tracking-widest text-slate-400">
                  ĐANG CHỜ
                </div>
                {xepHang.length === 0 ? (
                  <div className="mt-2 text-center text-xs text-slate-300">—</div>
                ) : (
                  <div className="mt-2 grid grid-cols-3 gap-1">
                    {xepHang.map((m, i) => (
                      <span
                        key={`${z.key}-${m.queue_number ?? "?"}-${i}`}
                        className="rounded-md bg-slate-100 py-1 text-center text-[11px] font-medium tabular-nums text-slate-600"
                      >
                        {soHienThi(m.queue_number, z.prefix)}
                        {m.promoted ? (
                          <span className="ml-0.5 align-middle text-[9px] text-teal-600">
                            ★
                          </span>
                        ) : null}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </section>
          );
        })}
      </main>

      <footer className="border-t border-slate-200 bg-white px-8 py-3">
        <div className="flex flex-wrap items-center justify-center gap-x-8 gap-y-2 text-xs text-slate-500">
          <span className="font-bold uppercase text-teal-700">
            Hướng dẫn dành cho Quý khách
          </span>
          <span>{footerText || "Vui lòng theo dõi số thứ tự trên màn hình và giữ trật tự trong khu vực chờ."}</span>
          <span>Khi đến lượt, vui lòng di chuyển đến đúng khu vực được gọi.</span>
          <span className="text-teal-700">★ = khách đã đặt lịch trước</span>
          {footerInfo ? <span>{footerInfo}</span> : null}
        </div>
      </footer>
    </div>
  );
}
