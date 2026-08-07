"use client";

// Thêm/xoá phân công cho 1 tuần. Mỗi lần thêm = 1 ô (ngày · trạm · ca · NV).
// Ghi qua /api/roster rồi router.refresh() để nạp lại danh sách từ server.

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Trash2 } from "lucide-react";
import { INPUT, LABEL, BTN } from "../../form-ui";
import {
  STATIONS,
  STATION_LABEL,
  SHIFTS,
  SHIFT_LABEL,
  dayShort,
  fmtDayMonth,
  stationsForRole,
  defaultStationForRole,
  type Shift,
} from "../../../../lib/roster";
import { ROLE_LABEL, type ClinicRole } from "../../../../lib/roles";

export interface EditorRow {
  id: string;
  work_date: string;
  shift: Shift;
  station: string;
  staff_id: string | null;
  staff_name: string;
}

interface StaffOpt {
  id: string;
  name: string;
  role: ClinicRole;
}

export default function RosterEditor({
  weekStart,
  dates,
  staff,
  initialRows,
}: {
  weekStart: string;
  dates: string[];
  staff: StaffOpt[];
  initialRows: EditorRow[];
}) {
  const router = useRouter();
  const [workDate, setWorkDate] = useState(dates[0]);
  const [station, setStation] = useState(STATIONS[0].key);
  const [shift, setShift] = useState<Shift>("FULL");
  const [staffId, setStaffId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Trạm hợp lệ theo vai trò NV đã chọn (tránh "lễ tân → trạm bác sĩ").
  const selected = staff.find((s) => s.id === staffId) ?? null;
  const validStations = selected ? stationsForRole(selected.role) : STATIONS;

  async function add() {
    setError(null);
    if (!staffId) {
      setError("Chọn nhân viên.");
      return;
    }
    const picked = staff.find((s) => s.id === staffId);
    setBusy(true);
    const res = await fetch("/api/roster", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        week_start: weekStart,
        work_date: workDate,
        shift,
        station,
        staff_id: staffId,
        staff_name: picked?.name ?? "",
      }),
    });
    setBusy(false);
    if (!res.ok) {
      const j = await res.json();
      setError(j.error ?? "Lỗi khi thêm.");
      return;
    }
    setStaffId("");
    router.refresh();
  }

  async function remove(id: string) {
    setError(null);
    setBusy(true);
    const res = await fetch("/api/roster", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id }),
    });
    setBusy(false);
    if (!res.ok) {
      // Trước đây chỉ có nhánh `if (res.ok)`. Nghĩa là 403 — thứ Trưởng ca gặp
      // mỗi lần bấm — biến mất không dấu vết: ô vẫn nguyên, không báo gì, người
      // dùng bấm lại và tưởng mạng chậm.
      const chi_tiet = await res
        .json()
        .then((d: { error?: string }) => d.error)
        .catch(() => null);
      setError(chi_tiet ?? `Không xoá được ca (lỗi ${res.status}).`);
      return;
    }
    setError(null);
    router.refresh();
  }

  const byDate = dates
    .map((d) => ({
      date: d,
      items: initialRows.filter((r) => r.work_date === d),
    }))
    .filter((g) => g.items.length > 0);

  return (
    <div className="space-y-4">
      {/* Form thêm */}
      <section className="rounded-card border border-line bg-surface p-5 shadow-card">
        <h2 className="mb-4 text-sm font-semibold text-ink">
          Thêm phân công
        </h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div>
            <label className={LABEL}>Ngày</label>
            <select
              value={workDate}
              onChange={(e) => setWorkDate(e.target.value)}
              className={INPUT}
            >
              {dates.map((d) => (
                <option key={d} value={d}>
                  {dayShort(d)} · {fmtDayMonth(d)}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className={LABEL}>Vị trí</label>
            <select
              value={station}
              onChange={(e) => setStation(e.target.value)}
              className={INPUT}
              disabled={!staffId}
            >
              {validStations.map((s) => (
                <option key={s.key} value={s.key}>
                  {s.label}
                </option>
              ))}
            </select>
            {!staffId && (
              <p className="mt-1 text-[11px] text-ink-faint">
                Chọn nhân viên trước — vị trí sẽ lọc theo chức danh.
              </p>
            )}
          </div>
          <div>
            <label className={LABEL}>Ca</label>
            <select
              value={shift}
              onChange={(e) => setShift(e.target.value as Shift)}
              className={INPUT}
            >
              {SHIFTS.map((s) => (
                <option key={s} value={s}>
                  {SHIFT_LABEL[s]}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className={LABEL}>Nhân viên (chức danh — tên)</label>
            <select
              value={staffId}
              onChange={(e) => {
                const id = e.target.value;
                setStaffId(id);
                // Đổi NV → tự đặt lại vị trí mặc định theo chức danh (tránh lệch).
                const r = staff.find((s) => s.id === id)?.role ?? null;
                if (r) setStation(defaultStationForRole(r));
              }}
              className={INPUT}
            >
              <option value="">— Chọn nhân viên —</option>
              {staff.map((s) => (
                <option key={s.id} value={s.id}>
                  {ROLE_LABEL[s.role]} — {s.name}
                </option>
              ))}
            </select>
          </div>
        </div>
        {error && (
          <p className="mt-3 rounded bg-danger-bg px-3 py-2 text-sm text-danger">
            {error}
          </p>
        )}
        <div className="mt-4">
          <button onClick={add} disabled={busy} className={BTN}>
            {busy ? "Đang lưu..." : "+ Thêm vào lịch"}
          </button>
        </div>
      </section>

      {/* Danh sách đã phân công */}
      {byDate.length === 0 ? (
        <div className="rounded-card border border-line bg-surface px-4 py-8 text-center text-sm text-ink-muted shadow-card">
          Tuần này chưa có phân công nào.
        </div>
      ) : (
        <div className="space-y-2">
          {byDate.map((g) => (
            <div
              key={g.date}
              className="rounded-card border border-line bg-surface p-3 shadow-card"
            >
              <p className="mb-2 text-sm font-semibold text-ink">
                {dayShort(g.date)} · {fmtDayMonth(g.date)}
              </p>
              <ul className="divide-y divide-surface-sunken">
                {g.items.map((it) => (
                  <li
                    key={it.id}
                    className="flex items-center justify-between gap-2 py-1.5 text-sm"
                  >
                    <span className="min-w-0 text-ink-soft">
                      <span className="font-medium text-ink">
                        {it.staff_name}
                      </span>{" "}
                      · {STATION_LABEL[it.station] ?? it.station}
                      {it.shift !== "FULL" && (
                        <span className="text-ink-faint">
                          {" "}
                          ({SHIFT_LABEL[it.shift]})
                        </span>
                      )}
                    </span>
                    <button
                      onClick={() => remove(it.id)}
                      disabled={busy}
                      aria-label="Xoá"
                      className="shrink-0 rounded-md p-1.5 text-ink-faint hover:bg-danger-bg hover:text-danger disabled:opacity-50"
                    >
                      <Trash2 size={15} />
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
