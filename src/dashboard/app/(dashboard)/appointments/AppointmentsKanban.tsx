// Reusable status board for appointment rows. The CSKH workspace uses a richer
// list-detail composition, while this component remains available to routes
// that only need the compact board.

import Link from "next/link";

import { fmtDate, fmtTimeOrNone } from "@/lib/datetime";
import { doctorName } from "@/lib/doctor-name";
import AppointmentActions from "./AppointmentActions";

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
  dotClass: string;
  headerClass: string;
}

const COLUMNS: Column[] = [
  {
    key: "pending",
    label: "Chờ xác nhận",
    statuses: ["SCHEDULED"],
    dotClass: "bg-status-ready",
    headerClass: "bg-status-ready-bg",
  },
  {
    key: "confirmed",
    label: "Đã xác nhận",
    statuses: ["CSKH_CONFIRMED", "CONFIRMED", "CHECKED_IN"],
    dotClass: "bg-status-assigned",
    headerClass: "bg-status-assigned-bg",
  },
  {
    key: "done",
    label: "Đã khám xong",
    statuses: ["COMPLETED"],
    dotClass: "bg-status-completed",
    headerClass: "bg-status-completed-bg",
  },
];

function Card({
  row,
  withDate,
  canAct,
  staffId,
}: {
  row: KanbanRow;
  withDate: boolean;
  canAct: boolean;
  staffId: string | null;
}) {
  const showActions =
    canAct && row.status === "SCHEDULED" && Boolean(staffId) && row.doctor_id === staffId;
  return (
    <div className="rounded-control border border-line bg-surface p-3 shadow-card">
      <div className="flex items-start justify-between gap-2">
        <Link
          href={`/patients/${row.clinic_patient_id}`}
          className="font-medium text-ink hover:text-brand-600 hover:underline"
        >
          {row.patient?.full_name ?? "—"}
        </Link>
        {row.queue_number ? (
          <span className="rounded-chip bg-surface-sunken px-2 py-0.5 text-[11px] font-medium text-ink-muted">
            STT {row.queue_number}
          </span>
        ) : null}
      </div>
      <p className="mt-0.5 font-mono text-xs text-ink-muted">
        {row.patient?.patient_code ?? "—"}
        {row.patient?.phone_primary ? ` · ${row.patient.phone_primary}` : ""}
      </p>
      <p className="mt-2 text-sm text-ink">
        <span className="font-medium">
          {withDate ? `${fmtDate(row.slot_start)} · ` : ""}
          {fmtTimeOrNone(row.slot_start)}
        </span>
        {row.service?.name ? ` · ${row.service.name}` : ""}
      </p>
      <p className="mt-0.5 text-xs text-ink-muted">
        {row.doctor?.full_name ? doctorName(row.doctor.full_name) : "—"}
        {row.booking_channel ? ` · ${row.booking_channel}` : ""}
      </p>
      {showActions ? (
        <div className="mt-2 border-t border-line pt-2">
          <AppointmentActions appointmentId={row.id} />
        </div>
      ) : null}
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
  withDate?: boolean;
  canAct: boolean;
  staffId: string | null;
}) {
  return (
    <section className="space-y-3">
      {title ? (
        <h2 className="text-base font-semibold text-ink">
          {title}
          <span className="ml-2 text-sm font-normal text-ink-muted">({rows.length})</span>
        </h2>
      ) : null}
      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        {COLUMNS.map((column) => {
          const cards = rows.filter((row) => column.statuses.includes(row.status));
          return (
            <div key={column.key} className="flex flex-col rounded-card border border-line bg-surface">
              <div className={`flex items-center justify-between gap-2 border-b border-line px-3 py-2 ${column.headerClass}`}>
                <span className="flex items-center gap-2 text-sm font-medium text-ink">
                  <span className={`size-2 rounded-full ${column.dotClass}`} aria-hidden="true" />
                  {column.label}
                </span>
                <span className="rounded-chip bg-surface px-2 py-0.5 text-xs font-medium text-ink-muted">
                  {cards.length}
                </span>
              </div>
              <div className="flex-1 space-y-2 p-2">
                {cards.map((row) => (
                  <Card key={row.id} row={row} withDate={withDate} canAct={canAct} staffId={staffId} />
                ))}
                {cards.length === 0 ? (
                  <p className="px-2 py-6 text-center text-xs text-ink-faint">Trống</p>
                ) : null}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
