"use client";

// MODAL đặt lịch nhanh từ "Danh sách bệnh nhân": bấm "Tái khám" trong popup hồ sơ →
// mở overlay CHỈ chứa khu vực đặt lịch (tái dùng <AppointmentBooking>, y như phần đặt
// lịch ở form tạo/nhập bệnh nhân), không phải điều hướng sang cả trang /patients/[id].
// Đặt xong → đóng modal + parent router.refresh() để bảng "Lịch sử lịch hẹn" cập nhật.

import { useEffect } from "react";
import AppointmentBooking, { type Option } from "../patients/AppointmentBooking";

interface ModalPatient {
  clinic_patient_id: string;
  full_name: string;
  patient_code: string;
}

export default function QuickBookingModal({
  patient,
  services,
  doctors,
  locations,
  onClose,
  onBooked,
  walkin = false,
}: {
  patient: ModalPatient;
  services: Option[];
  doctors: Option[];
  locations: Option[];
  onClose: () => void;
  onBooked: (appointmentId: string) => void;
  /** Lễ tân: xếp BN tái khám vãng lai vào chỗ Ưu tiên (ô xanh) thay vì ô hồng. */
  walkin?: boolean;
}) {
  // Esc để đóng.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-4 sm:p-8"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="Đặt lịch hẹn"
    >
      <div
        className="my-4 w-full max-w-2xl rounded-2xl bg-white p-5 shadow-xl sm:my-8"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h3 className="text-base font-semibold text-ink">Đặt lịch hẹn</h3>
            <p className="text-sm text-ink-muted">
              {patient.full_name} · {patient.patient_code}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Đóng"
            className="rounded-lg px-2 py-1 text-sm text-ink-muted hover:bg-surface-sunken hover:text-ink"
          >
            ✕
          </button>
        </div>
        <AppointmentBooking
          clinicPatientId={patient.clinic_patient_id}
          services={services}
          doctors={doctors}
          locations={locations}
          onBooked={onBooked}
          walkin={walkin}
        />
      </div>
    </div>
  );
}
