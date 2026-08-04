"use client";

// QuickBookingModal — Modal Đặt lịch hẹn sử dụng CskhBookingGrid mới.
// Mở khi bấm "Đặt lịch" từ màn "Thông tin khách hàng" hoặc "Danh sách bệnh nhân".

import { useEffect } from "react";
import { X } from "lucide-react";
import CskhBookingGrid from "../appointments/CskhBookingGrid";

interface ModalPatient {
  clinic_patient_id: string;
  full_name: string;
  patient_code: string;
}

export default function QuickBookingModal({
  onClose,
}: {
  patient: ModalPatient;
  services?: unknown[];
  doctors?: unknown[];
  locations?: unknown[];
  onClose: () => void;
  onBooked?: (appointmentId: string) => void;
  walkin?: boolean;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-black/50 p-2 sm:p-6 backdrop-blur-xs"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="Đặt lịch hẹn"
    >
      <div
        className="relative my-4 w-full max-w-6xl max-h-[92vh] overflow-y-auto rounded-2xl bg-surface p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          type="button"
          onClick={onClose}
          aria-label="Đóng"
          className="absolute right-4 top-4 z-10 rounded-full bg-surface-muted p-2 text-ink-muted hover:bg-surface-sunken hover:text-ink"
        >
          <X size={18} />
        </button>
        <CskhBookingGrid />
      </div>
    </div>
  );
}
