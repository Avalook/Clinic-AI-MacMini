"use client";

// Danh sách bệnh nhân là bề mặt tra cứu: dữ liệu trong ba vùng đều lấy từ cùng
// một dòng lịch hẹn gần nhất. Không dựng sinh hiệu, bệnh sử hay nghĩa vụ giả khi
// API của màn này chưa tải chúng; người có quyền lâm sàng vẫn mở phiếu khám thật.

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  CalendarDays,
  ClipboardList,
  FileText,
  Phone,
  Search,
  SlidersHorizontal,
  Stethoscope,
  UserRound,
  UsersRound,
} from "lucide-react";
import { fmtDate, fmtDateTimeOrDate } from "../../../lib/datetime";
import { unaccentVi } from "../../../lib/validation";
import ClinicalRecordForm from "../tasks/ClinicalRecordForm";
import type { DoctorApptRow } from "../tasks/DoctorWorkBoard";
import SplitPane from "../SplitPane";
import { nhanPhanLoaiKham } from "../../../lib/phan-loai-kham";

/** Khối hành chính của bệnh nhân — cùng hình dạng với `appt.patient`. */
type PatientFull = NonNullable<DoctorApptRow["patient"]> & {
  /** Các số gắn THÊM — embed từ patient_sdt_them (15/08/2026). */
  patient_sdt_them?: { so_dien_thoai: string; loai: string }[] | null;
};

/** Một lần khám trong quá khứ — đủ để liệt kê, không kèm dữ liệu lâm sàng. */
export interface VisitSummary {
  id: string;
  slot_start: string;
  status: string;
  service_name: string | null;
}

export interface ExaminedRow {
  clinic_patient_id: string;
  patient_code: string;
  full_name: string;
  phone_primary: string | null;
  date_of_birth: string | null;
  gender: string | null;
  visit_count: number;
  /** TỪNG lượt, mới→cũ. `visit_count` chỉ nói "bao nhiêu", cái này nói "những lần nào". */
  visits: VisitSummary[];
  /** Ngày lượt gần nhất; `null` = chưa khám lần nào. */
  latest: string | null;
  phan_loai: "Chưa khám" | "Khám lần đầu" | "Tái khám";
  /** Khối hành chính — LUÔN có, kể cả khi chưa khám lần nào. Trước đây nó đi
   *  kèm lượt hẹn, nên hồ sơ chưa khám thì không có gì để hiện. */
  hoso: PatientFull;
  /** Lượt hẹn gần nhất; `null` = chưa khám lần nào. */
  appt: DoctorApptRow | null;
}

type Filter = "all" | "first" | "return" | "none";

const STATUS_PRESENTATION: Record<string, { label: string; className: string }> = {
  SCHEDULED: { label: "Chưa xác nhận", className: "bg-warning-bg text-warning" },
  CSKH_CONFIRMED: { label: "Đã xác nhận", className: "bg-brand-100 text-brand-800" },
  CONFIRMED: { label: "Đã xác nhận", className: "bg-brand-100 text-brand-800" },
  CHECKED_IN: { label: "Đã check-in", className: "bg-status-assigned-bg text-status-assigned" },
  IN_PROGRESS: { label: "Đang khám", className: "bg-status-in-progress-bg text-status-in-progress" },
  COMPLETED: { label: "Đã khám xong", className: "bg-success-bg text-success" },
  NO_SHOW: { label: "Không đến", className: "bg-surface-sunken text-ink-soft" },
  CANCELLED: { label: "Đã huỷ", className: "bg-surface-sunken text-ink-soft" },
  DOCTOR_DECLINED: { label: "Bác sĩ từ chối", className: "bg-danger-bg text-danger" },
};

function initials(name: string): string {
  return name
    .trim()
    .split(/\s+/)
    .slice(-2)
    .map((part) => part[0]?.toLocaleUpperCase("vi-VN") ?? "")
    .join("") || "?";
}

const KIND_CLASS: Record<ExaminedRow["phan_loai"], string> = {
  "Khám lần đầu": "bg-success-bg text-success",
  "Tái khám": "bg-warning-bg text-warning",
  // Chưa khám là một trạng thái BÌNH THƯỜNG của hồ sơ mới, không phải cảnh
  // báo — nên nó xám, đứng yên, không tranh chỗ với hai nhãn kia.
  "Chưa khám": "bg-surface-sunken text-ink-soft",
};

