"use client";

// Reusable appointment-booking form for ONE patient. Used both in the
// new-patient intake flow (step 2 of NewPatientForm) and standalone on a
// patient's profile (PatientBooking). It renders ONLY the form; the parent
// owns the success UI and decides what happens after a booking via onBooked.
// Write path = POST /api/appointments (service-role + intake-role guard).

import { useState, useMemo, useEffect, type ReactNode } from "react";
import { vnLocalToUtcISO, nowMs } from "../../../lib/datetime";
import { todayVn, clinicHoursForDate, clinicHoursError } from "../../../lib/roster";
import { INPUT, LABEL, BTN, CHANNELS } from "../form-ui";
import { unaccentVi } from "../../../lib/validation";
import Time24Input from "../Time24Input";
import DateField from "../DateField";
import { LINH_VUC_OPTIONS } from "../../../lib/linh-vuc";
import CinemaSlotPicker from "./CinemaSlotPicker";
import {
  buildSlotUsage,
  usageAt,
  slotBucketMs,
  slotMinuteOptions,
  type SlotApptLite,
} from "../../../lib/slot-capacity";
import { useBookingPolicy } from "../BookingPolicyContext";

// Capacity Phase 1 — nhãn/lớp token của 6 trạng thái ô khung-giờ
// (khớp CellState ở lib/capacity.ts).
// BA TRẠNG THÁI, KHÔNG PHẢI SÁU.
//
// Bảng cũ có return_only / full_thanh / walkin_hold / locked — nhãn của mô hình
// "ngân sách phút của bác sĩ Thành" (block_budget), đã bị bỏ khi thời lượng
// khám chuyển thành số liệu ĐO ĐƯỢC và giới hạn đặt lịch chuyển thành SỐ CHỖ do
// Trưởng ca cấu hình. Giữ lại chúng nghĩa là màn hình còn nói bằng ngôn ngữ của
// một luật không còn tồn tại — và "Đầy-Thành" thì vô nghĩa với mọi phòng khám
// không có bác sĩ tên Thành.
//
// Backend giờ trả đúng ba trạng thái, tính từ cùng con số mà trigger chặn.
const CELL_UI: Record<string, { label: string; className: string }> = {
  free: { label: "Trống", className: "bg-success-bg text-success" },
  few: { label: "Còn ít", className: "bg-warning-bg text-warning" },
  full: { label: "Đã đầy", className: "bg-danger-bg text-danger" },
};

function findServiceIdByLinhVuc(code: string, services: Option[]): string {
  if (!code) return "";
  const nameMap: Record<string, string[]> = {
    PK: ["Phụ khoa", "PHU_KHOA"],
    SK: ["Sản 1", "Sản khoa", "Sản", "SAN_1"],
    NT: ["Nội tiết - Tình dục", "Nội tiết", "NOI_TIET_TINH_DUC"],
    HMVS: ["Hiếm muộn", "Hiếm muộn - Vô sinh", "HIEM_MUON"],
    NK: ["Nam khoa", "NAM_KHOA"],
  };
  const targets = nameMap[code] ?? [];
  for (const t of targets) {
    const found = services.find((s) => s.label.toLowerCase() === t.toLowerCase());
    if (found) return found.id;
  }
  for (const t of targets) {
    const found = services.find((s) => s.label.toLowerCase().includes(t.toLowerCase()));
    if (found) return found.id;
  }
  return services[0]?.id ?? "";
}

export interface Option {
  id: string;
  label: string;
}

/** Giá trị điền sẵn khi mở form ở chế độ SỬA lịch đã có. */
export interface BookingInitial {
  serviceId?: string;
  doctorId?: string;
  doctorLabel?: string;
  locationId?: string;
  apptDate?: string; // VN "YYYY-MM-DD"
  apptTime?: string; // "HH:mm"
  patientKind?: string;
  needSono?: boolean;
  channel?: string;
}

