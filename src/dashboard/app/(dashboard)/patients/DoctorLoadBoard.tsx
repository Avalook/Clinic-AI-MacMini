"use client";

// Bảng "Tải hôm nay theo bác sĩ" — Lễ tân ở màn Tạo bệnh nhân (walk-in) NHÌN tải từng bác
// sĩ hôm nay để ĐỊNH TUYẾN ca walk-in tránh nghẽn (BS Thành = trạm chính, đông thì đẩy sang
// bác sĩ phụ). BẤM tên hoặc ô của bác sĩ nào → CHỌN bác sĩ đó cho ca (onPick). Giờ walk-in =
// hiện tại nên chỉ điền bác sĩ. Số khám hệ tự cấp khi check-in — không nhập ở đây.

import type { Option } from "./AppointmentBooking";

interface LoadAppt {
  slot_start: string;
  doctor_id: string | null;
  queue_number: string | null;
  status: string;
}

// Đã đến / đang khám (ghế xanh); COMPLETED = đã xong (xám); còn lại = chưa đến.
const ARRIVED = new Set(["CHECKED_IN", "IN_PROGRESS"]);

const STATUS_VN: Record<string, string> = {
  SCHEDULED: "Chưa đến",
  CSKH_CONFIRMED: "Chưa đến",
  CONFIRMED: "Chưa đến",
  CHECKED_IN: "Đã đến",
  IN_PROGRESS: "Đang khám",
  COMPLETED: "Đã khám xong",
};

const NO_DOCTOR = "Chưa phân bác sĩ";

