"use client";

// Modal ĐỔI / HỦY lịch hẹn của khách — mở từ "Thông tin khách hàng" khi bấm ô
// "Lịch hẹn sắp tới". Tái dùng form đặt lịch (AppointmentBooking) ở chế độ SỬA:
// điền sẵn lịch cũ, chỉ cho "Đổi lịch hẹn" khi đã chọn ngày/giờ mới (reschedule).
// Kèm nút "Hủy lịch hẹn" (cancel). Chỉ CSKH/QL/Trưởng ca thấy (gate ở parent + API).

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { X } from "lucide-react";
import AppointmentBooking, {
  type Option,
  type BookingEdit,
  type BookingInitial,
} from "../patients/AppointmentBooking";
import { fmtDateTimeOrDate } from "../../../lib/datetime";
import { LY_DO_HUY, LY_DO_HUY_THU_TU } from "../../../lib/ly-do-huy";
import { INPUT, LABEL } from "../form-ui";

export interface EditableAppt {
  id: string;
  slot_start: string;
  service_type_id: string | null;
  service_name: string | null;
  doctor_id: string | null;
  doctor_name: string | null;
  location_id: string | null;
  booking_channel: string | null;
}

export default function AppointmentEditModal({
  appt,
  patientName,
  clinicPatientId,
  services,
  doctors,
  locations,
  onClose,
}: {
  appt: EditableAppt;
  patientName: string;
  clinicPatientId: string;
  services: Option[];
  doctors: Option[];
  locations: Option[];
  onClose: () => void;
}) {
  const router = useRouter();
  const [showCancel, setShowCancel] = useState(false);
  const [reason, setReason] = useState("");
  const [maLyDo, setMaLyDo] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const previousFocus = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeButtonRef.current?.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
      previousFocus?.focus();
    };
  }, [onClose]);

  function keepFocusInside(event: React.KeyboardEvent<HTMLDivElement>) {
    if (event.key !== "Tab") return;
    const focusable = dialogRef.current?.querySelectorAll<HTMLElement>(
      'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    );
    if (!focusable?.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  // UTC ISO → giờ VN (GMT+7) dạng "YYYY-MM-DD" + "HH:mm" để điền sẵn form.
  const vn = new Date(new Date(appt.slot_start).getTime() + 7 * 3_600_000);
  const origDate = vn.toISOString().slice(0, 10);
  const origTime = vn.toISOString().slice(11, 16);

  function finish() {
    router.refresh();
    onClose();
  }

  async function doCancel() {
    setBusy(true);
    setErr(null);
    const res = await fetch("/api/appointments", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        id: appt.id,
        action: "cancel",
        ly_do_huy_ma: maLyDo,
        cancellation_reason: reason,
      }),
    });
    setBusy(false);
    if (!res.ok) {
      setErr((await res.json()).error ?? "Lỗi hủy lịch.");
      return;
    }
    finish();
  }

  const initial: BookingInitial = {
    serviceId: appt.service_type_id ?? "",
    doctorId: appt.doctor_id ?? "",
    doctorLabel: appt.doctor_name ?? "",
    locationId: appt.location_id ?? "",
    apptDate: origDate,
    apptTime: origTime,
    channel: appt.booking_channel ?? "",
  };
  const edit: BookingEdit = {
    appointmentId: appt.id,
    origDate,
    origTime,
    serviceLabel: appt.service_name ?? "",
    onDone: finish,
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-ink/40 p-4"
      onClick={onClose}
      role="presentation"
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="appointment-edit-title"
        className="my-8 w-full max-w-2xl rounded-card bg-surface p-5 shadow-panel"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={keepFocusInside}
      >
        <div className="mb-3 flex items-start justify-between gap-2">
          <div className="min-w-0">
            <h3
              id="appointment-edit-title"
              className="text-base font-semibold text-ink"
            >
              Đổi / hủy lịch hẹn
            </h3>
            <p className="truncate text-xs text-ink-muted">{patientName}</p>
          </div>
          <button
            ref={closeButtonRef}
            type="button"
            onClick={onClose}
            aria-label="Đóng"
            className="rounded-md p-1 text-ink-muted hover:bg-surface-sunken"
          >
            <X size={18} />
          </button>
        </div>

        <div className="mb-4 rounded-lg border border-brand-100 bg-brand-50 px-3 py-2 text-sm text-brand-800">
          Lịch hiện tại: <b>{fmtDateTimeOrDate(appt.slot_start)}</b>
          {appt.doctor_name ? ` · ${appt.doctor_name}` : ""}
          {appt.service_name ? ` · ${appt.service_name}` : ""}
          <span className="mt-1 block text-xs text-brand-800/80">
            Chọn ngày/giờ mới bên dưới rồi bấm “Đổi lịch hẹn”. Chưa đổi thì nút
            vẫn khoá.
          </span>
        </div>

        <AppointmentBooking
          clinicPatientId={clinicPatientId}
          services={services}
          doctors={doctors}
          locations={locations}
          onBooked={() => {}}
          edit={edit}
          initial={initial}
          secondary={
            <button
              type="button"
              onClick={() => setShowCancel((v) => !v)}
              disabled={busy}
              className="inline-flex min-h-11 items-center justify-center rounded-control border border-danger px-4 text-sm font-medium text-danger hover:bg-danger-bg disabled:opacity-50 sm:min-h-0 sm:py-2"
            >
              Hủy lịch hẹn
            </button>
          }
        />

        {showCancel && (
          <div className="mt-3 space-y-2 rounded-control border border-danger bg-danger-bg p-3">
            {/* LÝ DO LÀ BẮT BUỘC, không còn "(tuỳ chọn)".
                Ô chữ tự do cũ để lại phần lớn lịch huỷ không có lý do gì, và
                phần có thì mỗi người viết một kiểu — "bận", "Bận", "ko đến
                được" — nên không đếm được cái gì. Ba mã đầu là ba THỜI ĐIỂM,
                và mỗi thời điểm tốn của phòng khám một khoản khác nhau. */}
            <label htmlFor="appointment-cancel-code" className={LABEL}>
              Lý do hủy
            </label>
            <select
              id="appointment-cancel-code"
              className={INPUT}
              value={maLyDo}
              onChange={(e) => setMaLyDo(e.target.value)}
            >
              <option value="">— Chọn lý do —</option>
              {LY_DO_HUY_THU_TU.map((ma) => (
                <option key={ma} value={ma}>
                  {LY_DO_HUY[ma]}
                </option>
              ))}
            </select>
            {maLyDo === "KHAC" && (
              <input
                id="appointment-cancel-reason"
                className={INPUT}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Khách nói gì?"
              />
            )}
            <div className="flex gap-2">
              <button
                type="button"
                onClick={doCancel}
                disabled={busy || !maLyDo || (maLyDo === "KHAC" && !reason.trim())}
                className="min-h-10 rounded-control bg-danger px-4 text-sm font-semibold text-white hover:bg-danger disabled:opacity-50"
              >
                {busy ? "Đang hủy…" : "Xác nhận hủy lịch"}
              </button>
              <button
                type="button"
                onClick={() => setShowCancel(false)}
                className="min-h-10 rounded-control border border-line bg-surface px-4 text-sm text-ink-soft hover:bg-surface-sunken"
              >
                Thôi
              </button>
            </div>
          </div>
        )}
        {err && (
          <p role="alert" className="mt-2 text-sm text-danger">
            {err}
          </p>
        )}
      </div>
    </div>
  );
}