function PatientKind({ value }: { value: ExaminedRow["phan_loai"] }) {
  return (
    <span
      className={
        "inline-flex items-center rounded-chip px-2 py-1 text-label font-semibold " +
        KIND_CLASS[value]
      }
    >
      {nhanPhanLoaiKham(value)}
    </span>
  );
}

function AppointmentStatus({ status }: { status: string }) {
  const presentation = STATUS_PRESENTATION[status] ?? {
    label: status,
    className: "bg-surface-sunken text-ink-soft",
  };
  return (
    <span className={`inline-flex rounded-chip px-2 py-1 text-label font-semibold ${presentation.className}`}>
      {presentation.label}
    </span>
  );
}

function DetailLine({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="flex gap-2.5 py-2.5">
      <span className="mt-0.5 shrink-0 text-brand-600">{icon}</span>
      <div className="min-w-0">
        <p className="text-label font-semibold uppercase tracking-wide text-ink-faint">{label}</p>
        <div className="mt-0.5 break-words text-sm text-ink">{value}</div>
      </div>
    </div>
  );
}

/** Một dòng "nhãn — giá trị" của khối hành chính.
 *
 * Thiếu dữ liệu thì nói THIẾU, không bỏ dòng đi: một ô trống nhìn ra ngay là
 * chưa ai điền, còn một dòng biến mất thì không ai biết nó từng tồn tại.
 */
function HangHanhChinh({
  nhan,
  giaTri,
}: {
  nhan: string;
  giaTri?: string | null;
}) {
  const co = Boolean(giaTri && String(giaTri).trim());
  return (
    <div className="flex items-start justify-between gap-3">
      <dt className="shrink-0 text-xs text-ink-muted">{nhan}</dt>
      <dd className={`text-right ${co ? "text-ink" : "text-ink-faint"}`}>
        {co ? giaTri : "Chưa có"}
      </dd>
    </div>
  );
}

