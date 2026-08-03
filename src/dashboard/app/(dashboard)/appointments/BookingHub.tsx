"use client";

// BookingHub — Hub Đặt lịch hẹn CSKH 3 cột hoàn chỉnh.
// Cột 1 (Trái - 280px): Khách hàng đang chọn (xếp trên) + Tìm kiếm khách hàng có sẵn (dài hơn) + Thông tin y tế & Lịch sử đặt hẹn.
// Cột 2 (Giữa - 1fr): Bảng lưới giờ chuẩn mockup (Cột đầu = Giờ, các ô KHÔNG ghi lại giờ, màu & trạng thái Có thể đặt / Còn 1 chỗ / Đã đầy / Đang giữ / Đang chọn ✓).
// Cột 3 (Phải - 320px): Panel Xác nhận thông tin đặt lịch (Sức chứa 1/3 đã đặt, Checklist, Đặt lịch hẹn).

import { useState, useMemo } from "react";
import {
  Calendar as CalendarIcon,
  Clock,
  User,
  Users,
  CheckCircle2,
  X,
  Search,
  Phone,
  Filter,
  ChevronLeft,
  ChevronRight,
  Info,
  UserPlus,
  UserCheck,
  Mail,
  MapPin,
  Pencil,
  ChevronDown,
  History,
} from "lucide-react";
import Link from "next/link";
import { slotRange } from "@/lib/datetime";
import { useBookingPolicy } from "../BookingPolicyContext";
import NewPatientForm, {
  type Option,
  type ProvinceOpt,
} from "../patients/new/NewPatientForm";

export interface PatientLite {
  clinic_patient_id: string;
  patient_code: string;
  full_name: string;
  phone_primary: string | null;
  date_of_birth: string | null;
  gender: string | null;
  address: string | null;
}

export interface ApptLite {
  id: string;
  slot_start: string;
  status: string;
  doctor_id: string | null;
  service_type_id: string | null;
  clinic_patient_id: string | null;
}

interface Props {
  locations: Option[];
  services: Option[];
  doctors: Option[];
  provinces: ProvinceOpt[];
  patients: PatientLite[];
  appts: ApptLite[];
}

const TIME_SLOTS = [
  "08:00",
  "08:15",
  "08:30",
  "08:45",
  "09:00",
  "09:15",
  "09:30",
  "09:45",
  "10:00",
  "10:15",
  "10:30",
  "10:45",
  "11:00",
  "11:15",
  "11:30",
  "11:45",
  "14:00",
  "14:15",
  "14:30",
  "14:45",
  "15:00",
  "15:15",
  "15:30",
  "15:45",
  "16:00",
  "16:15",
  "16:30",
  "16:45",
  "17:00",
];

const WEEK_DAYS = [
  { dayName: "T2", dateStr: "11/05", isoDate: "2026-05-11" },
  { dayName: "T3", dateStr: "12/05", isoDate: "2026-05-12" },
  { dayName: "T4", dateStr: "13/05", isoDate: "2026-05-13" },
  { dayName: "T5", dateStr: "14/05", isoDate: "2026-05-14" },
  { dayName: "T6", dateStr: "15/05", isoDate: "2026-05-15" },
  { dayName: "T7", dateStr: "16/05", isoDate: "2026-05-16" },
  { dayName: "CN", dateStr: "17/05", isoDate: "2026-05-17" },
];

/** Giờ mở cửa theo luật Dr4Women (lib/roster.ts):
 *  T2–T6 (Ngày thường): Chỉ khám ngoài giờ/buổi tối 17:00 – 23:00.
 *  T7–CN (Cuối tuần): Khám cả ngày 08:00 – 23:00.
 */
function generateSlotsForDate(isoDate: string): string[] {
  const dow = new Date(isoDate + "T00:00:00Z").getUTCDay();
  const isWeekend = dow === 0 || dow === 6;
  const startHour = isWeekend ? 8 : 17;
  const endHour = 22;

  const slots: string[] = [];
  for (let h = startHour; h <= endHour; h++) {
    const hh = String(h).padStart(2, "0");
    for (let m = 0; m < 60; m += 15) {
      const mm = String(m).padStart(2, "0");
      slots.push(`${hh}:${mm}`);
    }
  }
  return slots;
}

type SlotTone = "available" | "few" | "holding" | "full" | "selected";

interface CellStatus {
  tone: SlotTone;
  label: string;
  sub: string;
  bookedCount: number;
  maxCap: number;
}

