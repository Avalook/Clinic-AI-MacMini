"use client";

// Modal ĐỔI / HỦY lịch hẹn của khách — mở từ "Thông tin khách hàng" khi bấm ô
// "Lịch hẹn sắp tới". Tái dùng form đặt lịch (AppointmentBooking) ở chế độ SỬA:
// điền sẵn lịch cũ, chỉ cho "Đổi lịch hẹn" khi đã chọn ngày/giờ mới (reschedule).
// Kèm nút "Hủy lịch hẹn" (cancel). Chỉ CSKH/QL/Trưởng ca thấy (gate ở parent + API).

import { useState } from "react";
import { useRouter } from "next/navigation";
import { X } from "lucide-react";
import AppointmentBooking, {
  type Option,
  type BookingEdit,
  type BookingInitial,
} from "../patients/AppointmentBooking";
import { fmtDateTimeOrDate } from "../../../lib/datetime";
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
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

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
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-4"
      onClick={onClose}
    >
      <div
        className="my-8 w-full max-w-2xl rounded-xl bg-white p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-3 flex items-start justify-between gap-2">
          <div className="min-w-0">
            <h3 className="text-base font-semibold text-[#171717]">
              Đổi / hủy lịch hẹn
            </h3>
            <p className="truncate text-xs text-[#888888]">{patientName}</p>
          </div>
          <button
            onClick={onClose}
            aria-label="Đóng"
            className="rounded-md p-1 text-[#71717a] hover:bg-[#f4f4f5]"
          >
            <X size={18} />
          </button>
        </div>

        <div className="mb-4 rounded-lg border border-[#f3cfe0] bg-[#fdf2f8] px-3 py-2 text-sm text-[#9d2463]">
          Lịch hiện tại: <b>{fmtDateTimeOrDate(appt.slot_start)}</b>
          {appt.doctor_name ? ` · ${appt.doctor_name}` : ""}
          {appt.service_name ? ` · ${appt.service_name}` : ""}
          <span className="mt-1 block text-xs text-[#9d2463]/80">
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
              className="inline-flex min-h-11 items-center justify-center rounded-md border border-[#fecaca] px-4 text-sm font-medium text-[#dc2626] hover:bg-[#fef2f2] disabled:opacity-50 sm:min-h-0 sm:py-2"
            >
              Hủy lịch hẹn
            </button>
          }
        />

        {showCancel && (
          <div className="mt-3 space-y-2 rounded-lg border border-[#fecaca] bg-[#fff7f7] p-3">
            <label className={LABEL}>Lý do hủy (tuỳ chọn)</label>
            <input
              className={INPUT}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="VD: khách bận, đổi lịch…"
            />
            <div className="flex gap-2">
              <button
                onClick={doCancel}
                disabled={busy}
                className="min-h-10 rounded-lg bg-[#dc2626] px-4 text-sm font-semibold text-white hover:bg-[#b91c1c] disabled:opacity-50"
              >
                {busy ? "Đang hủy…" : "Xác nhận hủy lịch"}
              </button>
              <button
                onClick={() => setShowCancel(false)}
                className="min-h-10 rounded-lg border border-[#e4e4e7] bg-white px-4 text-sm text-[#52525b] hover:bg-[#f4f4f5]"
              >
                Thôi
              </button>
            </div>
          </div>
        )}
        {err && <p className="mt-2 text-sm text-[#dc2626]">{err}</p>}
      </div>
    </div>
  );
}
