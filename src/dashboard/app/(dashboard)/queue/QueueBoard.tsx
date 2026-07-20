"use client";

// Bảng SỐ THỨ TỰ GỌI KHÁM — gom theo bác sĩ, mỗi bác sĩ 1 cột. Trong mỗi cột:
//   • "Đang khám" (visit IN_PROGRESS) tách lên trên.
//   • "Chờ gọi" xếp theo callRank() (ưu tiên người có hẹn đến đúng giờ).
// Gọi bệnh nhân theo TÊN; số vé chỉ là nhãn định danh. Tự làm mới 30s.

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { ListOrdered, Stethoscope, BellRing } from "lucide-react";
import { fmtTime, isVnMidnight } from "../../../lib/datetime";

export interface QueueRow {
  id: string;
  slot_start: string;
  status: string | null;
  queue_number: string | null;
  booking_channel: string | null;
  patient: { full_name: string | null; patient_code: string | null } | null;
  doctor: { full_name: string | null } | null;
  service: { name: string | null } | null;
  checked_in_at: string | null;
  visit_status: string | null;
  b3_ready: boolean; // đã có KQ lab về hết → chờ bác sĩ đọc (làn B3)
}

// Bỏ tiền tố chức danh trong tên bác sĩ ("BS Thành" → "Thành").
function cleanName(name: string): string {
  return name.replace(/^(BS\s*SA|BS|ĐD|TL)\s+/i, "").trim();
}

function isBooked(r: QueueRow): boolean {
  return !!r.booking_channel && r.booking_channel !== "WALK_IN";
}

export default function QueueBoard({
  rows,
  error,
}: {
  rows: QueueRow[];
  error: string | null;
}) {
  const router = useRouter();

  // Tự làm mới định kỳ — bảng treo tường / quầy lễ tân luôn thấy số mới nhất.
  useEffect(() => {
    const t = setInterval(() => router.refresh(), 30_000);
    return () => clearInterval(t);
  }, [router]);

  // Gom theo bác sĩ (key = tên bác sĩ; chưa phân → "Chưa phân bác sĩ").
  const groups = new Map<string, QueueRow[]>();
  for (const r of rows) {
    const key = r.doctor?.full_name ? cleanName(r.doctor.full_name) : "Chưa phân bác sĩ";
    const arr = groups.get(key);
    if (arr) arr.push(r);
    else groups.set(key, [r]);
  }
  const doctors = [...groups.entries()].sort((a, b) => a[0].localeCompare(b[0]));

  return (
    <div className="space-y-6">
      <header className="flex items-center gap-2">
        <ListOrdered size={22} className="text-[#9d2463]" />
        <div>
          <h1 className="text-xl font-semibold text-[#171717]">Số thứ tự gọi khám</h1>
          <p className="text-sm text-[#888888]">
            Gọi theo TÊN · người có hẹn đến đúng giờ được ưu tiên trước khách vãng lai ·
            số vé chỉ là nhãn định danh
          </p>
        </div>
      </header>

      {error && (
        <div className="rounded-md bg-[#fee2e2] px-3 py-2 text-sm text-[#dc2626]">
          Lỗi tải hàng đợi: {error}
        </div>
      )}

      {doctors.length === 0 ? (
        <p className="rounded-xl border border-[#f3cfe0] bg-[#fdf2f8] px-4 py-10 text-center text-sm text-[#a1a1aa]">
          Chưa có bệnh nhân nào đang chờ khám.
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {doctors.map(([name, list]) => {
            // Order is authoritative from the backend (/api/v1/queue → call_rank).
            // The board only groups + splits by flags; it does NOT rank.
            const ordered = list;
            // Làn "Chờ đọc KQ (B3)" tách RIÊNG khỏi "Đang khám" (vốn gộp lẫn đang-khám /
            // đang-ở-sono / đã-quay-lại) để bác sĩ thấy ngay ai đọc được luôn.
            const b3 = ordered.filter((r) => r.b3_ready);
            const inExam = ordered.filter(
              (r) => r.visit_status === "IN_PROGRESS" && !r.b3_ready,
            );
            const waiting = ordered.filter(
              (r) => r.visit_status !== "IN_PROGRESS" && !r.b3_ready,
            );
            return (
              <section
                key={name}
                className="overflow-hidden rounded-xl border border-[#f3cfe0] bg-white shadow-[0_1px_3px_rgba(236,72,153,0.08)]"
              >
                <div className="flex items-center justify-between bg-[#fce7f3] px-4 py-2.5">
                  <span className="flex items-center gap-1.5 text-sm font-semibold text-[#9d2463]">
                    <Stethoscope size={15} /> {name}
                  </span>
                  <span className="rounded-full bg-white px-2 py-0.5 text-xs font-medium text-[#9d2463]">
                    {list.length} chờ
                  </span>
                </div>

                {b3.length > 0 && (
                  <div className="border-b border-[#fde68a] bg-[#fffbeb] px-3 py-2">
                    <p className="mb-1 flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wide text-[#b45309]">
                      <BellRing size={12} /> Chờ đọc kết quả
                    </p>
                    <ul className="space-y-1">
                      {b3.map((r) => (
                        <QueueLine key={r.id} r={r} readback />
                      ))}
                    </ul>
                  </div>
                )}

                {inExam.length > 0 && (
                  <div className="border-b border-[#dcfce7] bg-[#f0fdf4] px-3 py-2">
                    <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-[#15803d]">
                      Đang khám
                    </p>
                    <ul className="space-y-1">
                      {inExam.map((r) => (
                        <QueueLine key={r.id} r={r} examining />
                      ))}
                    </ul>
                  </div>
                )}

                <ul className="divide-y divide-[#f3cfe0]">
                  {waiting.map((r, i) => (
                    <QueueLine key={r.id} r={r} order={i + 1} />
                  ))}
                  {waiting.length === 0 && inExam.length === 0 && (
                    <li className="px-4 py-4 text-center text-xs text-[#a1a1aa]">
                      Không còn ai chờ.
                    </li>
                  )}
                </ul>
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}

function QueueLine({
  r,
  order,
  examining = false,
  readback = false,
}: {
  r: QueueRow;
  order?: number;
  examining?: boolean;
  readback?: boolean;
}) {
  const booked = isBooked(r);
  return (
    <li className="flex items-center gap-3 px-3 py-2">
      {!examining && !readback && (
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[#fce7f3] text-xs font-bold text-[#9d2463]">
          {order}
        </span>
      )}
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold text-[#171717]">
          {r.patient?.full_name ?? "—"}
        </p>
        <p className="truncate text-[11px] text-[#888888]">
          {r.queue_number ? (
            <span className="font-mono text-[#9d2463]">Vé {r.queue_number}</span>
          ) : (
            <span className="text-[#c4c4c8]">Chưa cấp vé</span>
          )}
          {!isVnMidnight(r.slot_start) && booked ? ` · hẹn ${fmtTime(r.slot_start)}` : ""}
          {r.service?.name ? ` · ${r.service.name}` : ""}
        </p>
      </div>
      <span
        className={
          "shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium " +
          (readback
            ? "bg-[#fef3c7] text-[#b45309]"
            : booked
              ? "bg-[#fce7f3] text-[#9d2463]"
              : "bg-[#f4f4f5] text-[#52525b]")
        }
      >
        {readback ? "🔔 Chờ đọc" : booked ? "Có hẹn" : "Vãng lai"}
      </span>
    </li>
  );
}