export default function PatientListView({
  rows,
  enablePopup = false,
  canEditAdmin = false,
  showPreVisitBrief = false,
  showRebook = false,
  enableVisitPager = false,
}: {
  rows: ExaminedRow[];
  /** Chỉ vai lâm sàng mở phiếu khám thật ở vùng SplitPane. */
  enablePopup?: boolean;
  canEditAdmin?: boolean;
  showPreVisitBrief?: boolean;
  showRebook?: boolean;
  enableVisitPager?: boolean;
}) {
  const router = useRouter();
  const [term, setTerm] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [selectedId, setSelectedId] = useState<string | null>(rows[0]?.clinic_patient_id ?? null);
  const [openAppt, setOpenAppt] = useState<DoctorApptRow | null>(null);
  const [moDanhSachLuot, setMoDanhSachLuot] = useState(false);

  // "TÁI KHÁM" ĐI TỚI MÀN ĐẶT LỊCH THẬT.
  //
  // Trước đây nút này mở `QuickBookingModal` → `CskhBookingGrid`: một màn DỰNG
  // SẴN (tên "Nguyễn Văn An", "BS. Trần Minh Đức", khung giờ viết cứng, nhãn
  // "Sắp ra mắt v2"). Bấm "Xác nhận đặt lịch" trong đó KHÔNG ghi gì xuống
  // database, mà màn hình vẫn báo như đã xong.
  //
  // Đường vào ấy đã bị gỡ ở màn Quản lý khách hàng (af1cf1a) nhưng CÒN NGUYÊN ở
  // đây — Lễ tân/CSKH mở phiếu khám rồi bấm "Tái khám" là rơi thẳng vào nó. Cả
  // hai đường nay đi cùng một chỗ: `/appointments`, kèm `?bn=` để không mất
  // người đang mở giữa đường.
  function datLichLai(appt: DoctorApptRow) {
    const ma = appt.patient?.patient_code ?? "";
    router.push(`/appointments${ma ? `?bn=${encodeURIComponent(ma)}` : ""}`);
  }

  const shown = useMemo(() => {
    const normalized = unaccentVi(term.trim());
    return rows.filter((row) => {
      if (filter === "first" && row.phan_loai !== "Khám lần đầu") return false;
      if (filter === "return" && row.phan_loai !== "Tái khám") return false;
      if (filter === "none" && row.phan_loai !== "Chưa khám") return false;
      if (!normalized) return true;
      return (
        unaccentVi(row.full_name).includes(normalized) ||
        unaccentVi(row.patient_code).includes(normalized) ||
        unaccentVi(row.phone_primary ?? "").includes(normalized)
      );
    });
  }, [filter, rows, term]);

  // Đổi bộ lọc không được để panel tiếp tục hiện một BN đã bị lọc ra.
  const selected =
    shown.find((item) => item.clinic_patient_id === selectedId) ??
    shown[0] ??
    null;
  /** Khối hành chính của BN đang chọn.
   *
   * Lấy từ CHÍNH hồ sơ, không đi ké lượt hẹn: hồ sơ chưa khám lần nào thì
   * không có lượt hẹn nào để ké, mà khối hành chính thì vẫn phải hiện.
   */
  const hc = selected?.hoso;

  const firstCount = rows.filter((row) => row.phan_loai === "Khám lần đầu").length;
  const returnCount = rows.filter((row) => row.phan_loai === "Tái khám").length;
  const noneCount = rows.filter((row) => row.phan_loai === "Chưa khám").length;
  const filters: { key: Filter; label: string }[] = [
    { key: "all", label: `Tất cả (${rows.length})` },
    { key: "first", label: `${nhanPhanLoaiKham("Khám lần đầu")} (${firstCount})` },
    { key: "return", label: `${nhanPhanLoaiKham("Tái khám")} (${returnCount})` },
    { key: "none", label: `Chưa khám (${noneCount})` },
  ];

  const directory = (
    <section
      aria-label="Danh sách bệnh nhân"
      className="min-w-0 overflow-hidden rounded-card border border-line bg-surface shadow-card"
    >
      <div className="border-b border-line px-4 py-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="flex items-center gap-2 text-sm font-semibold text-ink">
              <UsersRound size={16} className="text-brand-600" /> Danh sách bệnh nhân
            </p>
            <p className="mt-1 text-xs text-ink-muted">Tra cứu hồ sơ và lượt khám gần nhất</p>
          </div>
          <span className="rounded-chip bg-brand-50 px-2 py-1 text-xs font-semibold text-brand-800">
            {shown.length}
          </span>
        </div>
        <label className="relative mt-4 block">
          <Search
            size={16}
            aria-hidden="true"
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-faint"
          />
          <input
            value={term}
            onChange={(event) => setTerm(event.target.value)}
            placeholder="Tìm tên, mã BN hoặc SĐT"
            className="h-10 w-full rounded-control border border-line bg-white pl-9 pr-3 text-sm text-ink outline-none transition focus:border-brand-600 focus:ring-2 focus:ring-brand-600/15"
          />
        </label>
        <div className="mt-3 flex flex-wrap gap-1.5" aria-label="Lọc danh sách bệnh nhân">
          {filters.map((item) => (
            <button
              key={item.key}
              type="button"
              onClick={() => setFilter(item.key)}
              aria-pressed={filter === item.key}
              className={
                "rounded-chip px-2.5 py-1.5 text-xs font-semibold transition-colors " +
                (filter === item.key
                  ? "bg-brand-600 text-white"
                  : "bg-surface-muted text-ink-soft hover:bg-brand-50 hover:text-brand-800")
              }
            >
              {item.label}
            </button>
          ))}
          <span className="ml-auto inline-flex items-center gap-1 px-1 text-label text-ink-faint">
            <SlidersHorizontal size={12} /> Lọc cục bộ
          </span>
        </div>
      </div>

      <ul className="max-h-[62vh] divide-y divide-line overflow-y-auto" aria-label="Kết quả tìm bệnh nhân">
        {shown.length === 0 ? (
          <li className="px-5 py-12 text-center text-sm text-ink-muted">
            Không tìm thấy bệnh nhân phù hợp.
          </li>
        ) : (
          shown.map((row) => {
            const active = selected?.clinic_patient_id === row.clinic_patient_id;
            return (
              <li key={row.clinic_patient_id}>
                <button
                  type="button"
                  onClick={() => setSelectedId(row.clinic_patient_id)}
                  aria-pressed={active}
                  className={
                    "flex w-full items-start gap-3 px-4 py-3.5 text-left transition-colors " +
                    (active
                      ? "border-l-3 border-brand-600 bg-surface-selected pl-[13px]"
                      : "border-l-3 border-transparent hover:bg-surface-muted")
                  }
                >
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand-100 text-xs font-bold text-brand-800">
                    {initials(row.full_name)}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="flex items-start justify-between gap-2">
                      <span className="truncate text-sm font-semibold text-ink">{row.full_name}</span>
                      <PatientKind value={row.phan_loai} />
                    </span>
                    <span className="mt-1 block truncate font-mono text-label text-ink-muted">
                      {row.patient_code}
                    </span>
                    <span className="mt-1 flex items-center justify-between gap-2 text-label text-ink-muted">
                      <span className="truncate">{row.phone_primary ?? "Chưa có SĐT"}</span>
                      <span className="shrink-0 tabular-nums">
                        {row.latest
                          ? `${row.visit_count} lượt · ${fmtDate(row.latest)}`
                          : "0 lượt"}
                      </span>
                    </span>
                  </span>
                </button>
              </li>
            );
          })
        )}
      </ul>
      <div className="border-t border-line px-4 py-3 text-xs text-ink-muted">
        Hiển thị {shown.length} trên {rows.length} hồ sơ
      </div>
    </section>
  );

  const overview = (
    <section
      aria-label="Tổng quan hồ sơ"
      className="min-w-0 overflow-hidden rounded-card border border-line bg-surface shadow-card"
    >
      {selected ? (
        <>
          <header className="border-b border-line px-5 py-4">
            <div className="flex items-start justify-between gap-3">
              <div className="flex min-w-0 items-center gap-3">
                <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-brand-100 text-sm font-bold text-brand-800">
                  {initials(selected.full_name)}
                </span>
                <div className="min-w-0">
                  <h2 className="truncate text-lg font-semibold text-ink">{selected.full_name}</h2>
                  <p className="mt-0.5 truncate font-mono text-xs text-ink-muted">{selected.patient_code}</p>
                </div>
              </div>
              <PatientKind value={selected.phan_loai} />
            </div>
            <div className="mt-4 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-muted">
              <span>{selected.date_of_birth ? `Ngày sinh ${selected.date_of_birth}` : "Chưa có ngày sinh"}</span>
              <span>{selected.gender ?? "Chưa có giới tính"}</span>
              <span>{selected.visit_count} lượt khám</span>
            </div>
          </header>

          {/* HỒ SƠ HÀNH CHÍNH ĐẦY ĐỦ, hiện ngay tại chỗ.
              
              Trước đây chỗ này chỉ có số điện thoại và một dòng "Địa chỉ xem
              trong hồ sơ", còn muốn xem thật thì phải bấm sang màn khác — trong
              khi TOÀN BỘ khối hành chính đã được tải về cùng lượt hẹn từ đầu.
              Bắt Lễ tân đổi màn để đọc một thứ đã nằm sẵn trong bộ nhớ là bắt
              họ trả giá cho một khoảng trống không có thật. */}
          <div className="grid gap-3 p-5 sm:grid-cols-2">
            <article className="rounded-control border border-line bg-surface-muted p-3.5">
              <p className="flex items-center gap-2 text-xs font-semibold text-ink-soft">
                <UserRound size={14} className="text-brand-600" /> Hành chính
              </p>
              <dl className="mt-2 space-y-1 text-sm">
                <HangHanhChinh nhan="Ngày sinh" giaTri={hc?.date_of_birth} />
                <HangHanhChinh nhan="Giới tính" giaTri={hc?.gender} />
                <HangHanhChinh nhan="Dân tộc" giaTri={hc?.ethnicity} />
                <HangHanhChinh nhan="Quốc tịch" giaTri={hc?.nationality} />
                <HangHanhChinh nhan="Nghề nghiệp" giaTri={hc?.occupation} />
                <HangHanhChinh nhan="Đối tượng" giaTri={hc?.patient_objection} />
                <HangHanhChinh nhan="Người giám hộ" giaTri={hc?.guardian_name} />
              </dl>
            </article>
            <article className="rounded-control border border-line bg-surface-muted p-3.5">
              <p className="flex items-center gap-2 text-xs font-semibold text-ink-soft">
                <Phone size={14} className="text-brand-600" /> Liên hệ & địa chỉ
              </p>
              <dl className="mt-2 space-y-1 text-sm">
                <HangHanhChinh nhan="Điện thoại" giaTri={hc?.phone_primary ?? selected.phone_primary} />
                {(hc?.patient_sdt_them ?? [])
                  .filter((t) => t.loai === "CHINH")
                  .map((t) => (
                    <HangHanhChinh key={t.so_dien_thoai} nhan="Điện thoại (thêm)" giaTri={t.so_dien_thoai} />
                  ))}
                <HangHanhChinh nhan="Điện thoại phụ" giaTri={hc?.phone_secondary} />
                {(hc?.patient_sdt_them ?? [])
                  .filter((t) => t.loai === "NGUOI_NHA")
                  .map((t) => (
                    <HangHanhChinh key={t.so_dien_thoai} nhan="Người nhà (thêm)" giaTri={t.so_dien_thoai} />
                  ))}
                <HangHanhChinh nhan="Địa chỉ" giaTri={hc?.address} />
              </dl>
              <p className="mt-3 border-t border-line pt-2 text-xs text-ink-muted">
                <ClipboardList size={13} className="mr-1 inline text-brand-600" />
                {selected.latest
                  ? `Lần gần nhất: ${fmtDateTimeOrDate(selected.latest)} · ${selected.visit_count} lượt`
                  : "Chưa khám lần nào"}
              </p>
            </article>
          </div>
          {selected.appt ? (
            <section className="border-t border-line px-5 py-4">
              <div className="flex items-center justify-between gap-2">
                <h3 className="text-sm font-semibold text-ink">Lượt khám gần nhất</h3>
                <AppointmentStatus status={selected.appt.status} />
              </div>
              <div className="mt-3 grid gap-2 rounded-control border border-line p-3.5 text-sm sm:grid-cols-2">
                <p><span className="text-ink-muted">Thời gian:</span> {fmtDateTimeOrDate(selected.appt.slot_start)}</p>
                <p><span className="text-ink-muted">Dịch vụ:</span> {selected.appt.service?.name ?? "Chưa có dữ liệu"}</p>
                <p><span className="text-ink-muted">Số thứ tự:</span> {selected.appt.queue_number ?? "Chưa được cấp"}</p>
                <p><span className="text-ink-muted">Kênh:</span> {selected.appt.booking_channel ?? "Chưa ghi nhận"}</p>
              </div>
            </section>
          ) : (
            <section className="border-t border-line px-5 py-4">
              <p className="rounded-control bg-surface-muted px-3 py-2 text-sm text-ink-muted">
                Hồ sơ này chưa có lượt khám nào. Đặt lịch hoặc tiếp nhận trực
                tiếp thì lượt đầu tiên sẽ hiện ở đây.
              </p>
            </section>
          )}


          {/* Nút mở phiếu khám CHỈ cho vai lâm sàng.
              
              Với Lễ tân (`enablePopup` = false) nút này trước đây là một liên
              kết sang /patients/[id] — tức là bấm để đọc đúng khối hành chính
              vừa hiện đầy đủ ngay bên trên. Bỏ đi.
              
              Nhưng với bác sĩ và TKYK thì đây là cửa DUY NHẤT vào phiếu khám,
              nên nó ở lại. Bỏ luôn cho mọi vai là lặng lẽ lấy mất một việc mà
              không ai yêu cầu. */}
          {enablePopup && selected.appt ? (
            <div className="border-t border-line px-5 py-4">
              <button
                type="button"
                onClick={() => setOpenAppt(selected.appt)}
                className="inline-flex min-h-10 w-full items-center justify-center gap-2 rounded-control border border-brand-600 bg-white px-4 py-2 text-sm font-semibold text-brand-700 transition hover:bg-brand-50 sm:w-auto"
              >
                <FileText size={16} /> Mở phiếu khám
              </button>
            </div>
          ) : null}
        </>
      ) : (
        <div className="flex min-h-[360px] flex-col items-center justify-center px-5 text-center">
          <UserRound size={32} className="text-ink-faint" />
          <p className="mt-3 text-sm font-medium text-ink">Chưa chọn bệnh nhân</p>
          <p className="mt-1 text-xs text-ink-muted">Chọn một hồ sơ ở cột danh sách để xem thông tin.</p>
        </div>
      )}
    </section>
  );

  const visitPanel = (
    <aside
      aria-label="Lượt khám gần nhất"
      className="min-w-0 overflow-hidden rounded-card border border-line bg-surface shadow-card"
    >
      <header className="flex items-start justify-between gap-2 border-b border-line px-4 py-4">
        <div className="min-w-0">
          <p className="flex items-center gap-2 text-sm font-semibold text-ink">
            <Stethoscope size={16} className="text-brand-600" /> Thông tin lượt khám
          </p>
          <p className="mt-1 text-xs text-ink-muted">Chỉ hiển thị dữ liệu đã có từ lịch hẹn</p>
        </div>
        {selected ? (
          <button
            type="button"
            onClick={() => setMoDanhSachLuot((v) => !v)}
            aria-expanded={moDanhSachLuot}
            className={`shrink-0 rounded-control border px-2.5 py-1.5 text-xs font-medium transition-colors ${
              moDanhSachLuot
                ? "border-brand-600 bg-brand-50 text-brand-700"
                : "border-line text-ink-soft hover:bg-surface-sunken"
            }`}
          >
            Các lượt khám ({selected.visit_count})
          </button>
        ) : null}
      </header>
      {selected ? (
        <div className="divide-y divide-line px-4">
          {/* Hồ sơ chưa khám lần nào thì ba dòng này không có gì để nói —
              in "Chưa có dữ liệu" ba lần là nhiễu, nên bỏ hẳn. */}
          {selected.appt ? (
            <>
              <DetailLine icon={<CalendarDays size={15} />} label="Thời gian hẹn" value={fmtDateTimeOrDate(selected.appt.slot_start)} />
              <DetailLine icon={<Stethoscope size={15} />} label="Dịch vụ" value={selected.appt.service?.name ?? "Chưa có dữ liệu dịch vụ"} />
            </>
          ) : null}
          <DetailLine icon={<UsersRound size={15} />} label="Loại hồ sơ" value={selected.phan_loai} />
          {selected.appt ? (
            <DetailLine icon={<ArrowRight size={15} />} label="Trạng thái lịch" value={<AppointmentStatus status={selected.appt.status} />} />
          ) : null}
          {/* Danh sách CÁC LƯỢT KHÁM, mở ra tại chỗ.
              
              Bỏ nút "Xem thông tin hành chính": khối hành chính nay hiện đầy đủ
              ở panel giữa, nên nút đó dẫn sang một màn khác để xem đúng thứ vừa
              đọc xong. */}
          {moDanhSachLuot ? (
            <ul className="space-y-1.5 py-3">
              {selected.visits.map((v, i) => (
                <li
                  key={v.id}
                  className="rounded-control border border-line px-3 py-2 text-xs"
                >
                  <span className="flex items-center justify-between gap-2">
                    <span className="font-medium text-ink">
                      Lần {selected.visits.length - i}
                    </span>
                    <AppointmentStatus status={v.status} />
                  </span>
                  <span className="mt-1 block text-ink-muted">
                    {fmtDateTimeOrDate(v.slot_start)}
                    {v.service_name ? ` · ${v.service_name}` : ""}
                  </span>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : (
        <p className="px-4 py-10 text-center text-sm text-ink-muted">Chưa có lượt khám để hiển thị.</p>
      )}
    </aside>
  );

  if (openAppt) {
    return (
      <>
        <p className="mb-2 text-xs text-ink-muted">Kéo thanh phân cách để đổi độ rộng hai vùng làm việc.</p>
        <SplitPane
          className="md:h-[78vh]"
          initialLeftPct={42}
          left={directory}
          right={
            <ClinicalRecordForm
              key={openAppt.id}
              appt={openAppt}
              staffId={null}
              fill
              readOnly
              canEditAdmin={canEditAdmin}
              showPreVisitBrief={showPreVisitBrief}
              showRebook={showRebook}
              enableVisitPager={enableVisitPager}
              onRebook={() => datLichLai(openAppt)}
              onClose={() => setOpenAppt(null)}
            />
          }
        />
      </>
    );
  }

  return (
    <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(250px,0.82fr)_minmax(380px,1.42fr)_minmax(250px,0.8fr)]">
      {directory}
      {overview}
      {visitPanel}
    </div>
  );
}