/** Chế độ SỬA lịch đã có (Thông tin khách hàng → bấm ô "Lịch hẹn sắp tới").
 *  Khi set: form ĐIỀN SẴN lịch cũ; nút → PATCH reschedule (đổi giờ + bác sĩ),
 *  CHỈ bật khi đã đổi ngày/giờ; Dịch vụ hiển thị read-only (reschedule không
 *  đổi dịch vụ). */
export interface BookingEdit {
  appointmentId: string;
  origDate: string; // VN "YYYY-MM-DD"
  origTime: string; // "HH:mm"
  serviceLabel: string; // tên dịch vụ hiện tại (chỉ hiển thị)
  /** Gọi sau khi đổi lịch thành công (parent đóng modal + refresh). */
  onDone: () => void;
}

export default function AppointmentBooking({
  clinicPatientId,
  services,
  doctors,
  locations,
  defaultLocationId,
  onBooked,
  secondary,
  walkin = false,
  edit,
  initial,
  khoaDichVu,
  lichTruocId,
}: {
  clinicPatientId: string;
  services: Option[];
  doctors: Option[];
  locations: Option[];
  /** Pre-select a location (e.g. the one chosen at intake). */
  defaultLocationId?: string;
  /** Called with the new appointment id once the booking succeeds. */
  onBooked: (appointmentId: string) => void;
  /** Optional extra control rendered next to the submit button (e.g. "skip"). */
  secondary?: ReactNode;
  /** Lễ tân xếp BN tái khám VÃNG LAI: chỉ bấm ô xanh (chỗ đến trực tiếp),
   *  đặt như WALK_IN, không cần Kênh đặt. Mặc định false = đặt hẹn thường (ô hồng). */
  walkin?: boolean;
  /** Set để chuyển form sang chế độ SỬA (đổi lịch) thay vì tạo mới. */
  edit?: BookingEdit;
  /** Giá trị điền sẵn (dùng chung với edit; cũng dùng được khi tạo mới). */
  initial?: BookingInitial;
  /** TÁI KHÁM: khoá cứng dịch vụ theo lượt khám trước, hiện read-only.
   *
   *  KHÔNG dùng `initial.serviceId` cho việc này. Ô "Dịch vụ" là dropdown LĨNH
   *  VỰC, và `linhVuc` không đọc `initial` — nên `initial.serviceId` đặt được
   *  giá trị ngầm nhưng ô vẫn hiện "— Chọn dịch vụ —". Người dùng thấy chưa
   *  chọn gì mà nút Đặt lịch lại sáng; chọn lại thì `findServiceIdByLinhVuc`
   *  chạy, và hàm ấy kết thúc bằng `services[0]?.id` — IM LẶNG chọn dịch vụ
   *  đầu danh sách nếu không khớp tên. Tái khám mà lặng lẽ đổi sang dịch vụ
   *  khác là hỏng đúng thứ nút Tái khám sinh ra để bảo toàn. */
  khoaDichVu?: { serviceId: string; label: string };
  /** Lịch hẹn mà lịch sắp đặt là TÁI KHÁM của nó. Xem 20260810000007. */
  lichTruocId?: string;
}) {
  const [serviceId, setServiceId] = useState(
    khoaDichVu?.serviceId ?? initial?.serviceId ?? "",
  );
  // Bác sĩ: combobox tìm kiếm bỏ dấu thay native <select>
  const [doctorId, setDoctorId] = useState(initial?.doctorId ?? "");
  const [doctorQ, setDoctorQ] = useState(initial?.doctorLabel ?? ""); // text hiện trong ô
  const [doctorOpen, setDoctorOpen] = useState(false);
  const filteredDoctors = useMemo(() => {
    const t = unaccentVi(doctorQ.trim());
    if (!t) return doctors;
    return doctors.filter((d) => unaccentVi(d.label).includes(t));
  }, [doctorQ, doctors]);
  const [locationId, setLocationId] = useState(
    initial?.locationId ?? defaultLocationId ?? locations[0]?.id ?? "",
  );
  const [linhVuc, setLinhVuc] = useState("");
  const [apptDate, setApptDate] = useState(initial?.apptDate ?? "");
  const [apptTime, setApptTime] = useState(initial?.apptTime ?? "");
  // Luật đặt lịch của phòng khám (độ dài khung + số chỗ). `null` = chưa đọc
  // được; form vẫn hiện nhưng nút Đặt lịch khoá — xem chỗ dùng bên dưới.
  const policy = useBookingPolicy();
  // slot_end = đầu khung + đúng độ dài khung của phòng khám này. Trước đây là
  // useState(15) — một lịch dài 15' trong phòng khám chạy khung 30' để lại nửa
  // khung "trống" mà không ai đặt được vào.
  const duration = policy?.slotMinutes ?? 0;
  // Capacity Phase 1 (T-20260629-CAP-01) — CSKH chọn tay (DEC-3); backend gợi ý tải.
  const [patientKind, setPatientKind] = useState(initial?.patientKind ?? ""); // "" | "RETURN" | "NEW"
  const [needSono, setNeedSono] = useState(initial?.needSono ?? false);
  // Lịch sử dịch vụ của BN này (T-20260629-EPI-01) giờ CHỈ dùng để đặt mặc định
  // NEW/RETURN — xem effect gọi /api/appointments/service-history bên dưới.
  //
  // State `svcHistory` đã bỏ: phần giao diện hiện chú thích "đã khám N lần" bị
  // gỡ cùng đợt xoá ô "Số khám"/"Loại khám", nên state chỉ còn được ghi mà
  // không ai đọc. Bản thân lời gọi fetch thì GIỮ NGUYÊN, vì nó vẫn quyết định
  // patientKind mặc định.
  const [existingAppts, setExistingAppts] = useState<SlotApptLite[]>([]);
  // Bác sĩ TRỰC CA của ngày đã chọn (work_roster LICH_KHAM) — sơ đồ chỉ hiện
  // các bác sĩ này. null = chưa nạp; [] = ngày chưa phân trực (fallback tất cả).
  const [dutyDoctorIds, setDutyDoctorIds] = useState<string[] | null>(null);
  // Capacity Phase 1 — tải/khung-giờ để hiển thị (quote, read-only).
  // Sức chứa từng KHUNG (không phải từng giờ), đọc từ cùng resolver mà trigger
  // dùng để chặn. Trước đây nó đọc block_budget — một bảng thứ hai, mịn theo
  // giờ, không ai đối chiếu với thứ thật sự thi hành: lưới vẽ "còn chỗ" trong
  // khi trigger từ chối là chuyện có thể xảy ra và không ai phát hiện được.
  const [budgetBlocks, setBudgetBlocks] = useState<
    {
      time: string;
      state: string;
      regular_cap: number;
      regular_used: number;
    }[]
  >([]);
  const [channel, setChannel] = useState(initial?.channel ?? "");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // State from the previous selection may remain until the next async response.
  // Hide it immediately when the controlling input is empty so stale capacity or
  // service history is never rendered for a different selection.
  const visibleExistingAppts = useMemo(
    () => (apptDate ? existingAppts : []),
    [apptDate, existingAppts],
  );

  // Fetch appointments for selected date to check availability
  useEffect(() => {
    if (!apptDate) return;
    let active = true;
    // Lấy lịch của MỌI bác sĩ trong ngày (KHÔNG lọc doctor_id) để sơ đồ "rạp
    // chiếu phim" vẽ được từng hàng bác sĩ. isSlotBooked vẫn lọc theo doctorId
    // ở phía client nhờ field appt.doctor_id còn nguyên trong kết quả.
    fetch(`/api/appointments?date=${encodeURIComponent(apptDate)}`)
      .then((r) => (r.ok ? r.json() : { appointments: [] }))
      .then((data) => {
        if (active) {
          // Sửa lịch: bỏ CHÍNH lịch đang sửa khỏi sơ đồ để ô của nó không bị
          // tính là "đã kín" (server cũng loại trừ self khi reschedule).
          const list = (data.appointments ?? []) as (SlotApptLite & {
            id?: string;
          })[];
          setExistingAppts(
            edit ? list.filter((a) => a.id !== edit.appointmentId) : list,
          );
        }
      })
      .catch(() => {
        if (active) setExistingAppts([]);
      });
    return () => {
      active = false;
    };
    // edit ổn định (parent remount theo từng lịch) → không gây fetch lặp.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apptDate]);

  // Bác sĩ trực ca của ngày đã chọn — sơ đồ chỉ vẽ hàng các bác sĩ này.
  useEffect(() => {
    if (!apptDate) return;
    const ctrl = new AbortController();
    fetch(`/api/roster?date=${encodeURIComponent(apptDate)}`, { signal: ctrl.signal })
      .then((r) => (r.ok ? r.json() : null))
      .then((j) =>
        setDutyDoctorIds(
          j ? (j.doctors as { id: string }[]).map((d) => d.id) : null,
        ),
      )
      .catch(() => {});
    return () => ctrl.abort();
  }, [apptDate]);

  // Capacity Phase 1 — nạp tải/khung-giờ cho cơ sở+ngày+BS đã chọn (chỉ để hiển thị).
  useEffect(() => {
    // Không setState đồng bộ trong effect (tránh react-hooks/set-state-in-effect).
    // Khi thiếu ngày/cơ sở thì bỏ qua; render đã guard theo apptDate+locationId nên
    // dữ liệu cũ không hiện nhầm. setBudgetBlocks chỉ chạy trong .then (bất đồng bộ).
    if (!apptDate || !locationId) return;
    const ctrl = new AbortController();
    const params = new URLSearchParams({ date: apptDate, location_id: locationId });
    if (doctorId) params.set("doctor_id", doctorId);
    fetch(`/api/appointments/quote?${params.toString()}`, { signal: ctrl.signal })
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => setBudgetBlocks(j?.slots ?? []))
      .catch(() => {});
    return () => ctrl.abort();
  }, [apptDate, locationId, doctorId]);

  // Khi đổi DỊCH VỤ (hoặc BN) → tra lịch sử để hiện hint + đặt MẶC ĐỊNH NEW/RETURN.
  // Đợt còn sống ⇒ mặc định Tái khám; không có đợt sống ⇒ mặc định Khám mới (hướng sai
  // an toàn = đếm thừa tải, không overbook). CSKH vẫn sửa được sau đó.
  useEffect(() => {
    if (!serviceId || !clinicPatientId) return;
    const ctrl = new AbortController();
    const params = new URLSearchParams({
      clinic_patient_id: clinicPatientId,
      service_type_id: serviceId,
    });
    fetch(`/api/appointments/service-history?${params.toString()}`, { signal: ctrl.signal })
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => {
        if (!j) return;
        // Sửa lịch: GIỮ loại khám đã điền sẵn, không tự ghi đè theo lịch sử.
        if (!edit) setPatientKind(j.liveEpisode ? "RETURN" : "NEW");
      })
      .catch(() => {});
    return () => ctrl.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [serviceId, clinicPatientId]);

  // CSKH: khung đang chọn còn chỗ đặt hẹn không? Số chỗ kênh thường và số chỗ
  // vãng lai là cấu hình của phòng khám (clinic.settings.booking) — chỗ vãng
  // lai để dành nên KHÔNG tính vào chỗ đặt hẹn.
  const isSlotBooked = useMemo(() => {
    if (!apptDate || !apptTime || !policy) return false;
    try {
      // Giờ gõ tay có thể rơi giữa khung → phải quy về đầu khung, đúng như
      // trigger enforce_slot_capacity làm khi đếm.
      const bucketMs = slotBucketMs(vnLocalToUtcISO(apptDate, apptTime), policy);
      const u = usageAt(
        buildSlotUsage(visibleExistingAppts, policy),
        doctorId || null,
        bucketMs,
      );
      return walkin ? u.walkin >= policy.walkinCap : u.regular >= policy.regularCap;
    } catch {
      return false;
    }
  }, [walkin, apptDate, apptTime, doctorId, visibleExistingAppts, policy]);

  // Kênh đặt BẮT BUỘC cho đặt hẹn thường: kênh rỗng bị server mặc định WALK_IN →
  // chiếm nhầm chỗ vãng lai (chỗ 3). Vãng lai (Lễ tân) thì cố định WALK_IN nên
  // KHÔNG cần chọn kênh.
  // Chế độ SỬA: chỉ cho lưu khi ĐÃ đổi ngày/giờ (không đổi thì lưu vô nghĩa).
  const changed =
    !edit || apptDate !== edit.origDate || apptTime !== edit.origTime;
  const canBook =
    serviceId &&
    locationId &&
    apptDate &&
    apptTime &&
    (walkin || channel) &&
    changed &&
    // Không đọc được luật thì không biết lịch dài bao nhiêu phút → không gửi.
    !!policy;
  // Giới hạn giờ theo ngày đã chọn (giờ mở cửa PK).
  const ch =
    apptDate && policy ? clinicHoursForDate(apptDate, policy.hours) : null;
  const minHour = ch ? Number(ch.open.slice(0, 2)) : 0;
  const maxHour = ch ? Number(ch.close.slice(0, 2)) - 1 : 23;

  async function book() {
    setError(null);
    if (!policy) {
      setError(
        "Chưa đọc được luật đặt lịch của phòng khám — tải lại trang rồi thử lại.",
      );
      return;
    }
    // Interpret the picked date+time as Vietnam time (GMT+7), not the browser's.
    const start = new Date(vnLocalToUtcISO(apptDate, apptTime));
    // Logic thời gian thực: KHÔNG cho đặt lịch vào quá khứ.
    if (start.getTime() < nowMs()) {
      setError("Không thể đặt lịch trong quá khứ. Chọn ngày/giờ từ hiện tại trở đi.");
      return;
    }
    // Trong giờ mở cửa PK (T2–T6 17–23h; T7+CN cả ngày).
    const chErr = clinicHoursError(apptDate, apptTime, policy.hours);
    if (chErr) {
      setError(chErr);
      return;
    }
    setSubmitting(true);
    const end = new Date(start.getTime() + duration * 60_000);

    // Chế độ SỬA: PATCH reschedule (đổi giờ + tuỳ chọn bác sĩ). KHÔNG tạo lịch
    // mới. Backend giữ trạng thái, chặn trùng giờ + luật 2+1 (loại trừ chính lịch).
    if (edit) {
      const res = await fetch("/api/appointments", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          id: edit.appointmentId,
          action: "reschedule",
          slot_start: start.toISOString(),
          slot_end: end.toISOString(),
          doctor_id: doctorId, // "" = bỏ phân bác sĩ
        }),
      });
      const json = await res.json();
      setSubmitting(false);
      if (!res.ok) {
        setError(json.error ?? "Lỗi đổi lịch.");
        return;
      }
      edit.onDone();
      return;
    }

    const res = await fetch("/api/appointments", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        clinic_patient_id: clinicPatientId,
        doctor_id: doctorId,
        service_type_id: serviceId,
        location_id: locationId,
        slot_start: start.toISOString(),
        slot_end: end.toISOString(),
        // Vãng lai (Lễ tân) → WALK_IN để vào đúng ghế đến trực tiếp.
        booking_channel: walkin ? "WALK_IN" : channel,
        // Tải/ca — backend tự gợi ý thanh_min/sono_min từ 2 field này (DEC-3).
        patient_kind: patientKind || undefined,
        need_sono: needSono,
        // Chuỗi tái khám. Chỉ có giá trị khi form được mở từ nút "Tái khám";
        // backend còn kiểm lại lịch ấy đúng của khách này không.
        lich_truoc_id: lichTruocId ?? undefined,
      }),
    });
    const json = await res.json();
    setSubmitting(false);
    if (!res.ok) {
      setError(json.error ?? "Có lỗi xảy ra.");
      return;
    }
    // Nạp lại sơ đồ chỗ để lịch VỪA đặt hiện "đã kín" ngay, không phải đổi ngày
    // mới thấy — quan trọng khi đặt liên tiếp nhiều lịch trong cùng form.
    try {
      const r = await fetch(
        `/api/appointments?date=${encodeURIComponent(apptDate)}`,
      );
      if (r.ok) {
        const data = await r.json();
        setExistingAppts(data.appointments ?? []);
      }
    } catch {
      // im lặng: lỗi nạp lại không được chặn xác nhận đặt lịch đã thành công
    }
    onBooked(json.appointment_id as string);
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="space-y-1">
          <label className={LABEL}>Dịch vụ *</label>
          {edit ? (
            // Sửa lịch: dịch vụ giữ nguyên (reschedule không đổi dịch vụ) → chỉ hiển thị.
            <div
              className={INPUT + " flex items-center bg-surface-muted text-ink-soft"}
            >
              {edit.serviceLabel || "—"}
            </div>
          ) : khoaDichVu ? (
            // TÁI KHÁM: dịch vụ lấy theo lượt khám trước, không đổi được ở đây.
            // Đổi dịch vụ thì nó không còn là tái khám nữa — đó là "Đặt lịch
            // khám mới", và có nút riêng cho việc ấy.
            <div
              className={INPUT + " flex items-center bg-surface-muted text-ink-soft"}
              title="Tái khám giữ nguyên dịch vụ của lượt trước. Muốn đổi dịch vụ thì dùng “Đặt lịch khám mới”."
            >
              {khoaDichVu.label || "—"}
            </div>
          ) : (
            <select
              value={linhVuc}
              onChange={(e) => {
                const code = e.target.value;
                setLinhVuc(code);
                const svcId = findServiceIdByLinhVuc(code, services);
                setServiceId(svcId);
              }}
              className={INPUT}
            >
              <option value="">— Chọn dịch vụ —</option>
              {LINH_VUC_OPTIONS.map((o) => (
                <option key={o.code} value={o.code}>
                  {o.label}
                </option>
              ))}
            </select>
          )}
        </div>
        <div className="space-y-1">
          <label className={LABEL}>Bác sĩ</label>
          {/* Combobox: gõ tìm — không phân biệt dấu / hoa-thường */}
          <div className="relative">
            <input
              value={doctorQ}
              onChange={(e) => {
                setDoctorQ(e.target.value);
                setDoctorId(""); // xóa chọn cũ khi gõ đè
                setDoctorOpen(true);
              }}
              onFocus={() => setDoctorOpen(true)}
              onBlur={() => setTimeout(() => setDoctorOpen(false), 150)}
              placeholder="Tìm bác sĩ… (bỏ trống nếu chưa phân)"
              className={INPUT}
              autoComplete="off"
            />
            {doctorOpen && (
              <ul className="absolute z-30 mt-1 max-h-52 w-full overflow-auto rounded-lg border border-line bg-white shadow-lg">
                <li
                  onMouseDown={() => {
                    setDoctorId("");
                    setDoctorQ("");
                    setDoctorOpen(false);
                  }}
                  className="cursor-pointer px-3 py-2 text-sm text-ink-muted hover:bg-brand-50"
                >
                  — Chưa phân bác sĩ —
                </li>
                {filteredDoctors.length === 0 ? (
                  <li className="px-3 py-2 text-sm text-ink-faint">
                    Không tìm thấy bác sĩ
                  </li>
                ) : (
                  filteredDoctors.map((d) => (
                    <li
                      key={d.id}
                      onMouseDown={() => {
                        setDoctorId(d.id);
                        setDoctorQ(d.label);
                        setDoctorOpen(false);
                      }}
                      className={
                        "cursor-pointer px-3 py-2 text-sm hover:bg-brand-50 " +
                        (d.id === doctorId
                          ? "bg-brand-100 font-medium text-brand-800"
                          : "text-ink")
                      }
                    >
                      {d.label}
                    </li>
                  ))
                )}
              </ul>
            )}
          </div>
        </div>
        <div className="space-y-1">
          <label className={LABEL}>Ngày *</label>
          <DateField
            value={apptDate}
            onChange={setApptDate}
            min={todayVn()}
            ariaLabel="Ngày khám"
          />
        </div>
        <div className="space-y-1">
          <label className={LABEL}>Giờ *</label>
          <Time24Input
            value={apptTime}
            onChange={setApptTime}
            minHour={minHour}
            maxHour={maxHour}
            minutesOptions={policy ? slotMinuteOptions(policy) : []}
          />
          {/* Bỏ dòng "đến muộn 15 phút mất chỗ" — xem ghi chú cùng chỗ trong
              NewPatientForm.tsx. */}
          {ch && (
            <p className="mt-1 text-[11px] text-ink-faint">
              Giờ mở cửa: {ch.open}–{ch.close}
            </p>
          )}
        </div>
        <div className="space-y-1 sm:col-span-2">
          <label className={LABEL}>Chọn chỗ (sơ đồ trống)</label>
          <CinemaSlotPicker
            date={apptDate}
            doctors={doctors}
            dutyDoctorIds={dutyDoctorIds}
            existingAppts={visibleExistingAppts}
            selectedDoctorId={doctorId}
            selectedTime={apptTime}
            mode={walkin ? "walkin" : "regular"}
            onPick={(docId, t) => {
              setApptTime(t);
              setDoctorId(docId);
              setDoctorQ(docId ? (doctors.find((d) => d.id === docId)?.label ?? "") : "");
            }}
          />
          {apptDate && apptTime && (
            <p
              className={`text-[11px] font-medium ${
                isSlotBooked ? "text-danger" : "text-success"
              }`}
            >
              {isSlotBooked
                ? "Khung đang chọn đã kín — chọn ô khác."
                : "Khung đang chọn còn trống."}
            </p>
          )}
          {apptDate && locationId && budgetBlocks.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {budgetBlocks.map((b) => {
                const ui = CELL_UI[b.state] ?? CELL_UI.free;
                return (
                  <span
                    key={b.time}
                    title={`${ui.label} — ${b.regular_used}/${b.regular_cap} chỗ đặt hẹn`}
                    className={`rounded-chip px-1.5 py-0.5 text-[11px] ${ui.className}`}
                  >
                    {b.time} · {b.regular_used}/{b.regular_cap}
                  </span>
                );
              })}
            </div>
          )}
        </div>
        <div className="space-y-1">
          <label className={LABEL}>Cơ sở *</label>
          <select
            value={locationId}
            onChange={(e) => setLocationId(e.target.value)}
            className={INPUT}
          >
            {locations.map((l) => (
              <option key={l.id} value={l.id}>
                {l.label}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1">
          <label className={LABEL}>{walkin ? "Kênh đặt" : "Kênh đặt *"}</label>
          {walkin ? (
            <div className={INPUT + " flex items-center bg-success-bg text-success"}>
              Khách đến trực tiếp (không đặt trước)
            </div>
          ) : (
            <select
              value={channel}
              onChange={(e) => setChannel(e.target.value)}
              className={INPUT}
            >
              <option value="">— Chọn kênh —</option>
              {CHANNELS.filter((c) => c.id !== "WALK_IN").map((c) => (
                <option key={c.id} value={c.id}>
                  {c.label}
                </option>
              ))}
            </select>
          )}
        </div>
        <div className="space-y-1">
          <label className={LABEL}>Siêu âm</label>
          <label className="flex h-[38px] items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={needSono}
              onChange={(e) => setNeedSono(e.target.checked)}
            />
            Có đi siêu âm
          </label>
        </div>
      </div>

      {error && (
        <p className="rounded bg-danger-bg px-3 py-2 text-sm text-danger">
          {error}
        </p>
      )}

      <div className="flex flex-col gap-2 sm:flex-row">
        <button onClick={book} disabled={!canBook || submitting} className={BTN}>
          {submitting
            ? edit
              ? "Đang đổi..."
              : "Đang đặt..."
            : edit
              ? "Đổi lịch hẹn"
              : "Đặt lịch hẹn"}
        </button>
        {secondary}
      </div>
    </div>
  );
}
