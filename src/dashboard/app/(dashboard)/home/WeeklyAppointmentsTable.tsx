"use client";

// Bảng "Lịch hẹn khám (check đặt lịch)" — TÁI CẤU TRÚC 2026-07-02 theo mô hình
// "rạp chiếu phim": gom theo NGÀY → KHUNG GIỜ 15' → BÁC SĨ TRỰC; mỗi bác sĩ tối
// đa 2 dòng lịch hẹn kênh thường (BN1/BN2) + 1 dòng khách vãng lai (WALK_IN).
// Khi chỗ vãng lai của khung còn trống (và khung chưa qua) hiện Ô XANH "đặt vào
// đây" — hôm nay thì bấm được, dẫn sang Tạo bệnh nhân với ngày/giờ/bác sĩ điền
// sẵn. Luật 2+1 nằm ở lib/slot-capacity (server chặn cứng — đây là hiển thị).
// Read-only với dữ liệu thật từ appointment; cột thao tác check-in/sinh hiệu
// giữ nguyên như bản trước.

import { useState, Fragment } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Printer, X } from "lucide-react";
import {
  canCheckin,
  canWriteIntake,
  isNurseRole,
  type ClinicRole,
} from "../../../lib/roles";
import ClinicalRecordForm from "../tasks/ClinicalRecordForm";
import { dayLabel, fmtDayMonth, todayVn } from "../../../lib/roster";
import { nowMs } from "../../../lib/datetime";
import { compareQueue } from "../../../lib/queue";
import { doctorName } from "../../../lib/doctor-name";
import {
  SLOT_MIN,
  WALKIN_CAP,
  slotBucketMs,
  isWalkinChannel,
  isDeadStatus,
} from "../../../lib/slot-capacity";

export interface WeekApptRow {
  id: string;
  slot_start: string;
  status: string;
  queue_number: string | null;
  doctor_id: string | null;
  booking_channel: string | null;
  phan_loai: string; // "Tái khám" | "Khám lần đầu" | "" (suy từ lịch sử hẹn)
  /** ĐÃ ghi sinh hiệu (đủ 3 vital bắt buộc) chưa — tắt "!" nhắc điều dưỡng. */
  has_vitals?: boolean;
  patient: {
    clinic_patient_id: string;
    full_name: string;
    patient_code: string;
    phone_primary: string | null;
    date_of_birth: string | null;
    phone_secondary: string | null;
    gender: string | null;
    ethnicity: string | null;
    nationality: string | null;
    occupation: string | null;
    patient_objection: string | null;
    address: string | null;
    guardian_name: string | null;
  } | null;
  doctor: { full_name: string } | null;
  service: { name: string } | null;
}
export interface ApptDay {
  date: string;
  items: WeekApptRow[];
}
/** Bác sĩ trực ca (work_roster LICH_KHAM) theo ngày — nuôi các nhóm bác sĩ
 *  hiện cả khi CHƯA có lịch trong khung (để thấy chỗ vãng lai còn trống). */
export type DutyByDate = Record<string, { id: string; name: string }[]>;

const NO_DOCTOR = "Chưa phân bác sĩ";
const SLOT_MS = SLOT_MIN * 60_000;

function PhanLoai({ value }: { value: string }) {
  if (!value) return <span className="text-[#c9a3b8]">—</span>;
  const first = value === "Khám lần đầu";
  return (
    <span
      className={
        "inline-block rounded-full px-2 py-0.5 text-[11px] font-medium " +
        (first ? "bg-[#dcfce7] text-[#15803d]" : "bg-[#fef3c7] text-[#b45309]")
      }
    >
      {value}
    </span>
  );
}

// Ô thân chung (viền lưới + padding gọn).
const CELL = "border-b border-r border-[#f3cfe0] px-2 py-1.5 align-top";
// Tiêu đề cột.
const TH =
  "border-b border-r border-[#f3cfe0] px-2 py-1.5 text-left text-[10px] font-semibold uppercase tracking-wide text-[#9d2463]";

const STATUS_VN: Record<string, string> = {
  SCHEDULED: "Chưa xác nhận",
  CSKH_CONFIRMED: "Đã xác nhận",
  CONFIRMED: "Đã xác nhận",
  CHECKED_IN: "Đã check-in",
  COMPLETED: "Đã khám xong",
  NO_SHOW: "Không đến",
  CANCELLED: "Đã huỷ",
  DOCTOR_DECLINED: "Bác sĩ từ chối",
};

