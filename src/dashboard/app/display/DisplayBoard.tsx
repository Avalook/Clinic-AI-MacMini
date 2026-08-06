"use client";

// DisplayBoard — bảng gọi số của màn hình TV phòng chờ.
//
// Màn này CHỈ HIỂN THỊ. Thứ tự, khu vực, ai đang được gọi, và câu giải thích
// "được ưu tiên vì đã đặt lịch trước" đều do backend quyết
// (services/display_board_service.py + services/queue_order.py).
//
// Ba thứ đã sửa so với bản trước:
//   · thứ tự lấy theo LUẬT GỌI, không phải theo giờ hẹn;
//   · "đang gọi" đọc từ trạng thái LƯỢT KHÁM — bản cũ lọc `status ===
//     "IN_PROGRESS"` trên lịch hẹn, một giá trị mà ràng buộc CHECK của bảng đó
//     không cho phép tồn tại, nên nhánh ấy chưa bao giờ khớp dòng nào;
//   · bộ đếm 30 giây nay TẢI LẠI DỮ LIỆU. Trước đây nó chỉ `setNow(new Date())`
//     — tức chỉ nhích cái đồng hồ trên góc màn hình — trong khi chú thích ngay
//     đầu file ghi "Tự refresh mỗi 30s". Bảng số đứng im cả buổi.

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { VN_TZ } from "../../lib/datetime";

export interface DisplayZone {
  key: string;
  label: string;
  prefix?: string;
}

export interface DisplayItem {
  queue_number: string | null;
  zone_key: string | null;
  call_order: number | null;
  call_reason: string | null;
  /** Đang trong phòng khám (visit.status = IN_PROGRESS). */
  is_current: boolean;
  /** Đã check-in — người chưa đến không nằm trong hàng chờ. */
  waiting: boolean;
  promoted: boolean;
  /** Câu giải thích do backend soạn, để nó không lệch với lý do thật. */
  promoted_note: string | null;
}

interface Props {
  zones: DisplayZone[];
  items: DisplayItem[];
}

const LAM_MOI_MS = 30_000;

export default function DisplayBoard({ zones, items }: Props) {
  const router = useRouter();
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const t = setInterval(() => {
      setNow(new Date());
      // Đây mới là phần "tự refresh" thật: kéo lại dữ liệu từ server component.
      router.refresh();
    }, LAM_MOI_MS);
    return () => clearInterval(t);
  }, [router]);

  // Chỉ người ĐÃ đến mới nằm trong hàng chờ. Danh sách đã được backend xếp theo
  // thứ tự gọi — màn hình không xếp lại.
  const dangCho = items.filter((m) => m.waiting);

  const theoKhu = (key: string) => dangCho.filter((m) => m.zone_key === key);

  const timeStr = now.toLocaleTimeString("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: VN_TZ,
  });
  const dateStr = now.toLocaleDateString("vi-VN", {
    weekday: "long",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    timeZone: VN_TZ,
  });

  return (
    <div className="flex h-screen flex-col bg-ink text-white">
      <header className="flex items-center justify-between border-b border-white/10 px-8 py-4">
        <div className="text-2xl font-semibold tracking-wide">Dr4Women</div>
        <div className="text-right">
          <div className="text-3xl font-bold tabular-nums">{timeStr}</div>
          <div className="text-sm capitalize text-white/50">{dateStr}</div>
        </div>
      </header>

      <main className="grid flex-1 grid-cols-3 gap-4 p-6 lg:grid-cols-6">
        {zones.map((z) => {
          const rows = theoKhu(z.key);
          // "Đang gọi" là người đang trong phòng; chưa có ai vào thì là người
          // đứng đầu hàng chờ của khu đó.
          const current = rows.find((m) => m.is_current) ?? rows[0] ?? null;
          const next = rows.filter((m) => m !== current).slice(0, 3);
          return (
            <section
              key={z.key}
              className="flex flex-col rounded-2xl border border-white/10 bg-white/5 p-4"
            >
              <h2 className="text-sm font-semibold uppercase tracking-wide text-white/60">
                {z.label}
              </h2>
              <div className="mt-3 flex flex-1 flex-col items-center justify-center text-center">
                {current ? (
                  <>
                    <div className="text-5xl font-bold tabular-nums text-brand-300">
                      {current.queue_number ?? "—"}
                    </div>
                    <div className="mt-1 text-xs text-white/60">ĐANG GỌI</div>
                    {/* Câu trả lời cho "vì sao người kia vào trước tôi?" */}
                    {current.promoted_note && (
                      <div className="mt-1 text-[11px] leading-tight text-brand-200/80">
                        {current.promoted_note}
                      </div>
                    )}
                  </>
                ) : (
                  <div className="text-3xl font-bold text-white/20">—</div>
                )}
              </div>
              <div className="mt-3 border-t border-white/10 pt-2">
                <div className="text-[11px] text-white/40">Tiếp theo</div>
                <div className="mt-1 space-y-0.5">
                  {next.length === 0 ? (
                    <div className="text-xs text-white/30">—</div>
                  ) : (
                    next.map((m, i) => (
                      <div
                        key={`${z.key}-${m.queue_number ?? "?"}-${i}`}
                        className="text-sm font-medium tabular-nums text-white/70"
                      >
                        {m.queue_number ?? "—"}
                        {m.promoted && (
                          <span className="ml-1 align-middle text-[10px] text-brand-200/70">
                            ★
                          </span>
                        )}
                      </div>
                    ))
                  )}
                </div>
              </div>
            </section>
          );
        })}
      </main>

      <footer className="flex items-center justify-between border-t border-white/10 px-8 py-3 text-sm text-white/50">
        <div>
          Vui lòng chờ đến lượt số của mình · ★ = khách đã đặt lịch trước
        </div>
        <div>WiFi: Dr4Women · Hotline: 1900 0000</div>
      </footer>
    </div>
  );
}
