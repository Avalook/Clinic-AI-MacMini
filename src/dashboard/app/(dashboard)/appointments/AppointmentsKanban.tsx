// Kanban board for appointments: three status columns side-by-side on desktop,
// stacked on mobile (no horizontal swipe). Each appointment is a card with the
// patient + slot + doctor info; the doctor can confirm/decline their own
// pending cards inline. Presentational — the page fetches the rows.
// SECURITY: national_id_number (CCCD) is never selected — D-identity gate.

import Link from "next/link";
import AppointmentActions from "./AppointmentActions";
import { fmtTimeOrNone, fmtDate } from "../../../lib/datetime";
import { doctorName } from "../../../lib/doctor-name";

export interface KanbanRow {
  id: string;
  clinic_patient_id: string;
  doctor_id: string | null;
  queue_number: string | null;
  booking_channel: string | null;
  slot_start: string;
  status: string;
  patient: {
    full_name: string;
    phone_primary: string | null;
    patient_code: string;
  } | null;
  doctor: { full_name: string } | null;
  service: { name: string } | null;
}

export const KANBAN_SELECT = `
  id, clinic_patient_id, doctor_id, queue_number, booking_channel, slot_start, status,
  patient:patient!clinic_patient_id ( full_name, phone_primary, patient_code ),
  doctor:staff!doctor_id ( full_name ),
  service:service_type!service_type_id ( name )
`;

interface Column {
  key: string;
  label: string;
  statuses: string[];
  accent: string; // left-border / dot colour
  tint: string; // soft header background
}

const COLUMNS: Column[] = [
  {
    key: "pending",
    label: "Chờ xác nhận",
    statuses: ["SCHEDULED"],
    accent: "#2563eb",
    tint: "#eff6ff",
  },
  {
    key: "confirmed",
    label: "Đã xác nhận",
    statuses: ["CSKH_CONFIRMED", "CONFIRMED", "CHECKED_IN"],
    accent: "#16a34a",
    tint: "#f0fdf4",
  },
  {
    key: "done",
    label: "Đã khám xong",
    statuses: ["COMPLETED"],
    accent: "#71717a",
    tint: "#f4f4f5",
  },
];

function Card({
  a,
  withDate,
  canAct,
  staffId,
}: {
  a: KanbanRow;
  withDate: boolean;
  canAct: boolean;
  staffId: string | null;
}) {
  const showActions =
    canAct && a.status === "SCHEDULED" && !!staffId && a.doctor_id === staffId;
  return (
    <div className="rounded-lg border border-line bg-white p-3 shadow-[0_1px_2px_rgba(0,0,0,0.06)]">
      {/* Patient + code */}
      <div className="flex items-start justify-between gap-2">
        <Link
          href={`/patients/${a.clinic_patient_id}`}
          className="font-medium text-ink hover:text-brand-600 hover:underline"
        >
          {a.patient?.full_name ?? "—"}
        </Link>
        {a.queue_number && (
          <span className="shrink-0 rounded-full bg-surface-sunken px-2 py-0.5 text-[11px] font-medium text-ink-muted">
            STT {a.queue_number}
          </span>
        )}
      </div>
      <p className="mt-0.5 font-mono text-xs text-ink-muted">
        {a.patient?.patient_code ?? "—"}
        {a.patient?.phone_primary ? ` · ${a.patient.phone_primary}` : ""}
      </p>

      {/* Time + service */}
      <p className="mt-2 text-sm text-ink">
        <span className="font-medium">
          {withDate ? `${fmtDate(a.slot_start)} · ` : ""}
          {fmtTimeOrNone(a.slot_start)}
        </span>
        {a.service?.name ? ` · ${a.service.name}` : ""}
      </p>

      {/* Doctor + channel */}
      <p className="mt-0.5 text-xs text-ink-muted">
        {a.doctor?.full_name ? doctorName(a.doctor.full_name) : "—"}
        {a.booking_channel ? ` · ${a.booking_channel}` : ""}
      </p>

      {showActions && (
        <div className="mt-2 border-t border-surface-sunken pt-2">
          <AppointmentActions appointmentId={a.id} />
        </div>
      )}
    </div>
  );
}

export default function AppointmentsKanban({
  title,
  rows,
  withDate = false,
  canAct,
  staffId,
}: {
  title: string;
  rows: KanbanRow[];
  /** Show the date on cards (used by the "upcoming" board). */
  withDate?: boolean;
  /** Caller is a doctor → confirm/decline controls on own pending cards. */
  canAct: boolean;
  staffId: string | null;
}) {
  return (
    <section className="space-y-3">
      {title && (
        <h2 className="text-base font-semibold text-ink">
          {title}
          <span className="ml-2 text-sm font-normal text-ink-muted">
            ({rows.length})
          </span>
        </h2>
      )}

      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        {COLUMNS.map((col) => {
          const cards = rows.filter((r) => col.statuses.includes(r.status));
          return (
            <div
              key={col.key}
              className="flex flex-col rounded-lg border border-brand-100 bg-brand-50"
            >
              <div
                className="flex items-center justify-between gap-2 rounded-t-lg border-b border-line px-3 py-2"
                style={{ backgroundColor: col.tint }}
              >
                <span className="flex items-center gap-2 text-sm font-medium text-ink">
                  <span
                    className="h-2 w-2 rounded-full"
                    style={{ backgroundColor: col.accent }}
                  />
                  {col.label}
                </span>
                <span className="rounded-full bg-white px-2 py-0.5 text-xs font-medium text-ink-muted">
                  {cards.length}
                </span>
              </div>

              <div className="flex-1 space-y-2 p-2">
                {cards.map((a) => (
                  <Card
                    key={a.id}
                    a={a}
                    withDate={withDate}
                    canAct={canAct}
                    staffId={staffId}
                  />
                ))}
                {cards.length === 0 && (
                  <p className="px-2 py-6 text-center text-xs text-ink-faint">
                    Trống
                  </p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
