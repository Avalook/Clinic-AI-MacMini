"use client";

// "Thông tin khách hàng" — DANH BẠ khách đã nhập, dạng master-detail:
//   • Trái: danh sách (lọc Hôm nay/Tuần/Tháng/Tất cả theo NGÀY TẠO hoặc NGÀY HẸN
//     + tìm tên/mã/SĐT). Mỗi dòng hiện LỊCH HẸN sắp tới của khách.
//   • Phải: thông tin chi tiết của khách đang chọn (bôi HỒNG ở list).
// Sau khi tạo khách mới, NewPatientForm điều hướng /customers?selected=<id> →
// khách đó tự được chọn + bôi hồng. Lọc/tìm: GÕ TỚI ĐÂU LỌC TỚI ĐÓ — lọc CLIENT
// tức thì trên danh sách đã nạp + tự gọi server (debounce 350ms, bọc useTransition
// nên KHÔNG nháy skeleton / không mất focus) để phủ toàn DB. KHÔNG cần bấm "Tìm"
// (feedback PM 23/6). CHỌN = state client.

import { useState, useEffect, useMemo, useRef, useTransition } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Search, ExternalLink, X, CalendarClock } from "lucide-react";
import { fmtDate, fmtDateTimeOrDate } from "../../../lib/datetime";
import { unaccentVi } from "../../../lib/validation";
import PatientAdminEditor from "../PatientAdminEditor";
import AppointmentEditModal, {
  type EditableAppt,
} from "./AppointmentEditModal";
import QuickBookingModal from "../patient-list/QuickBookingModal";

export interface CustomerRow {
  clinic_patient_id: string;
  patient_code: string;
  full_name: string;
  date_of_birth: string | null;
  birth_year: number | null;
  phone_primary: string | null;
  phone_secondary: string | null;
  gender: string | null;
  ethnicity: string | null;
  nationality: string | null;
  occupation: string | null;
  patient_objection: string | null;
  address: string | null;
  guardian_name: string | null;
  location_id: string | null;
  created_at: string | null;
  van_de_di_kham: string | null;
  linh_vuc: string | null;
}
/** Lịch hẹn "đại diện" của 1 khách (sắp tới gần nhất, else gần nhất quá khứ). */
export interface ApptInfo {
  slot_start: string;
  status: string;
  upcoming: boolean;
  count: number;
  /** Đã khám xong (có ≥1 lịch COMPLETED) → mới hiện nút "Hồ sơ & lịch sử khám". */
  examined: boolean;
  /** Lịch SẮP TỚI còn "sống" (đủ field để ĐỔI/HỦY). Chỉ có khi canManage. */
  appt?: EditableAppt;
}
export interface Opt {
  id: string;
  label: string;
}
export type Period = "today" | "week" | "month" | "all";
export type ByDim = "created" | "appt";

const PERIODS: { key: Period; label: string }[] = [
  { key: "today", label: "Hôm nay" },
  { key: "week", label: "Tuần này" },
  { key: "month", label: "Tháng này" },
  { key: "all", label: "Tất cả" },
];

const BY_OPTS: { key: ByDim; label: string }[] = [
  { key: "created", label: "Ngày tạo" },
  { key: "appt", label: "Ngày hẹn" },
];