export default function BookingHub({
  locations,
  services,
  doctors,
  provinces,
  patients,
  appts,
}: Props) {
  const policy = useBookingPolicy();
  const dynamicCap = (policy?.regularCap ?? 3) + (policy?.walkinCap ?? 0);

  const [mode, setMode] = useState<"grid" | "new_patient">("grid");
  const [selectedDateIso, setSelectedDateIso] = useState("2026-05-15");

  const timeSlots = useMemo(
    () => generateSlotsForDate(selectedDateIso),
    [selectedDateIso],
  );

  // Clean Service Names
  const cleanServices = useMemo(
    () =>
      services.map((s) => ({
        ...s,
        label: s.label.replace(/^[\*\#\s]+/, "").trim(),
      })),
    [services],
  );

  const [selectedServiceId, setSelectedServiceId] = useState<string>(
    cleanServices[0]?.id ?? "",
  );
  const [selectedDoctorId, setSelectedDoctorId] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedPatientId, setSelectedPatientId] = useState<string | null>(
    patients[0]?.clinic_patient_id ?? null,
  );

  const activePatient = useMemo(
    () =>
      patients.find((p) => p.clinic_patient_id === selectedPatientId) ??
      patients[0] ??
      null,
    [patients, selectedPatientId],
  );

  // Selected Slot
  const [selectedSlot, setSelectedSlot] = useState<{
    doctorId: string;
    doctorName: string;
    time: string;
  }>({
    doctorId: doctors[0]?.id ?? "",
    doctorName: doctors[0]?.label ?? "Bác sĩ",
    time: "18:00",
  });

  const [note, setNote] = useState("");
  const [chkCustomer, setChkCustomer] = useState(true);
  const [chkService, setChkService] = useState(true);
  const [chkDocSlot, setChkDocSlot] = useState(true);
  const [confirmedMsg, setConfirmedMsg] = useState<string | null>(null);
  const [bookingLoading, setBookingLoading] = useState(false);

  // Active doctors list
  const activeDoctors = useMemo(() => {
    if (selectedDoctorId === "all") return doctors.slice(0, 3);
    const doc = doctors.find((d) => d.id === selectedDoctorId);
    return doc ? [doc] : doctors.slice(0, 3);
  }, [doctors, selectedDoctorId]);

  // Handle doctor filter selection
  function handleDoctorFilterChange(docId: string) {
    setSelectedDoctorId(docId);
    if (docId !== "all") {
      const doc = doctors.find((d) => d.id === docId);
      if (doc) {
        setSelectedSlot((prev) => ({
          ...prev,
          doctorId: doc.id,
          doctorName: doc.label,
        }));
      }
    }
  }

  // Filtered patients for search list
  const filteredPatients = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return patients;
    return patients.filter(
      (p) =>
        p.full_name.toLowerCase().includes(q) ||
        (p.phone_primary ?? "").includes(q) ||
        p.patient_code.toLowerCase().includes(q),
    );
  }, [patients, searchQuery]);

  // Calculate Cell Status with dynamic capacity from booking policy!
  function getCellStatus(docId: string, time: string): CellStatus {
    const maxCap = Math.max(1, dynamicCap);
    const isSelected =
      selectedSlot.doctorId === docId && selectedSlot.time === time;
    if (isSelected) {
      return {
        tone: "selected",
        label: `Còn ${Math.max(0, maxCap - 1)} chỗ`,
        sub: `1/${maxCap}`,
        bookedCount: 1,
        maxCap,
      };
    }

    const matchingAppts = appts.filter((a) => {
      if (a.doctor_id !== docId) return false;
      const apptTime = a.slot_start.slice(11, 16);
      return apptTime === time && a.status !== "CANCELLED";
    });
    const bookedCount = matchingAppts.length;
    const isHolding = matchingAppts.some(
      (a) => a.status === "WAITING" || a.status === "CSKH_CONFIRMED",
    );

    if (bookedCount >= maxCap) {
      return {
        tone: "full",
        label: "Đã đầy",
        sub: `${maxCap}/${maxCap}`,
        bookedCount,
        maxCap,
      };
    }
    if (isHolding) {
      return {
        tone: "holding",
        label: "Đang giữ",
        sub: `${bookedCount}/${maxCap}`,
        bookedCount,
        maxCap,
      };
    }
    if (bookedCount > 0) {
      const remaining = maxCap - bookedCount;
      return {
        tone: "few",
        label: `Còn ${remaining} chỗ`,
        sub: `${bookedCount}/${maxCap}`,
        bookedCount,
        maxCap,
      };
    }
    return {
      tone: "available",
      label: "Có thể đặt",
      sub: `0/${maxCap}`,
      bookedCount: 0,
      maxCap,
    };
  }

  // Current slot capacity summary for right panel
  const selectedCellStatus = useMemo(
    () => getCellStatus(selectedSlot.doctorId, selectedSlot.time),
    [selectedSlot, appts],
  );

  async function handleConfirmBooking() {
    if (!activePatient || !selectedSlot.doctorId) return;
    setBookingLoading(true);
    try {
      const slotMins = policy?.slotMinutes ?? 15;
      const timeDisplay = slotRange(selectedSlot.time, slotMins);

      // Compute slot_start and slot_end in ISO string format
      const targetDate = selectedDateIso || new Date().toISOString().slice(0, 10);
      const [startH, startM] = selectedSlot.time.split(":").map(Number);
      const totalStartMin = (startH ?? 0) * 60 + (startM ?? 0);
      const totalEndMin = totalStartMin + slotMins;
      const endH = String(Math.floor(totalEndMin / 60)).padStart(2, "0");
      const endM = String(totalEndMin % 60).padStart(2, "0");

      const slotStartIso = `${targetDate}T${selectedSlot.time}:00+07:00`;
      const slotEndIso = `${targetDate}T${endH}:${endM}:00+07:00`;

      const res = await fetch("/api/appointments", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          clinic_patient_id: activePatient.clinic_patient_id,
          doctor_id: selectedSlot.doctorId,
          service_type_id: selectedServiceId || cleanServices[0]?.id,
          location_id: locations[0]?.id,
          slot_start: slotStartIso,
          slot_end: slotEndIso,
          notes: note,
        }),
      });

      if (res.ok) {
        setConfirmedMsg(
          `Đã đặt lịch hẹn thành công cho ${activePatient.full_name} vào khung giờ ${timeDisplay} với ${selectedSlot.doctorName}!`,
        );
      } else {
        const err = await res.json().catch(() => ({}));
        alert(
          `Lỗi đặt lịch: ${err.error || err.message || err.detail || "Không thể đặt lịch"}`,
        );
      }
    } finally {
      setBookingLoading(false);
    }
  }

  const selectedServiceName =
    cleanServices.find((s) => s.id === selectedServiceId)?.label ??
    "Khám Phụ khoa";

  return (
    <div className="space-y-4">


      {confirmedMsg && (
        <div className="flex items-center justify-between rounded-2xl border border-success/30 bg-success/10 p-3.5 text-xs text-success shadow-xs">
          <div className="flex items-center gap-2">
            <CheckCircle2 size={16} />
            <span className="font-semibold">{confirmedMsg}</span>
          </div>
          <button
            onClick={() => setConfirmedMsg(null)}
            className="text-success hover:underline"
          >
            <X size={14} />
          </button>
        </div>
      )}

      {/* Mode 1: New Patient Intake Form */}
      {mode === "new_patient" ? (
        <div className="rounded-2xl border border-line bg-surface p-4 shadow-card">
          <div className="mb-4 border-b border-line pb-3">
            <h2 className="text-base font-bold text-ink flex items-center gap-2">
              <UserPlus className="size-4 text-brand-600" />
              Nhập thông tin hành chính &amp; Đặt lịch hẹn cho khách hàng mới
            </h2>
            <p className="text-xs text-ink-muted mt-0.5">
              Điền đầy đủ thông tin hành chính của khách hàng lần đầu đến phòng khám
            </p>
          </div>
          <NewPatientForm
            role="CSKH"
            locations={locations}
            services={cleanServices}
            doctors={doctors}
            provinces={provinces}
            variant="full"
          />
        </div>
      ) : (
        /* Mode 2: 3-Column Standard Layout (Left: Patient Cards, Middle: Slot Grid, Right: Confirm Panel) */
        <div className="space-y-4">
          {/* Top 4 Summary Stat Cards */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div className="flex items-center gap-3.5 rounded-2xl border border-line bg-surface p-3.5 shadow-card">
              <div className="grid size-11 shrink-0 place-items-center rounded-2xl bg-brand-50 text-brand-700">
                <CalendarIcon className="size-5" />
              </div>
              <div>
                <p className="text-xs font-medium text-ink-muted">Lịch hôm nay</p>
                <p className="text-xl font-bold text-ink">42</p>
              </div>
            </div>

            <div className="flex items-center gap-3.5 rounded-2xl border border-line bg-surface p-3.5 shadow-card">
              <div className="grid size-11 shrink-0 place-items-center rounded-2xl bg-emerald-50 text-emerald-600">
                <User className="size-5" />
              </div>
              <div>
                <p className="text-xs font-medium text-ink-muted">Còn chỗ</p>
                <p className="text-xl font-bold text-ink">18</p>
              </div>
            </div>

            <div className="flex items-center gap-3.5 rounded-2xl border border-line bg-surface p-3.5 shadow-card">
              <div className="grid size-11 shrink-0 place-items-center rounded-2xl bg-sky-50 text-sky-600">
                <Clock className="size-5" />
              </div>
              <div>
                <p className="text-xs font-medium text-ink-muted">Đang giữ</p>
                <p className="text-xl font-bold text-ink">4</p>
              </div>
            </div>

            <div className="flex items-center gap-3.5 rounded-2xl border border-line bg-surface p-3.5 shadow-card">
              <div className="grid size-11 shrink-0 place-items-center rounded-2xl bg-teal-50 text-teal-600">
                <CheckCircle2 className="size-5" />
              </div>
              <div>
                <p className="text-xs font-medium text-ink-muted">Đã xác nhận</p>
                <p className="text-xl font-bold text-ink">20</p>
              </div>
            </div>
          </div>

          {/* Stepper (1 Khách hàng -> 2 Khung giờ -> 3 Xác nhận) */}
          <div className="flex items-center justify-center gap-4 rounded-2xl border border-line bg-surface py-2.5 px-4 text-xs font-medium text-ink-muted shadow-card">
            <div className="flex items-center gap-2">
              <span className="grid size-5 place-items-center rounded-full bg-emerald-600 text-[11px] font-bold text-white">
                ✓
              </span>
              <span className="font-semibold text-ink">1 Khách hàng</span>
            </div>
            <div className="h-px w-16 bg-line" />
            <div className="flex items-center gap-2">
              <span className="grid size-5 place-items-center rounded-full bg-brand-600 text-[11px] font-bold text-white">
                2
              </span>
              <span className="font-bold text-brand-700">Khung giờ</span>
            </div>
            <div className="h-px w-16 bg-line" />
            <div className="flex items-center gap-2">
              <span className="grid size-5 place-items-center rounded-full bg-surface-sunken text-[11px] font-bold text-ink-muted">
                3
              </span>
              <span>Xác nhận</span>
            </div>
          </div>

          {/* 3-Column Layout: Left (Patient Cards) + Middle (Grid) + Right (Panel) */}
          <div className="grid items-start gap-4 xl:grid-cols-[280px_1fr_320px]">
            {/* COLUMN 1 (LEFT - 280px): New Patient Button + Active Patient Card + Search List */}
            <aside className="space-y-3">
              {/* Nút đặt lịch cho khách hàng mới (Đặt lên trên cùng của Cột 1) */}
              <button
                type="button"
                onClick={() => setMode("new_patient")}
                className="w-full inline-flex items-center justify-center gap-2 rounded-2xl bg-brand-600 py-2.5 px-3.5 text-xs font-bold text-white shadow-xs hover:bg-brand-700 transition-all"
              >
                <UserPlus className="size-4" />
                + Đặt lịch hẹn cho khách mới
              </button>

              {/* 1. KHÁCH HÀNG ĐANG CHỌN */}
              {activePatient && (
                <div className="rounded-2xl border border-brand-300 bg-brand-50/50 p-3.5 shadow-card space-y-3">
                  <div className="flex items-start justify-between">
                    <span className="text-[11px] font-bold text-brand-700 uppercase tracking-wide">
                      Khách hàng đang chọn
                    </span>
                    <button
                      className="text-ink-muted hover:text-brand-600"
                      title="Chỉnh sửa"
                    >
                      <Pencil size={13} />
                    </button>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="grid size-11 place-items-center rounded-full bg-brand-600 text-sm font-bold text-white shadow-xs">
                      {activePatient.full_name
                        .split(" ")
                        .slice(-2)
                        .map((w) => w[0])
                        .join("")}
                    </div>
                    <div className="min-w-0">
                      <h3 className="text-sm font-bold text-ink truncate">
                        {activePatient.full_name}
                      </h3>
                      <p className="text-xs text-brand-700 font-mono font-semibold">
                        {activePatient.patient_code}
                      </p>
                    </div>
                  </div>
                  <div className="space-y-1.5 pt-2 text-xs text-ink-soft border-t border-brand-200/60">
                    <div className="flex items-center gap-2">
                      <Phone size={13} className="text-brand-600 shrink-0" />
                      <span>{activePatient.phone_primary ?? "Chưa có SĐT"}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <MapPin size={13} className="text-brand-600 shrink-0" />
                      <span className="truncate">
                        {activePatient.address ?? "Chưa có địa chỉ"}
                      </span>
                    </div>
                  </div>
                </div>
              )}

              {/* 2. TÌM KIẾM KHÁCH HÀNG CÓ SẴN (Kéo dài tối đa max-h-[380px]) */}
              <div className="rounded-2xl border border-line bg-surface p-3.5 shadow-card space-y-2.5">
                <span className="text-[11px] font-semibold uppercase tracking-wide text-ink-muted">
                  Tìm kiếm khách hàng có sẵn
                </span>
                <label className="flex items-center gap-2 rounded-xl border border-line bg-surface-muted px-3 py-2 text-xs text-ink focus-within:border-brand-500">
                  <Search className="size-4 text-ink-muted shrink-0" />
                  <input
                    type="search"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Tên, SĐT, mã bệnh nhân..."
                    className="w-full bg-transparent text-xs outline-none"
                  />
                </label>
                {/* Expanded scroll list */}
                <div className="max-h-[380px] overflow-y-auto divide-y divide-line text-xs pr-0.5">
                  {filteredPatients.map((p) => {
                    const selected = p.clinic_patient_id === selectedPatientId;
                    return (
                      <button
                        key={p.clinic_patient_id}
                        type="button"
                        onClick={() => setSelectedPatientId(p.clinic_patient_id)}
                        className={`w-full text-left p-2.5 rounded-xl transition-colors ${
                          selected
                            ? "bg-brand-100/80 font-bold text-brand-800"
                            : "hover:bg-surface-sunken"
                        }`}
                      >
                        <div className="truncate font-semibold text-ink">
                          {p.full_name}
                        </div>
                        <div className="text-[11px] text-ink-muted">
                          {p.patient_code} · {p.phone_primary ?? "Chưa có SĐT"}
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            </aside>

            {/* COLUMN 2 (MIDDLE - 1fr): Slot Table Grid */}
            <div className="space-y-3 min-w-0">
              {/* Filter controls row */}
              <div className="flex flex-wrap items-center gap-2.5 rounded-2xl border border-line bg-surface p-3 shadow-card">
                {/* Service dropdown */}
                <div className="flex items-center gap-1 rounded-xl border border-line bg-surface px-3 py-1.5 text-xs text-ink font-medium">
                  <span className="text-ink-muted">🩺</span>
                  <select
                    value={selectedServiceId}
                    onChange={(e) => setSelectedServiceId(e.target.value)}
                    className="bg-transparent text-xs font-semibold text-ink outline-none cursor-pointer"
                  >
                    {cleanServices.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.label}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Doctor dropdown */}
                <div className="flex items-center gap-1 rounded-xl border border-line bg-surface px-3 py-1.5 text-xs text-ink font-medium">
                  <User size={14} className="text-ink-muted" />
                  <select
                    value={selectedDoctorId}
                    onChange={(e) => handleDoctorFilterChange(e.target.value)}
                    className="bg-transparent text-xs font-semibold text-ink outline-none cursor-pointer"
                  >
                    <option value="all">Tất cả bác sĩ</option>
                    {doctors.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.label}
                      </option>
                    ))}
                  </select>
                </div>

                <Link
                  href="/schedule"
                  className="inline-flex items-center gap-1.5 rounded-xl border border-line bg-surface px-3 py-1.5 text-xs font-semibold text-brand-700 hover:bg-brand-50 ml-auto"
                  title="Xem lịch làm việc ca trực của bác sĩ & phòng khám"
                >
                  📅 Lịch làm việc
                </Link>
                <button
                  type="button"
                  className="inline-flex items-center gap-1.5 rounded-xl border border-line bg-surface px-3 py-1.5 text-xs font-medium text-ink-soft hover:bg-surface-muted"
                >
                  <Filter size={13} /> Bộ lọc
                </button>
              </div>

              {/* Date navigator & legend */}
              <div className="space-y-2.5 rounded-2xl border border-line bg-surface p-3.5 shadow-card">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <div className="flex items-center rounded-xl border border-line bg-surface px-2 py-1 text-xs">
                      <button className="p-1 hover:text-brand-600">
                        <ChevronLeft size={14} />
                      </button>
                      <span className="px-2 font-bold text-ink">
                        11–16/05/2026
                      </span>
                      <button className="p-1 hover:text-brand-600">
                        <ChevronRight size={14} />
                      </button>
                    </div>
                    <button className="rounded-xl border border-line bg-surface px-3 py-1.5 text-xs font-medium text-ink hover:bg-surface-muted">
                      Hôm nay
                    </button>
                  </div>

                  {/* Day Tabs */}
                  <div className="flex items-center gap-1 overflow-x-auto text-xs">
                    {WEEK_DAYS.map((d) => {
                      const isSelectedDay = d.isoDate === selectedDateIso;
                      return (
                        <button
                          key={d.dayName}
                          type="button"
                          onClick={() => setSelectedDateIso(d.isoDate)}
                          className={`rounded-xl border px-3 py-1 font-medium transition-all ${
                            isSelectedDay
                              ? "border-teal-600 bg-teal-50 text-teal-700 font-bold"
                              : "border-line bg-surface text-ink-muted hover:border-line"
                          }`}
                        >
                          {d.dayName} {d.dateStr}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Status Legend Pills (Exact colors from mockup) */}
                <div className="flex flex-wrap items-center gap-4 pt-1 text-xs">
                  <span className="flex items-center gap-1.5 text-teal-700 font-medium">
                    <span className="size-3.5 rounded-md border border-teal-300 bg-teal-50" />
                    Có thể đặt
                  </span>
                  <span className="flex items-center gap-1.5 text-amber-700 font-medium">
                    <span className="size-3.5 rounded-md border border-amber-300 bg-amber-50" />
                    Còn ít chỗ
                  </span>
                  <span className="flex items-center gap-1.5 text-sky-700 font-medium">
                    <span className="size-3.5 rounded-md border border-sky-300 bg-sky-50" />
                    Đang giữ
                  </span>
                  <span className="flex items-center gap-1.5 text-rose-700 font-medium">
                    <span className="size-3.5 rounded-md border border-rose-300 bg-rose-50" />
                    Đã đầy
                  </span>
                </div>
              </div>

              {/* Table Grid (FIRST COLUMN = TIME RANGE e.g. 18:00 - 18:15, NO INNER GRID LINES) */}
              <div className="overflow-hidden rounded-2xl border border-line bg-surface shadow-card p-2">
                {/* Doctor Header Row */}
                <div
                  className={`grid text-xs font-bold text-ink text-center pb-2 border-b border-line ${
                    activeDoctors.length === 1
                      ? "grid-cols-[110px_1fr]"
                      : activeDoctors.length === 2
                        ? "grid-cols-[110px_1fr_1fr]"
                        : "grid-cols-[110px_1fr_1fr_1fr]"
                  }`}
                >
                  <div className="p-2 text-ink-muted font-medium flex items-center justify-center">
                    Giờ
                  </div>
                  {activeDoctors.map((doc) => (
                    <div key={doc.id} className="p-2">
                      <div className="truncate font-bold text-ink">
                        {doc.label}
                      </div>
                      <div className="text-[11px] font-normal text-ink-muted truncate">
                        Phụ khoa
                      </div>
                    </div>
                  ))}
                </div>

                {/* Slot Rows */}
                <div className="max-h-[480px] overflow-y-auto space-y-1 pt-1.5">
                  {timeSlots.map((time) => {
                    const timeRangeStr = slotRange(time, 15);
                    return (
                      <div
                        key={time}
                        className={`grid text-xs items-center ${
                          activeDoctors.length === 1
                            ? "grid-cols-[110px_1fr]"
                            : activeDoctors.length === 2
                              ? "grid-cols-[110px_1fr_1fr]"
                              : "grid-cols-[110px_1fr_1fr_1fr]"
                        }`}
                      >
                        {/* FIRST COLUMN: TIME RANGE (e.g. 08:00 - 08:15) */}
                        <div className="p-2 text-center font-mono font-medium text-ink-muted text-[11px]">
                          {timeRangeStr}
                        </div>

                        {/* DOCTOR COLUMNS (CELLS - NO TIME TEXT INSIDE!) */}
                        {activeDoctors.map((doc) => {
                          const st = getCellStatus(doc.id, time);

                          if (st.tone === "selected") {
                            return (
                              <button
                                key={doc.id}
                                type="button"
                                className="m-1 flex items-center justify-between rounded-xl bg-teal-600 px-3 py-2 text-xs font-bold text-white shadow-xs transition-all border border-teal-700"
                              >
                                <span>
                                  {st.label} · {st.sub}
                                </span>
                                <span className="grid size-4 place-items-center rounded-full bg-white text-teal-700 text-[10px] font-extrabold">
                                  ✓
                                </span>
                              </button>
                            );
                          }

                          if (st.tone === "few") {
                            return (
                              <button
                                key={doc.id}
                                type="button"
                                onClick={() =>
                                  setSelectedSlot({
                                    doctorId: doc.id,
                                    doctorName: doc.label,
                                    time,
                                  })
                                }
                                className="m-1 flex items-center justify-center rounded-xl border border-amber-200 bg-amber-50/80 py-2 px-3 text-xs font-semibold text-amber-800 transition-all hover:bg-amber-100"
                              >
                                {st.label} · {st.sub}
                              </button>
                            );
                          }

                          if (st.tone === "holding") {
                            return (
                              <button
                                key={doc.id}
                                type="button"
                                onClick={() =>
                                  setSelectedSlot({
                                    doctorId: doc.id,
                                    doctorName: doc.label,
                                    time,
                                  })
                                }
                                className="m-1 flex items-center justify-center rounded-xl border border-sky-200 bg-sky-50/80 py-2 px-3 text-xs font-semibold text-sky-800 transition-all hover:bg-sky-100"
                              >
                                {st.label} · {st.sub}
                              </button>
                            );
                          }

                          if (st.tone === "full") {
                            return (
                              <button
                                key={doc.id}
                                disabled
                                type="button"
                                className="m-1 flex items-center justify-center rounded-xl border border-rose-200 bg-rose-50/70 py-2 px-3 text-xs font-semibold text-rose-700 cursor-not-allowed opacity-75"
                              >
                                {st.label} · {st.sub}
                              </button>
                            );
                          }

                          return (
                            <button
                              key={doc.id}
                              type="button"
                              onClick={() =>
                                setSelectedSlot({
                                  doctorId: doc.id,
                                  doctorName: doc.label,
                                  time,
                                })
                              }
                              className="m-1 flex items-center justify-center rounded-xl border border-teal-200 bg-teal-50/60 py-2 px-3 text-xs font-semibold text-teal-800 transition-all hover:bg-teal-100/80"
                            >
                              {st.label} · {st.sub}
                            </button>
                          );
                        })}
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* COLUMN 3 (RIGHT - 320px): Thông tin đặt lịch (Matching Image 3 Mockup) */}
            <aside className="space-y-3.5 rounded-2xl border border-line bg-surface p-4 shadow-card">
              <div className="flex items-center justify-between border-b border-line pb-2.5">
                <h3 className="text-sm font-bold text-ink">Thông tin đặt lịch</h3>
                <span className="rounded-full bg-teal-50 px-2.5 py-0.5 text-[11px] font-bold text-teal-700 border border-teal-200">
                  Đang chọn
                </span>
              </div>

              {/* Patient info box */}
              {activePatient && (
                <div className="rounded-xl border border-line bg-surface-muted/60 p-3 space-y-2 text-xs">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-2">
                      <User size={15} className="text-ink-muted shrink-0" />
                      <div>
                        <div className="font-bold text-ink">
                          {activePatient.full_name}
                        </div>
                        <div className="text-[11px] text-ink-muted font-mono">
                          {activePatient.patient_code}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-1 text-ink-muted font-mono">
                      <Phone size={12} />
                      <span>{activePatient.phone_primary ?? "—"}</span>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setMode("grid")}
                    className="text-[11px] font-semibold text-brand-700 hover:underline pt-0.5 block"
                  >
                    Đổi khách hàng
                  </button>
                </div>
              )}

              <div className="space-y-2 text-xs">
                <div className="flex justify-between border-b border-line/60 pb-1.5">
                  <span className="text-ink-muted">Dịch vụ:</span>
                  <span className="font-bold text-ink">{selectedServiceName}</span>
                </div>
                <div className="flex justify-between border-b border-line/60 pb-1.5">
                  <span className="text-ink-muted">Bác sĩ:</span>
                  <span className="font-bold text-ink">
                    {selectedSlot.doctorName}
                  </span>
                </div>
              </div>

              {/* Selected Slot Time Box */}
              <div className="rounded-xl border border-teal-200 bg-teal-50/60 p-3 flex items-center gap-3">
                <div className="grid size-9 shrink-0 place-items-center rounded-lg bg-teal-600 text-white shadow-xs">
                  <CalendarIcon size={18} />
                </div>
                <div>
                  <div className="text-xs font-bold text-teal-800">
                    {slotRange(selectedSlot.time, 15)}
                  </div>
                  <div className="text-[11px] text-teal-700 font-medium">
                    Thứ Sáu, 15/05/2026
                  </div>
                </div>
              </div>

              {/* Capacity Status */}
              <div className="flex items-center justify-between text-xs rounded-xl bg-surface-muted p-2.5 border border-line">
                <span className="text-ink-muted font-medium flex items-center gap-1.5">
                  <Users size={13} className="text-brand-600" />
                  Sức chứa:
                </span>
                <span className="font-bold text-ink">
                  {selectedCellStatus.bookedCount}/{selectedCellStatus.maxCap} đã đặt
                  ·{" "}
                  <span className="text-teal-700 font-bold">
                    còn {selectedCellStatus.maxCap - selectedCellStatus.bookedCount} chỗ
                  </span>
                </span>
              </div>

              {/* Note */}
              <div className="space-y-1">
                <label className="text-xs font-semibold text-ink">Ghi chú</label>
                <textarea
                  rows={2}
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder="Thêm ghi chú cho phòng khám..."
                  className="w-full rounded-xl border border-line p-2.5 text-xs text-ink outline-none focus:border-brand-500"
                />
              </div>

              {/* Confirmation Checklist */}
              <div className="space-y-1.5 border-t border-line pt-2 text-xs">
                <span className="font-semibold text-ink block">
                  Thông tin xác nhận
                </span>
                <label className="flex items-center gap-2 cursor-pointer text-ink-soft">
                  <input
                    type="checkbox"
                    checked={chkCustomer}
                    onChange={(e) => setChkCustomer(e.target.checked)}
                    className="rounded border-line text-brand-600 focus:ring-brand-500"
                  />
                  Đúng khách hàng
                </label>
                <label className="flex items-center gap-2 cursor-pointer text-ink-soft">
                  <input
                    type="checkbox"
                    checked={chkService}
                    onChange={(e) => setChkService(e.target.checked)}
                    className="rounded border-line text-brand-600 focus:ring-brand-500"
                  />
                  Đúng dịch vụ
                </label>
                <label className="flex items-center gap-2 cursor-pointer text-ink-soft">
                  <input
                    type="checkbox"
                    checked={chkDocSlot}
                    onChange={(e) => setChkDocSlot(e.target.checked)}
                    className="rounded border-line text-brand-600 focus:ring-brand-500"
                  />
                  Đúng bác sĩ và khung giờ
                </label>
              </div>

              {/* Notice */}
              <div className="rounded-xl bg-sky-50 p-2.5 text-[11px] text-sky-800 flex items-start gap-2 border border-sky-200/60">
                <Info size={14} className="shrink-0 mt-0.5 text-sky-600" />
                <span>Lịch hẹn sẽ được tạo ngay khi bạn đặt. 10 phút ưu tiên chỉ áp dụng lúc bệnh nhân check-in (theo giờ hẹn).</span>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => setSelectedPatientId(null)}
                  className="flex-1 rounded-xl border border-line bg-surface py-2.5 text-xs font-semibold text-ink hover:bg-surface-sunken"
                >
                  Hủy chọn
                </button>
                <button
                  type="button"
                  onClick={handleConfirmBooking}
                  disabled={bookingLoading || !activePatient}
                  className="flex-[1.5] rounded-xl bg-brand-600 py-2.5 text-xs font-bold text-white shadow-xs hover:bg-brand-700 disabled:opacity-50"
                >
                  {bookingLoading ? "Đang xử lý..." : "Đặt lịch hẹn"}
                </button>
              </div>
            </aside>
          </div>
        </div>
      )}
    </div>
  );
}