function vnHHmm(iso: string): string {
  return new Date(iso).toLocaleTimeString("vi-VN", {
    timeZone: "Asia/Ho_Chi_Minh",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

// BS Thành = trạm nghẽn chính → ưu tiên đưa lên gần đầu (sau bác sĩ đang chọn).
function isMainDoctor(label: string): boolean {
  return /thành/i.test(label);
}

export default function DoctorLoadBoard({
  appts,
  doctors,
  selectedDoctorId,
  onPick,
}: {
  appts: LoadAppt[];
  doctors: Option[];
  selectedDoctorId: string;
  // Bấm chọn 1 bác sĩ trong bảng → điền vào form (id + nhãn hiển thị).
  onPick?: (doctorId: string, doctorLabel: string) => void;
}) {
  const labelOf = (id: string | null): string =>
    (id && doctors.find((d) => d.id === id)?.label) || NO_DOCTOR;

  // Hàng = TẤT CẢ bác sĩ ở cơ sở (kể cả 0 ca) + "Chưa phân" nếu có lịch chưa gán bác sĩ.
  const doctorIds: string[] = doctors.map((d) => d.id);
  if (appts.some((a) => !a.doctor_id)) doctorIds.push("");

  // Cột = các khung giờ CÓ lịch, tăng dần.
  const timeSet = new Set<string>();
  for (const a of appts) timeSet.add(vnHHmm(a.slot_start));
  const times = [...timeSet].sort();

  // (doctor_id|giờ) → ghế.
  const cellMap = new Map<string, LoadAppt[]>();
  for (const a of appts) {
    const key = `${a.doctor_id ?? ""}|${vnHHmm(a.slot_start)}`;
    const arr = cellMap.get(key) ?? [];
    arr.push(a);
    cellMap.set(key, arr);
  }

  // Sắp hàng: đang chọn → BS chính (Thành) → theo tên → "Chưa phân" cuối.
  doctorIds.sort((a, b) => {
    if (a === selectedDoctorId) return -1;
    if (b === selectedDoctorId) return 1;
    if (a === "") return 1;
    if (b === "") return -1;
    const ma = isMainDoctor(labelOf(a));
    const mb = isMainDoctor(labelOf(b));
    if (ma !== mb) return ma ? -1 : 1;
    return labelOf(a).localeCompare(labelOf(b), "vi");
  });

  const countFor = (id: string) =>
    appts.filter((a) => (a.doctor_id ?? "") === id).length;
  const arrivedFor = (id: string) =>
    appts.filter((a) => (a.doctor_id ?? "") === id && ARRIVED.has(a.status)).length;

  if (doctorIds.length === 0) {
    return (
      <p className="rounded-lg border border-line bg-surface-muted px-3 py-2 text-xs text-ink-muted">
        Chọn cơ sở để xem danh sách bác sĩ.
      </p>
    );
  }

  const pick = (id: string) => {
    if (id) onPick?.(id, labelOf(id));
  };

  return (
    <div className="space-y-1.5">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-ink-muted">
        <span className="font-medium text-ink">Tải hôm nay theo bác sĩ</span>
        <span className="inline-flex items-center gap-1">
          <span className="inline-block h-3 w-3 rounded border border-brand-100 bg-white" /> Chưa đến
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="inline-block h-3 w-3 rounded bg-success" /> Đã đến
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="inline-block h-3 w-3 rounded bg-line" /> Đã xong
        </span>
        {onPick && (
          <span className="font-medium text-brand-800">— Bấm tên/ô để chọn bác sĩ đỡ nghẽn</span>
        )}
      </div>
      <div className="overflow-x-auto rounded-xl border border-brand-100">
        <table className="border-separate border-spacing-1 p-2">
          <thead>
            <tr>
              <th className="sticky left-0 z-10 bg-white px-2 text-left text-[11px] font-medium text-ink-muted">
                Bác sĩ \ Giờ
              </th>
              {times.map((t) => (
                <th key={t} className="px-0.5 text-[10px] font-normal text-ink-faint">
                  {t}
                </th>
              ))}
              <th className="px-1 text-[10px] font-normal text-ink-faint">Tổng</th>
            </tr>
          </thead>
          <tbody>
            {doctorIds.map((id) => {
              const isSel = id === selectedDoctorId;
              const pickable = id !== "" && !!onPick;
              return (
                <tr key={id || NO_DOCTOR} className={isSel ? "bg-brand-50" : undefined}>
                  <td
                    className={
                      "sticky left-0 z-10 p-0 " + (isSel ? "bg-brand-50" : "bg-white")
                    }
                  >
                    <button
                      type="button"
                      disabled={!pickable}
                      onClick={() => pick(id)}
                      className={
                        "w-full whitespace-nowrap px-2 py-1 text-left text-xs " +
                        (isSel
                          ? "font-semibold text-brand-800"
                          : "font-medium text-ink") +
                        (pickable ? " cursor-pointer hover:bg-brand-100" : " cursor-default")
                      }
                    >
                      {labelOf(id)}
                    </button>
                  </td>
                  {times.map((t) => {
                    const cell = cellMap.get(`${id}|${t}`) ?? [];
                    return (
                      <td key={t} className="p-0 align-top">
                        <button
                          type="button"
                          disabled={!pickable}
                          onClick={() => pick(id)}
                          title={pickable ? `Chọn ${labelOf(id)} cho ca này` : undefined}
                          className={
                            "flex min-h-7 w-full flex-col items-center gap-0.5 rounded px-0.5 " +
                            (pickable ? "cursor-pointer hover:bg-brand-100" : "cursor-default")
                          }
                        >
                          {cell.map((a, i) => {
                            const arrived = ARRIVED.has(a.status);
                            const done = a.status === "COMPLETED";
                            const label =
                              a.queue_number?.trim() || (arrived ? "✓" : "•");
                            return (
                              <span
                                key={`${t}-${i}`}
                                title={`${t} · ${STATUS_VN[a.status] ?? a.status}${a.queue_number ? ` · số ${a.queue_number}` : ""}`}
                                className={
                                  "flex h-6 min-w-8 items-center justify-center rounded px-1 text-[10px] font-semibold " +
                                  (arrived
                                    ? "bg-success text-white"
                                    : done
                                      ? "bg-line text-ink-faint"
                                      : "border border-brand-100 bg-white text-brand-800")
                                }
                              >
                                {label}
                              </span>
                            );
                          })}
                        </button>
                      </td>
                    );
                  })}
                  <td
                    className={
                      "px-1 text-center text-[11px] " +
                      (isSel ? "font-semibold text-brand-800" : "text-ink-muted")
                    }
                  >
                    {countFor(id)}
                    {arrivedFor(id) > 0 && (
                      <span className="text-success"> ({arrivedFor(id)}↩)</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