export default function CustomersView({
  rows,
  apptByPatient,
  locations,
  q,
  period,
  by,
  initialSelected,
  canEdit = false,
  canManage = false,
  services = [],
  doctors = [],
}: {
  rows: CustomerRow[];
  apptByPatient: Record<string, ApptInfo>;
  locations: Opt[];
  q: string;
  period: Period;
  by: ByDim;
  initialSelected: string | null;
  /** CSKH/Lễ tân/QL: sửa thông tin hành chính ngay trong panel chi tiết. */
  canEdit?: boolean;
  /** CSKH/QL/Trưởng ca: bấm ô "Lịch hẹn sắp tới" để ĐỔI/HỦY lịch. */
  canManage?: boolean;
  /** Dropdown cho modal đổi lịch (chỉ nạp khi canManage). */
  services?: Opt[];
  doctors?: Opt[];
}) {
  const router = useRouter();
  // Mặc định KHÔNG chọn ai → chỉ hiện danh sách. Bấm 1 khách mới hiện chi tiết
  // (trừ khi vừa tạo khách mới → initialSelected để bôi hồng + xem ngay).
  const [sel, setSel] = useState<string | null>(initialSelected ?? null);
  const [term, setTerm] = useState(q);
  const [editOpen, setEditOpen] = useState(false);
  const [bookOpen, setBookOpen] = useState(false);
  const [isPending, startTransition] = useTransition();

  const selected = rows.find((r) => r.clinic_patient_id === sel) ?? null;
  const selectedAppt = selected
    ? apptByPatient[selected.clinic_patient_id]
    : undefined;
  const locName = (id: string | null) =>
    locations.find((l) => l.id === id)?.label ?? "—";

  function go(nextPeriod: Period, nextQ: string, nextBy: ByDim) {
    const p = new URLSearchParams();
    if (nextQ.trim()) p.set("q", nextQ.trim());
    if (nextPeriod !== "all") p.set("period", nextPeriod);
    if (nextBy !== "created") p.set("by", nextBy);
    const qs = p.toString();
    router.push(`/customers${qs ? `?${qs}` : ""}`);
  }

  // Lọc CLIENT tức thì trên rows đã nạp (cảm giác như /patient-list) — không phân
  // biệt dấu/hoa-thường, khớp một phần tên/mã/SĐT. Server (debounce dưới) sẽ phủ
  // toàn DB cho từ khoá khớp BN nằm ngoài ~300 dòng đã nạp.
  const shown = useMemo(() => {
    const t = unaccentVi(term.trim());
    if (!t) return rows;
    return rows.filter(
      (r) =>
        unaccentVi(r.full_name).includes(t) ||
        unaccentVi(r.patient_code).includes(t) ||
        unaccentVi(r.phone_primary ?? "").includes(t),
    );
  }, [rows, term]);

  // Tự động tìm khi gõ (debounce 350ms) — bỏ qua lần mount đầu + khi term trùng q
  // hiện tại (tránh đẩy router thừa / lặp). startTransition → giữ danh sách cũ
  // trong lúc server trả về (không nháy skeleton, không mất focus ô nhập).
  const firstRun = useRef(true);
  useEffect(() => {
    if (firstRun.current) {
      firstRun.current = false;
      return;
    }
    if (term.trim() === q.trim()) return;
    const id = setTimeout(() => {
      startTransition(() => go(period, term, by));
    }, 350);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [term]);

  return (
    <div className="space-y-3">
      {/* Bộ lọc + tìm kiếm */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap items-center gap-1.5">
          {/* Chiều lọc: theo ngày TẠO hay ngày HẸN */}
          <div className="inline-flex rounded-full border border-brand-100 bg-white p-0.5">
            {BY_OPTS.map((b) => (
              <button
                key={b.key}
                onClick={() => go(period, term, b.key)}
                className={
                  "rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors " +
                  (by === b.key
                    ? "bg-brand-800 text-white"
                    : "text-brand-800 hover:bg-brand-50")
                }
              >
                {b.label}
              </button>
            ))}
          </div>
          <span className="px-0.5 text-line-strong">·</span>
          {PERIODS.map((p) => (
            <button
              key={p.key}
              onClick={() => go(p.key, term, by)}
              className={
                "rounded-full px-3 py-1 text-xs font-medium transition-colors " +
                (period === p.key
                  ? "bg-brand-600 text-white"
                  : "border border-brand-100 bg-white text-brand-800 hover:bg-brand-50")
              }
            >
              {p.label}
            </button>
          ))}
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            startTransition(() => go(period, term, by));
          }}
          className="flex items-center gap-2"
        >
          <div className="relative">
            <Search
              size={15}
              className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-faint"
            />
            <input
              value={term}
              onChange={(e) => setTerm(e.target.value)}
              placeholder="Tìm tên / mã BN / SĐT…"
              className="min-h-9 w-full rounded-lg border border-line bg-white pl-8 pr-3 text-sm outline-none focus:border-brand-600 focus:ring-2 focus:ring-brand-600/15 sm:w-64"
            />
          </div>
          {term && (
            <button
              type="button"
              onClick={() => {
                setTerm("");
                startTransition(() => go(period, "", by));
              }}
              className="min-h-9 rounded-lg border border-line bg-white px-3 text-sm text-ink-soft hover:bg-surface-sunken"
            >
              Xoá
            </button>
          )}
        </form>
      </div>

      {by === "appt" && period !== "all" && (
        <p className="text-xs text-brand-800">
          Đang xem khách có <b>lịch hẹn</b> trong kỳ đã chọn.
        </p>
      )}

      {/* Dòng đếm ĐẶT TRÊN cả 2 cột → list + chi tiết bắt đầu cùng 1 mốc (canh đều). */}
      <div className="text-xs text-ink-muted">
        {shown.length} khách hàng
        {isPending && " · đang tìm…"}
        {rows.length >= 300 && " (300 gần nhất — lọc hẹp hơn nếu cần)"}
        {selected && (
          <span className="text-brand-800">
            {" "}
            · đang xem 1 khách (bấm khách khác để đổi)
          </span>
        )}
      </div>

      <div className="flex flex-col gap-4 lg:flex-row lg:items-start">
        {/* DANH SÁCH (trái) */}
        <div className="min-w-0 flex-1">
          <div className="h-[560px] max-h-[80vh] overflow-y-auto rounded-xl border border-brand-100 bg-white shadow-[0_1px_3px_rgba(236,72,153,0.08)]">
            {shown.length === 0 ? (
              <p className="px-4 py-12 text-center text-sm text-ink-faint">
                {term.trim()
                  ? "Không tìm thấy khách khớp từ khoá."
                  : by === "appt"
                    ? "Không có khách nào có lịch hẹn trong kỳ này."
                    : "Chưa có bệnh nhân nào trong khoảng lọc này. Tạo ở “Tạo bệnh nhân”."}
              </p>
            ) : (
              <ul className="divide-y divide-brand-100">
                {shown.map((r) => {
                  const active =
                    r.clinic_patient_id === selected?.clinic_patient_id;
                  const ap = apptByPatient[r.clinic_patient_id];
                  return (
                    <li key={r.clinic_patient_id}>
                      <button
                        onClick={() => setSel(r.clinic_patient_id)}
                        className={
                          "flex w-full flex-col items-start px-3 py-2.5 text-left transition-colors " +
                          (active ? "bg-brand-100" : "hover:bg-brand-50")
                        }
                      >
                        <span
                          className={
                            "truncate text-sm font-semibold " +
                            (active ? "text-status-cancelled" : "text-ink")
                          }
                        >
                          {r.full_name}
                        </span>
                        <span className="mt-0.5 truncate font-mono text-[11px] text-ink-muted">
                          {r.patient_code}
                          {r.phone_primary ? ` · ${r.phone_primary}` : ""}
                        </span>
                        {ap ? (
                          <span
                            className={
                              "mt-0.5 inline-flex items-center gap-1 truncate text-[11px] " +
                              (ap.upcoming
                                ? "font-medium text-brand-800"
                                : "text-ink-faint")
                            }
                          >
                            <CalendarClock size={11} />
                            {ap.upcoming ? "Hẹn" : "Gần nhất"}:{" "}
                            {fmtDateTimeOrDate(ap.slot_start)}
                            {ap.count > 1 ? ` · ${ap.count} lịch` : ""}
                          </span>
                        ) : (
                          <span className="mt-0.5 truncate text-[11px] text-[#c4c4c8]">
                            Chưa có lịch hẹn
                          </span>
                        )}
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </div>

        {/* CHI TIẾT (phải) — CHỈ hiện khi đã bấm chọn 1 khách; cùng chiều cao + mốc
            trên với list cho đều. Bấm X để đóng, về lại chỉ-danh-sách. */}
        {selected && (
          <aside className="h-[560px] max-h-[80vh] w-full shrink-0 overflow-y-auto rounded-xl border border-brand-200 bg-brand-50 p-4 shadow-[0_1px_3px_rgba(0,0,0,0.06)] lg:w-[400px]">
              <div className="mb-3 flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <h3 className="truncate text-base font-semibold text-status-cancelled">
                    {selected.full_name}
                  </h3>
                  <p className="font-mono text-xs text-ink-muted">
                    {selected.patient_code}
                  </p>
                </div>
                <button
                  onClick={() => setSel(null)}
                  aria-label="Đóng chi tiết"
                  className="rounded-md p-1 text-status-cancelled hover:bg-white/60"
                >
                  <X size={16} />
                </button>
              </div>

              {/* Lịch hẹn nổi bật (yêu cầu 05/06: thấy ngày-giờ hẹn ngay).
                  CSKH/QL: BẤM để mở modal ĐỔI / HỦY lịch (chỉ khi còn lịch sắp tới). */}
              {canManage && selectedAppt?.appt ? (
                <button
                  onClick={() => setEditOpen(true)}
                  className="mb-3 flex w-full items-center gap-2 rounded-lg border border-brand-100 bg-white px-3 py-2 text-left transition-colors hover:border-brand-600 hover:bg-brand-50"
                >
                  <CalendarClock size={15} className="shrink-0 text-brand-600" />
                  <span className="text-sm text-ink">
                    <span className="text-ink-muted">Lịch hẹn sắp tới: </span>
                    <b>{fmtDateTimeOrDate(selectedAppt.slot_start)}</b>
                    {selectedAppt.count > 1 && (
                      <span className="text-ink-muted">
                        {" "}
                        · {selectedAppt.count} lịch
                      </span>
                    )}
                    <span className="ml-1 font-medium text-brand-600">
                      · bấm để đổi / hủy
                    </span>
                  </span>
                </button>
              ) : (
                <div className="mb-3 flex items-center gap-2 rounded-lg border border-brand-100 bg-white px-3 py-2">
                  <CalendarClock size={15} className="shrink-0 text-brand-600" />
                  {selectedAppt ? (
                    <span className="text-sm text-ink">
                      <span className="text-ink-muted">
                        {selectedAppt.upcoming
                          ? "Lịch hẹn sắp tới: "
                          : "Lịch gần nhất: "}
                      </span>
                      <b>{fmtDateTimeOrDate(selectedAppt.slot_start)}</b>
                      {selectedAppt.count > 1 && (
                        <span className="text-ink-muted">
                          {" "}
                          · {selectedAppt.count} lịch
                        </span>
                      )}
                    </span>
                  ) : (
                    <span className="text-sm text-ink-faint">
                      Chưa có lịch hẹn nào.
                    </span>
                  )}
                </div>
              )}

              {/* Chưa có lịch sắp tới (vd vừa hủy) → cho ĐẶT LỊCH lại ngay. */}
              {canEdit && !selectedAppt?.upcoming && (
                <button
                  onClick={() => setBookOpen(true)}
                  className="mb-3 inline-flex min-h-10 items-center gap-1 rounded-lg bg-brand-600 px-4 text-sm font-semibold text-white hover:bg-brand-700"
                >
                  + Đặt lịch
                </button>
              )}

              {canEdit ? (
                <>
                  {/* key = remount editor khi đổi khách (state cur theo từng BN). */}
                  <PatientAdminEditor
                    key={selected.clinic_patient_id}
                    patient={{
                      clinic_patient_id: selected.clinic_patient_id,
                      full_name: selected.full_name,
                      date_of_birth: selected.date_of_birth,
                      phone_primary: selected.phone_primary,
                      phone_secondary: selected.phone_secondary,
                      gender: selected.gender,
                      ethnicity: selected.ethnicity,
                      nationality: selected.nationality,
                      occupation: selected.occupation,
                      patient_objection: selected.patient_objection,
                      address: selected.address,
                      guardian_name: selected.guardian_name,
                      van_de_di_kham: selected.van_de_di_kham,
                      linh_vuc: selected.linh_vuc,
                    }}
                  />
                  <dl className="mt-2 space-y-1.5 text-sm">
                    <Row label="Cơ sở" value={locName(selected.location_id)} />
                    <Row
                      label="Ngày tạo"
                      value={fmtDateTimeOrDate(selected.created_at)}
                    />
                  </dl>
                </>
              ) : (
                <dl className="space-y-1.5 text-sm">
                  <Row label="Ngày sinh" value={dobDisplay(selected)} />
                  <Row label="Giới tính" value={selected.gender} />
                  <Row label="SĐT chính" value={selected.phone_primary} />
                  <Row label="SĐT người nhà" value={selected.phone_secondary} />
                  <Row label="Dân tộc" value={selected.ethnicity} />
                  <Row label="Quốc tịch" value={selected.nationality} />
                  <Row label="Nghề nghiệp" value={selected.occupation} />
                  <Row label="Đối tượng" value={selected.patient_objection} />
                  <Row label="Địa chỉ" value={selected.address} />
                  <Row label="Cơ sở" value={locName(selected.location_id)} />
                  <Row
                    label="Ngày tạo"
                    value={fmtDateTimeOrDate(selected.created_at)}
                  />
                </dl>
              )}

              {/* Nút hồ sơ CHỈ hiện khi khách ĐÃ KHÁM (lịch COMPLETED) — lúc đó mới
                  là "bệnh nhân" có hồ sơ/lịch sử để xem. Người mới đặt lịch /
                  check-in mà chưa khám (kể cả đang khám, hồ sơ chưa lưu) thì trang
                  này chỉ để Lễ tân/CSKH sửa thông tin hành chính, chưa có hồ sơ. */}
              {selectedAppt?.examined && (
                <div className="mt-4 flex flex-wrap gap-2">
                  <Link
                    href={`/patients/${selected.clinic_patient_id}`}
                    className="inline-flex min-h-10 items-center gap-1 rounded-lg bg-brand-600 px-4 text-sm font-semibold text-white hover:bg-brand-700"
                  >
                    <ExternalLink size={14} /> Hồ sơ & lịch sử khám
                  </Link>
                </div>
              )}
          </aside>
        )}
      </div>

      {/* Modal ĐỔI / HỦY lịch hẹn — mở khi bấm ô "Lịch hẹn sắp tới". */}
      {editOpen && selected && selectedAppt?.appt && (
        <AppointmentEditModal
          appt={selectedAppt.appt}
          patientName={selected.full_name}
          clinicPatientId={selected.clinic_patient_id}
          services={services}
          doctors={doctors}
          locations={locations}
          onClose={() => setEditOpen(false)}
        />
      )}

      {/* Modal ĐẶT LỊCH mới — mở từ nút "+ Đặt lịch" khi khách chưa có lịch. */}
      {bookOpen && selected && (
        <QuickBookingModal
          patient={{
            clinic_patient_id: selected.clinic_patient_id,
            full_name: selected.full_name,
            patient_code: selected.patient_code,
          }}
          services={services}
          doctors={doctors}
          locations={locations}
          onClose={() => setBookOpen(false)}
          onBooked={() => {
            setBookOpen(false);
            router.refresh();
          }}
        />
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="flex gap-2">
      <dt className="w-28 shrink-0 text-ink-muted">{label}</dt>
      <dd className="min-w-0 break-words text-ink">{value || "—"}</dd>
    </div>
  );
}

/** Ngày sinh hiển thị: chỉ-năm (birth_year) → "1990 (chỉ năm)"; else ngày sinh thật
 *  (tránh hiện "01/01" gây hiểu nhầm cho khách chỉ nhớ năm). */
function dobDisplay(r: CustomerRow): string | null {
  if (r.birth_year) return `${r.birth_year} (chỉ năm)`;
  return r.date_of_birth ? fmtDate(r.date_of_birth) : null;
}