// Nhãn khung 15' theo giờ VN: "17:00 - 17:15".
function bucketLabel(bucketMs: number): string {
  const hhmm = (ms: number) =>
    new Date(ms).toLocaleTimeString("vi-VN", {
      timeZone: "Asia/Ho_Chi_Minh",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  return `${hhmm(bucketMs)} - ${hhmm(bucketMs + SLOT_MS)}`;
}

// Giờ HH:MM (VN) của đầu khung — làm query ?time= cho link "đặt vào đây".
function bucketHHMM(bucketMs: number): string {
  return new Date(bucketMs).toLocaleTimeString("en-GB", {
    timeZone: "Asia/Ho_Chi_Minh",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

// Mô tả 1 dòng render sau khi gom khung giờ → bác sĩ (rowSpan tính sẵn).
interface RowDesc {
  key: string;
  bucket?: { label: string; span: number }; // chỉ dòng đầu của khung
  doctor?: { label: string; span: number }; // chỉ dòng đầu của nhóm bác sĩ
  appt?: WeekApptRow; // dòng lịch thật…
  free?: { href: string | null }; // …hoặc ô xanh "đặt vào đây" (href null = chỉ nhìn)
}

// Gom lịch 1 ngày thành các dòng render. duty = bác sĩ trực ngày đó (nhóm hiện
// cả khi chưa có lịch trong khung để thấy chỗ vãng lai trống).
function buildDayRows(
  day: ApptDay,
  duty: { id: string; name: string }[],
  now: number,
  canBook: boolean,
): RowDesc[] {
  const isToday = day.date === todayVn();
  // Khung giờ có ít nhất 1 lịch (mọi trạng thái — lịch huỷ vẫn hiện để check).
  const byBucket = new Map<number, WeekApptRow[]>();
  for (const a of day.items) {
    const b = slotBucketMs(a.slot_start);
    const list = byBucket.get(b) ?? [];
    list.push(a);
    byBucket.set(b, list);
  }
  const out: RowDesc[] = [];
  for (const bucketMs of [...byBucket.keys()].sort((x, y) => x - y)) {
    const inBucket = byBucket.get(bucketMs)!;
    const bucketNotPast = bucketMs >= now;
    // Thứ tự nhóm bác sĩ: bác sĩ TRỰC trước (theo thứ tự roster), rồi bác sĩ
    // khác có lịch (theo tên), "Chưa phân bác sĩ" cuối cùng.
    const groups: { id: string; label: string }[] = [];
    const seen = new Set<string>();
    if (bucketNotPast) {
      for (const d of duty) {
        groups.push({ id: d.id, label: doctorName(d.name) });
        seen.add(d.id);
      }
    }
    const extras = inBucket
      .filter((a) => !seen.has(a.doctor_id ?? ""))
      .map((a) => ({
        id: a.doctor_id ?? "",
        label: a.doctor?.full_name ? doctorName(a.doctor.full_name) : NO_DOCTOR,
      }))
      .filter((g, i, arr) => arr.findIndex((x) => x.id === g.id) === i)
      .sort((x, y) =>
        x.id === "" ? 1 : y.id === "" ? -1 : x.label.localeCompare(y.label, "vi"),
      );
    groups.push(...extras);

    const bucketRows: RowDesc[] = [];
    for (const g of groups) {
      const mine = inBucket.filter((a) => (a.doctor_id ?? "") === g.id);
      const regular = mine
        .filter((a) => !isWalkinChannel(a.booking_channel))
        .sort(compareQueue);
      const walkins = mine
        .filter((a) => isWalkinChannel(a.booking_channel))
        .sort(compareQueue);
      const walkinAlive = walkins.filter((a) => !isDeadStatus(a.status)).length;
      const groupRows: RowDesc[] = [];
      for (const a of [...regular, ...walkins]) {
        groupRows.push({ key: a.id, appt: a });
      }
      // Ô XANH "đặt vào đây": chỗ vãng lai còn trống + khung chưa qua. Chỉ ngày
      // HÔM NAY mới bấm được (walk-in là khách đến trực tiếp trong ngày); ngày
      // sau chỉ hiện trạng thái. Nhóm "Chưa phân bác sĩ" không có ô này.
      // CHỈ vai đặt lịch (CSKH/Lễ tân/QL/Trưởng ca) mới thấy hàng này — bác sĩ,
      // điều dưỡng không đặt lịch nên bỏ hẳn cho gọn.
      if (canBook && g.id && bucketNotPast && walkinAlive < WALKIN_CAP) {
        groupRows.push({
          key: `${bucketMs}-${g.id}-free`,
          free: {
            href: isToday
              ? `/patients/new?date=${day.date}&time=${encodeURIComponent(
                  bucketHHMM(bucketMs),
                )}&doctor=${g.id}`
              : null,
          },
        });
      }
      if (groupRows.length === 0) continue;
      groupRows[0].doctor = { label: g.label, span: groupRows.length };
      bucketRows.push(...groupRows);
    }
    if (bucketRows.length === 0) continue;
    bucketRows[0].bucket = { label: bucketLabel(bucketMs), span: bucketRows.length };
    out.push(...bucketRows);
  }
  return out;
}

export default function WeeklyAppointmentsTable({
  days,
  role,
  staffId,
  canWriteClinical = false,
  dutyByDate = {},
}: {
  days: ApptDay[];
  role: ClinicRole | null;
  staffId: string | null;
  canWriteClinical?: boolean;
  dutyByDate?: DutyByDate;
}) {
  const router = useRouter();
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selAppt, setSelAppt] = useState<WeekApptRow | null>(null);

  const showActions = canCheckin(role);
  // Điều dưỡng: KHÔNG check-in (việc Lễ tân) mà điền SINH HIỆU ngay trên lịch hẹn.
  const isNurse = isNurseRole(role);
  const showActionCol = showActions || isNurse;
  const nCols = showActionCol ? 6 : 5;

  async function act(
    id: string,
    action: "checkin" | "undo_checkin" | "no_show",
  ) {
    if (busyId) return;
    setBusyId(id);
    setError(null);
    const res = await fetch("/api/appointments", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, action }),
    });
    setBusyId(null);
    if (!res.ok) {
      setError((await res.json()).error ?? "Có lỗi xảy ra.");
      return;
    }
    router.refresh();
  }

  // Cả tuần KHÔNG có lịch → thẻ rỗng GỌN (không dựng bảng trống huơ).
  if (days.every((d) => d.items.length === 0)) {
    return (
      <div className="rounded-xl border border-dashed border-[#f3cfe0] bg-white px-4 py-10 text-center text-sm text-[#c084a8] shadow-[0_1px_3px_rgba(236,72,153,0.08)]">
        Chưa có lịch hẹn nào trong tuần này.
      </div>
    );
  }

  const now = nowMs();

  return (
    <div className="space-y-4">
      {error && (
        <div className="rounded-lg bg-[#fee2e2] px-3 py-2 text-xs text-[#dc2626]">
          {error}
        </div>
      )}
      <div className="overflow-auto rounded-xl border border-[#f3cfe0] bg-white shadow-[0_1px_3px_rgba(236,72,153,0.08)] max-h-[88vh] min-h-[180px] max-w-full">
        <table className="w-full min-w-max border-collapse text-xs">
          <thead className="sticky top-0 z-10">
            <tr className="bg-[#fce7f3]">
              <th className={`${TH} min-w-[92px]`}>Khung giờ</th>
              <th className={`${TH} min-w-[120px]`}>Bác sĩ</th>
              <th className={`${TH} min-w-[52px]`}>Số</th>
              <th className={`${TH} min-w-[200px]`}>Thông tin</th>
              <th className={`${TH} min-w-[110px]`}>Phân loại khám</th>
              {showActionCol && (
                <th className={`${TH} min-w-[150px]`}>
                  {isNurse ? "Sinh hiệu" : "Thao tác Check-in"}
                </th>
              )}
            </tr>
          </thead>
          <tbody>
            {days.map((day) => {
              const rows = buildDayRows(
                day,
                dutyByDate[day.date] ?? [],
                now,
                canWriteIntake(role),
              );
              return (
                <Fragment key={day.date}>
                  {/* Dòng tiêu đề NGÀY (gộp cả 5 hoặc 6 cột). */}
                  <tr className="bg-[#fdf2f8]">
                    <td
                      colSpan={nCols}
                      className="border-b border-[#f3cfe0] border-l-[3px] border-l-[#f3a8cc] px-2 py-1.5 text-sm font-semibold text-[#9d2463]"
                    >
                      {dayLabel(day.date)} · {fmtDayMonth(day.date)}
                      <span className="ml-2 rounded-full bg-white px-1.5 py-0.5 text-[10px] font-medium text-[#c084a8]">
                        {day.items.length} lịch
                      </span>
                    </td>
                  </tr>
                  {rows.length === 0 ? (
                    <tr>
                      <td
                        colSpan={nCols}
                        className="border-b border-[#f3cfe0] px-3 py-2 text-center text-[11px] text-[#c9c9cf]"
                      >
                        — chưa có lịch —
                      </td>
                    </tr>
                  ) : (
                    rows.map((r) => {
                      const a = r.appt;
                      return (
                        <tr
                          key={r.key}
                          className={r.free ? "bg-[#f0fdf4]" : "bg-white"}
                        >
                          {r.bucket && (
                            <td
                              rowSpan={r.bucket.span}
                              className={`${CELL} whitespace-nowrap bg-white font-medium text-[#171717]`}
                            >
                              {r.bucket.label}
                            </td>
                          )}
                          {r.doctor && (
                            <td
                              rowSpan={r.doctor.span}
                              className={`${CELL} whitespace-nowrap bg-white font-medium text-[#b83280]`}
                            >
                              {r.doctor.label}
                            </td>
                          )}
                          {a ? (
                            <>
                              <td className={`${CELL} whitespace-nowrap text-center text-[#52525b]`}>
                                {a.queue_number ?? "—"}
                              </td>
                              <td className={`${CELL} text-[#171717]`}>
                                {showActionCol ? (
                                  <button
                                    onClick={() => setSelAppt(a)}
                                    className="flex items-center gap-1.5 font-medium text-[#ec4899] hover:underline text-left"
                                  >
                                    {isNurse &&
                                      a.status === "CHECKED_IN" &&
                                      !a.has_vitals && (
                                        <span
                                          title="Cần điền sinh hiệu"
                                          className="inline-flex h-4 w-4 shrink-0 animate-pulse items-center justify-center rounded-full bg-[#dc2626] text-[10px] font-bold leading-none text-white"
                                        >
                                          !
                                        </span>
                                      )}
                                    {a.patient?.full_name ?? "—"}
                                  </button>
                                ) : (
                                  <span className="block font-medium">
                                    {a.patient?.full_name ?? "—"}
                                  </span>
                                )}
                                <span className="block font-mono text-[10px] text-[#888888]">
                                  {a.patient?.patient_code}
                                  {a.patient?.phone_primary
                                    ? ` · ${a.patient.phone_primary}`
                                    : ""}
                                  {a.service?.name ? ` · ${a.service.name}` : ""}
                                  {isWalkinChannel(a.booking_channel)
                                    ? " · vãng lai"
                                    : ""}
                                </span>
                              </td>
                              <td className={CELL}>
                                <PhanLoai value={a.phan_loai} />
                              </td>
                              {showActionCol && (
                                <td className={CELL}>
                                  {isNurse ? (
                                    ["CANCELLED", "NO_SHOW", "DOCTOR_DECLINED"].includes(
                                      a.status,
                                    ) ? (
                                      <span className="rounded-full bg-[#f4f4f5] px-2 py-0.5 text-[10px] font-medium text-[#52525b]">
                                        {STATUS_VN[a.status] ?? a.status}
                                      </span>
                                    ) : a.status !== "CHECKED_IN" &&
                                      a.status !== "COMPLETED" ? (
                                      // Chưa check-in → điều dưỡng CHƯA điền sinh hiệu
                                      // được (lễ tân phải check-in trước).
                                      <span className="text-[10px] text-[#a1a1aa]">
                                        Chờ lễ tân check-in
                                      </span>
                                    ) : (
                                      <div className="flex items-center gap-1.5">
                                        <button
                                          onClick={() => setSelAppt(a)}
                                          className="rounded bg-[#ec4899] px-2.5 py-1 text-[11px] font-semibold text-white hover:bg-[#db2777]"
                                        >
                                          Điền sinh hiệu
                                        </button>
                                        {a.status === "COMPLETED" && (
                                          <a
                                            href={`/print/${a.id}`}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="inline-flex min-h-7 items-center gap-1 rounded border border-[#bbf7d0] bg-white px-2 text-[11px] font-semibold text-[#15803d] hover:bg-[#f0fdf4]"
                                          >
                                            <Printer size={12} /> In phiếu
                                          </a>
                                        )}
                                      </div>
                                    )
                                  ) : a.status === "COMPLETED" ? (
                                    <div className="flex items-center gap-1.5">
                                      <span className="rounded-full bg-[#f4f4f5] px-2 py-0.5 text-[10px] font-medium text-[#52525b]">
                                        Đã khám xong
                                      </span>
                                      <a
                                        href={`/print/${a.id}`}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="inline-flex min-h-7 items-center gap-1 rounded border border-[#bbf7d0] bg-white px-2 text-[11px] font-semibold text-[#15803d] hover:bg-[#f0fdf4]"
                                      >
                                        <Printer size={12} /> In phiếu
                                      </a>
                                    </div>
                                  ) : a.status === "CHECKED_IN" ? (
                                    <div className="flex flex-col items-start gap-0.5">
                                      <span className="rounded-full bg-[#dcfce7] px-2 py-0.5 text-[10px] font-medium text-[#15803d]">
                                        Đang chờ khám
                                      </span>
                                      <button
                                        onClick={() => act(a.id, "undo_checkin")}
                                        disabled={busyId === a.id}
                                        className="text-[10px] text-[#a1a1aa] hover:text-[#71717a] font-medium disabled:opacity-50"
                                      >
                                        Hoàn tác check-in
                                      </button>
                                    </div>
                                  ) : ["SCHEDULED", "CSKH_CONFIRMED", "CONFIRMED"].includes(
                                      a.status,
                                    ) ? (
                                    <div className="flex items-center gap-2">
                                      <button
                                        onClick={() => act(a.id, "checkin")}
                                        disabled={busyId === a.id}
                                        className="rounded bg-[#ec4899] px-2.5 py-1 text-[11px] font-semibold text-white hover:bg-[#db2777] disabled:opacity-50"
                                      >
                                        {busyId === a.id ? "..." : "Check-in"}
                                      </button>
                                      <button
                                        onClick={() => act(a.id, "no_show")}
                                        disabled={busyId === a.id}
                                        className="text-[10px] text-[#a1a1aa] hover:text-[#dc2626] font-medium disabled:opacity-50"
                                      >
                                        Không đến
                                      </button>
                                    </div>
                                  ) : (
                                    <span className="rounded-full bg-[#f4f4f5] px-2 py-0.5 text-[10px] font-medium text-[#52525b]">
                                      {STATUS_VN[a.status] ?? a.status}
                                    </span>
                                  )}
                                </td>
                              )}
                            </>
                          ) : (
                            <>
                              <td className={`${CELL} text-center text-[#86efac]`}>—</td>
                              <td className={`${CELL}`}>
                                {r.free?.href ? (
                                  <Link
                                    href={r.free.href}
                                    className="inline-block rounded bg-[#dcfce7] px-2 py-1 text-[11px] font-semibold text-[#15803d] hover:bg-[#bbf7d0]"
                                  >
                                    ＋ Đặt lịch vào đây
                                  </Link>
                                ) : (
                                  <span className="inline-block rounded bg-[#dcfce7] px-2 py-1 text-[11px] font-medium text-[#15803d]/70">
                                    đặt vào đây (còn trống)
                                  </span>
                                )}
                              </td>
                              <td className={CELL}>
                                <PhanLoai value="Khám lần đầu" />
                              </td>
                              {showActionCol && <td className={CELL} />}
                            </>
                          )}
                        </tr>
                      );
                    })
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>

      {selAppt && (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/40" onClick={() => setSelAppt(null)}>
          <div className="h-full w-full max-w-lg border-l border-[#f3cfe0] bg-white p-4 shadow-[-8px_0_30px_rgba(0,0,0,0.12)] flex flex-col" onClick={(e) => e.stopPropagation()}>
            <div className="mb-2 flex items-center justify-between border-b border-[#f3cfe0] pb-2">
              <h3 className="text-base font-semibold text-[#9d2463]">Hành chính & Sinh hiệu bệnh nhân</h3>
              <button onClick={() => setSelAppt(null)} className="rounded-md p-1 text-[#9d2463] hover:bg-[#fce7f3]">
                <X size={18} />
              </button>
            </div>
            <div className="flex-1 min-h-0 overflow-y-auto">
              <ClinicalRecordForm
                appt={selAppt as any}
                staffId={staffId}
                vitalsOnly
                readOnly={!canWriteClinical}
                fill
                onClose={() => setSelAppt(null)}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
