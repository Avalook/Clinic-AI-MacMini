"use client";

// "Đặt lịch hẹn" entry point on an existing patient's profile. Collapsed to a
// button by default; expands the shared <AppointmentBooking> form for this
// patient. On success it refreshes the route so the appointment-history table
// in <PatientDetail> picks up the new booking. Only rendered for intake roles
// (gated server-side in page.tsx via canWriteIntake).

import { useState } from "react";
import { useRouter } from "next/navigation";
import AppointmentBooking, { type Option } from "../AppointmentBooking";
import { BTN, CARD } from "../../form-ui";

export default function PatientBooking({
  clinicPatientId,
  services,
  doctors,
  locations,
}: {
  clinicPatientId: string;
  services: Option[];
  doctors: Option[];
  locations: Option[];
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [bookedId, setBookedId] = useState<string | null>(null);

  if (bookedId) {
    return (
      <section className={`${CARD} space-y-3`}>
        <p className="rounded bg-[#dcfce7] px-3 py-2 text-sm text-[#15803d]">
          ✓ Đã đặt lịch hẹn.
        </p>
        <button
          onClick={() => {
            setBookedId(null);
            setOpen(true);
          }}
          className={BTN}
        >
          Đặt lịch khác
        </button>
      </section>
    );
  }

  if (!open) {
    return (
      <button onClick={() => setOpen(true)} className={BTN}>
        + Đặt lịch hẹn
      </button>
    );
  }

  return (
    <section className={`${CARD} space-y-4`}>
      <div className="flex items-center justify-between">
        <h3 className="text-base font-semibold text-[#171717]">Đặt lịch hẹn</h3>
        <button
          onClick={() => setOpen(false)}
          className="text-sm text-[#71717a] hover:underline"
        >
          Đóng
        </button>
      </div>
      <AppointmentBooking
        clinicPatientId={clinicPatientId}
        services={services}
        doctors={doctors}
        locations={locations}
        onBooked={(id) => {
          setBookedId(id);
          router.refresh();
        }}
      />
    </section>
  );
}
