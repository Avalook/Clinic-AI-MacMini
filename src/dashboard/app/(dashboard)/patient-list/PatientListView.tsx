"use client";

// Danh sách bệnh nhân là bề mặt tra cứu: dữ liệu trong ba vùng đều lấy từ cùng
// một dòng lịch hẹn gần nhất. Không dựng sinh hiệu, bệnh sử hay nghĩa vụ giả khi
// API của màn này chưa tải chúng; người có quyền lâm sàng vẫn mở phiếu khám thật.

import { useCallback, useEffect, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowRight,
  ArrowUpDown,
  CalendarDays,
  ClipboardList,
  FileText,
  Phone,
  Search,
  Stethoscope,
  UserRound,
  UsersRound,
} from "lucide-react";
import { fmtDate, fmtDateTimeOrDate } from "../../../lib/datetime";
import ClinicalRecordForm from "../tasks/ClinicalRecordForm";
import type { DoctorApptRow } from "../tasks/DoctorApptRow";
import KenhDoiHuy, { type CoKenhDoiHuy } from "../customers/KenhDoiHuy";
import SplitPane from "../SplitPane";
import LichSuKham from "../_lam-viec/LichSuKham";
import PhieuKhamLuot from "../_lam-viec/phieu-kham/PhieuKhamLuot";
import LichSuNotion from "./LichSuNotion";
import { chuNhanLuot, type NhanLuot } from "../../../lib/nhan-luot";
import { nhanPhanLoaiKham } from "../../../lib/phan-loai-kham";
import { khoangDong } from "../../../lib/so-trang";
import ThanhSoTrang from "../../../components/ui/ThanhSoTrang";

/** Khối hành chính của bệnh nhân — cùng hình dạng với `appt.patient`. */
type PatientFull = NonNullable<DoctorApptRow["patient"]> & {
  /** Các số gắn THÊM — embed từ patient_sdt_them (15/08/2026). */
  patient_sdt_them?: { so_dien_thoai: string; loai: string }[] | null;
} & CoKenhDoiHuy;

/** Một lần khám trong quá khứ — đủ để liệt kê, không kèm dữ liệu lâm sàng. */
export interface VisitSummary {
  id: string;
  slot_start: string;
  status: string;
  service_name: string | null;
  doctor_name?: string | null;
  /** Lượt khám thật của lịch (07/10/2026) — null = chưa check-in. */
  visit_id?: string | null;
  /** v5 | notion | cu | trong — máy chủ quyết khung đọc. */
  loai_du_lieu?: string | null;
  /** Nhãn đếm lượt máy chủ tính ("Lượt khám n" / "Buổi k/N"), 08/10/2026. */
  nhan_luot?: NhanLuot | null;
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
  /** Có lượt CHECKED_IN chưa đóng ở quầy (backend tính, 16/09/2026). */
  dang_mo?: boolean;
  /** Khối hành chính — LUÔN có, kể cả khi chưa khám lần nào. Trước đây nó đi
   *  kèm lượt hẹn, nên hồ sơ chưa khám thì không có gì để hiện. */
  hoso: PatientFull;
  /** Lượt hẹn gần nhất; `null` = chưa khám lần nào. */
  appt: DoctorApptRow | null;
}

/** Tab lọc = giá trị `?loc=` máy chủ hiểu ("" = tất cả). */
type Filter = "" | "lan-dau" | "tai-kham" | "chua-kham";
const CAC_LOC: readonly Filter[] = ["", "lan-dau", "tai-kham", "chua-kham"];

/** Số đếm trên TOÀN BỘ hồ sơ (máy chủ tính) — ô tổng + số ở tab. */
export interface TongDanhSach {
  ho_so: number;
  dang_mo: number;
  lan_dau: number;
  tai_kham: number;
  chua_kham: number;
}

/** Chiều xếp (Tuyền 29/09/2026): máy chủ xếp hoạt động GẦN NHẤT trước;
 *  "Xa nhất trước" đảo trên TOÀN BỘ danh sách (`?sap=xa`, 06/10/2026 — trước
 *  đó chỉ đảo các dòng đã tải). Lựa chọn vẫn được nhớ trên máy người dùng —
 *  tiện ích, không phải dữ liệu: mở màn không có `?sap` mà máy nhớ "xa" thì
 *  tự chuyển sang `?sap=xa`. */
type ChieuXep = "gan" | "xa";
const KHOA_CHIEU_XEP = "clinicai.ds-benh-nhan.chieu-xep";

/** Gõ xong bao lâu mới tìm (ms) — đủ để không gửi một yêu cầu mỗi phím. */
const CHO_GO = 350;

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
  chonRow = null,
  tong,
  phanTrang,
  boLoc,
  enablePopup = false,
  canEditAdmin = false,
  showRebook = false,
  enableVisitPager = false,
  canBook = false,
  chonSan = null,
}: {
  /** MỘT trang hồ sơ máy chủ đã tìm + lọc + xếp (06/10/2026). */
  rows: ExaminedRow[];
  /** Khách `?chon=` khi không nằm trong trang này (mở từ link, hoặc chọn rồi
   *  chuyển trang) — để hồ sơ đang mở không biến mất theo trang. */
  chonRow?: ExaminedRow | null;
  /** Số đếm TOÀN BỘ hồ sơ — nhãn tab. */
  tong: TongDanhSach;
  phanTrang: { trang: number; soTrang: number; soKhop: number; motTrang: number };
  /** Giá trị đang có trên URL (`null` = không có). */
  boLoc: { q: string | null; loc: string | null; sap: string | null };
  /** Chỉ vai lâm sàng mở phiếu khám thật ở vùng SplitPane. */
  enablePopup?: boolean;
  canEditAdmin?: boolean;
  showRebook?: boolean;
  enableVisitPager?: boolean;
  /** Vai đặt lịch được: hiện nút "Đặt lịch mới" ở đầu hồ sơ. */
  canBook?: boolean;
  /** `?chon=<clinic_patient_id>` — mở sẵn hồ sơ khách (link từ Quản lý khách
   *  hàng, phiếu khám; thay trang /patients/[id] đã gộp 27/09/2026). */
  chonSan?: string | null;
}) {
  const router = useRouter();
  const [dangTai, batDauTai] = useTransition();
  const filter: Filter = CAC_LOC.includes(boLoc.loc as Filter) ? (boLoc.loc as Filter) : "";
  const chieuXep: ChieuXep = boLoc.sap === "xa" ? "xa" : "gan";
  const qUrl = boLoc.q ?? "";

  /** Đổi tham số trên URL rồi để máy chủ dựng lại trang. Đọc URL HIỆN TẠI
   *  (không theo prop) để giữ `?chon=` vừa ghi bằng `history.replaceState`. */
  const di = useCallback(
    (doi: Record<string, string | null>) => {
      const ts = new URLSearchParams(window.location.search);
      for (const [k, v] of Object.entries(doi)) {
        if (v) ts.set(k, v);
        else ts.delete(k);
      }
      const chuoi = ts.toString();
      batDauTai(() => {
        router.replace(`/patient-list${chuoi ? `?${chuoi}` : ""}`, { scroll: false });
      });
    },
    [router],
  );

  // Ô TÌM: gõ tại chỗ, nghỉ CHO_GO ms mới gửi `?q=` (về trang 1). `daGui` nhớ
  // chuỗi vừa gửi: khi máy chủ trả về đúng chuỗi ấy thì KHÔNG ghi đè ô (người
  // dùng có thể đã gõ thêm); URL đổi vì lý do khác (nút Lùi) thì ô theo URL.
  const [term, setTerm] = useState(qUrl);
  const [daGui, setDaGui] = useState(qUrl);
  const [qDaThay, setQDaThay] = useState(qUrl);
  if (qUrl !== qDaThay) {
    setQDaThay(qUrl);
    if (qUrl !== daGui) {
      setTerm(qUrl);
      setDaGui(qUrl);
    }
  }
  useEffect(() => {
    const t = term.trim();
    if (t === daGui.trim()) return;
    const hen = setTimeout(() => {
      setDaGui(t);
      di({ q: t || null, trang: null });
    }, CHO_GO);
    return () => clearTimeout(hen);
  }, [term, daGui, di]);

  // Máy nhớ "xa" mà URL chưa nói gì → chuyển sang `?sap=xa` một lần.
  useEffect(() => {
    if (boLoc.sap !== null) return;
    try {
      if (localStorage.getItem(KHOA_CHIEU_XEP) === "xa") di({ sap: "xa", trang: null });
    } catch {
      /* trình duyệt chặn bộ nhớ — giữ mặc định */
    }
  }, [boLoc.sap, di]);
  const doiChieuXep = () => {
    const moi: ChieuXep = chieuXep === "gan" ? "xa" : "gan";
    try {
      localStorage.setItem(KHOA_CHIEU_XEP, moi);
    } catch {
      /* không nhớ được thì thôi */
    }
    di({ sap: moi === "xa" ? "xa" : null, trang: null });
  };
  // MỞ MÀN LÀ BẢNG TRA CỨU, chưa chọn ai (Tuyền 16/09/2026: *"lấy giống của
  // cskh cái danh sách khách hàng sang là được, để tra cứu thôi mà"*). Trước
  // đó màn này tự chọn hồ sơ ĐẦU DANH SÁCH rồi mở luôn ba vùng — người vào tra
  // cứu một cái tên lại phải đọc hồ sơ của một người mình không hỏi.
  const [selectedId, setSelectedId] = useState<string | null>(chonSan);
  const [openAppt, setOpenAppt] = useState<DoctorApptRow | null>(null);
  const [moDanhSachLuot, setMoDanhSachLuot] = useState(false);
  /** Lượt có phiếu v5 đang mở ở vùng phải (hồ sơ kiểu Bàn khám, chỉ xem). */
  const [openV5, setOpenV5] = useState<VisitSummary | null>(null);

  /** Chọn / bỏ chọn một khách. Ghi `?chon=` lên URL KHÔNG dựng lại trang
   *  (`history.replaceState` — Next đồng bộ nó với router): F5 vẫn mở đúng
   *  khách, và sang trang khác thì máy chủ trả kèm khách ấy (`chonRow`). */
  const chonKhach = (id: string | null) => {
    setSelectedId(id);
    const ts = new URLSearchParams(window.location.search);
    if (id) ts.set("chon", id);
    else ts.delete("chon");
    const chuoi = ts.toString();
    window.history.replaceState(null, "", `/patient-list${chuoi ? `?${chuoi}` : ""}`);
  };
  /** Đổi ô tìm / tab: như bản lọc tại chỗ cũ, khách không còn khớp thì cột hồ
   *  sơ đóng lại — nên bỏ `?chon=` để máy chủ không trả kèm. */
  const doiLoc = (loc: Filter) => di({ loc: loc || null, trang: null, chon: null });
  const doiTrang = (so: number) => di({ trang: so > 1 ? String(so) : null });

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

  // MỞ MỘT LƯỢT (07/10/2026, T8): máy chủ nói lượt có loại dữ liệu gì — phiếu
  // v5 → hồ sơ kiểu Bàn khám (chỉ xem); đời cũ / Notion / chưa phiếu → khung
  // đọc cũ (`ClinicalRecordForm`, giữ nguyên). Chỉ đổi hiển thị, không ghi gì.
  function moLuot(v: VisitSummary) {
    if (v.loai_du_lieu === "v5" && v.visit_id) {
      setOpenAppt(null);
      setOpenV5(v);
      return;
    }
    if (!selected?.appt) return;
    setOpenV5(null);
    setOpenAppt({
      ...selected.appt,
      id: v.id,
      slot_start: v.slot_start,
      status: v.status,
      service: v.service_name ? { name: v.service_name } : null,
    } as DoctorApptRow);
  }

  // Danh sách = đúng trang máy chủ trả (đã tìm, lọc, xếp). Khách đang chọn
  // lấy từ trang này, hoặc từ `chonRow` khi khách nằm ở trang khác.
  const selected = selectedId
    ? (rows.find((item) => item.clinic_patient_id === selectedId) ??
      (chonRow?.clinic_patient_id === selectedId ? chonRow : null))
    : null;
  /** Khối hành chính của BN đang chọn.
   *
   * Lấy từ CHÍNH hồ sơ, không đi ké lượt hẹn: hồ sơ chưa khám lần nào thì
   * không có lượt hẹn nào để ké, mà khối hành chính thì vẫn phải hiện.
   */
  const hc = selected?.hoso;

  // Số ở tab đếm trên TOÀN BỘ hồ sơ (máy chủ), không theo trang đang xem.
  const filters: { key: Filter; label: string }[] = [
    { key: "", label: `Tất cả (${tong.ho_so})` },
    { key: "lan-dau", label: `${nhanPhanLoaiKham("Khám lần đầu")} (${tong.lan_dau})` },
    { key: "tai-kham", label: `${nhanPhanLoaiKham("Tái khám")} (${tong.tai_kham})` },
    { key: "chua-kham", label: `Chưa khám (${tong.chua_kham})` },
  ];
  const { tu, den } = khoangDong(phanTrang.trang, phanTrang.motTrang, rows.length);
  const dongHienThi =
    phanTrang.soKhop === 0
      ? "Không có hồ sơ phù hợp"
      : `Hiển thị ${tu}–${den} trên ${phanTrang.soKhop} hồ sơ`;

  // Một nút đảo chiều, dùng ở cả bảng tra cứu lẫn danh sách bên cạnh hồ sơ.
  const nutChieuXep = (
    <button
      type="button"
      onClick={doiChieuXep}
      aria-label={`Đang xếp: ${chieuXep === "gan" ? "gần nhất trước" : "xa nhất trước"} — bấm để đảo`}
      className="inline-flex items-center gap-1 rounded-chip bg-surface-muted px-2.5 py-1.5 text-xs font-semibold text-ink-soft transition-colors hover:bg-brand-50 hover:text-brand-800"
    >
      <ArrowUpDown size={12} aria-hidden="true" />
      {chieuXep === "gan" ? "Gần nhất trước" : "Xa nhất trước"}
    </button>
  );

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
            {/* ĐƯỜNG VỀ BẢNG. Bấm một dòng là vào ba vùng; không có nút này thì
                muốn tra người khác phải tải lại trang. */}
            <button
              type="button"
              onClick={() => chonKhach(null)}
              className="mt-1 text-xs font-semibold text-brand-700 hover:underline"
            >
              ← Về danh sách
            </button>
          </div>
          <span className="rounded-chip bg-brand-50 px-2 py-1 text-xs font-semibold tabular-nums text-brand-800">
            {phanTrang.soKhop}
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
            aria-label="Tìm tên, mã BN hoặc SĐT"
            className="h-10 w-full rounded-control border border-line bg-white pl-9 pr-3 text-sm text-ink outline-none transition focus:border-brand-600 focus:ring-2 focus:ring-brand-600/15"
          />
        </label>
        <div className="mt-3 flex flex-wrap gap-1.5" aria-label="Lọc danh sách bệnh nhân">
          {filters.map((item) => (
            <button
              key={item.key}
              type="button"
              onClick={() => doiLoc(item.key)}
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
          {nutChieuXep}
        </div>
      </div>

      <ul
        className={`max-h-[62vh] divide-y divide-line overflow-y-auto transition-opacity ${dangTai ? "opacity-60" : ""}`}
        aria-label="Kết quả tìm bệnh nhân"
        aria-busy={dangTai}
      >
        {rows.length === 0 ? (
          <li className="px-5 py-12 text-center text-sm text-ink-muted">
            Không tìm thấy bệnh nhân phù hợp.
          </li>
        ) : (
          rows.map((row) => {
            const active = selected?.clinic_patient_id === row.clinic_patient_id;
            return (
              <li key={row.clinic_patient_id}>
                <button
                  type="button"
                  onClick={() => chonKhach(row.clinic_patient_id)}
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
                    <KenhDoiHuy k={row.hoso} gon />
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
      <div className="space-y-2 border-t border-line px-4 py-3">
        <p className="text-xs tabular-nums text-ink-muted">{dongHienThi}</p>
        <ThanhSoTrang
          trang={phanTrang.trang}
          soTrang={phanTrang.soTrang}
          onChon={doiTrang}
          nhan="Chuyển trang danh sách bệnh nhân"
          hep
          dangTai={dangTai}
        />
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
                  <KenhDoiHuy k={selected.hoso} />
                </div>
              </div>
              <PatientKind value={selected.phan_loai} />
            </div>
            {/* THAO TÁC NHANH ở đầu hồ sơ (ảnh Tuyền 16/09/2026). Chỉ những việc
                có đường thật: đặt lịch (màn Đặt lịch mang mã khách), gọi, và
                trang hồ sơ đầy đủ. */}
            <div className="mt-3 flex flex-wrap gap-2">
              {canBook && (
                <Link
                  href={`/appointments?bn=${encodeURIComponent(selected.patient_code)}`}
                  className="inline-flex h-8 items-center gap-1.5 rounded-control bg-brand-600 px-3 text-body font-semibold text-white hover:bg-brand-700"
                >
                  <CalendarDays size={14} /> Đặt lịch mới
                </Link>
              )}
              {selected.phone_primary && (
                <a
                  href={`tel:${selected.phone_primary}`}
                  className="inline-flex h-8 items-center gap-1.5 rounded-control bg-surface px-3 text-body font-medium text-ink ring-1 ring-inset ring-line-strong hover:bg-surface-muted"
                >
                  <Phone size={14} /> Gọi
                </a>
              )}
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


          {/* LỊCH SỬ CÁC LƯỢT KHÁM — bảng ngay trong hồ sơ (ảnh Tuyền 16/09/2026),
              thay vì phải bấm mở danh sách ở cột phải. Lượt = khách đã tới. */}
          {selected.visits.length > 0 && (
            <section className="border-t border-line px-5 py-4">
              <h3 className="text-sm font-semibold text-ink">
                Lịch sử các lượt khám ({selected.visits.length})
              </h3>
              <div className="mt-2 overflow-x-auto">
                <table className="w-full border-collapse text-body">
                  <thead>
                    <tr className="text-left text-label font-semibold uppercase tracking-wide text-ink-muted">
                      <th className="border-b border-hairline py-1.5 pr-2">#</th>
                      <th className="border-b border-hairline py-1.5 pr-2">Ngày khám</th>
                      <th className="border-b border-hairline py-1.5 pr-2">Dịch vụ</th>
                      <th className="border-b border-hairline py-1.5 pr-2">Bác sĩ</th>
                      <th className="border-b border-hairline py-1.5">Trạng thái</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selected.visits.map((v, i) => (
                      <tr key={v.id}>
                        <td className="border-b border-hairline py-1.5 pr-2 tabular-nums text-ink-muted">
                          {selected.visits.length - i}
                        </td>
                        <td className="border-b border-hairline py-1.5 pr-2 tabular-nums">
                          {fmtDateTimeOrDate(v.slot_start)}
                        </td>
                        <td className="border-b border-hairline py-1.5 pr-2">
                          {v.service_name ?? <span className="text-ink-faint">—</span>}
                        </td>
                        <td className="border-b border-hairline py-1.5 pr-2">
                          {v.doctor_name ?? <span className="text-ink-faint">Chưa phân</span>}
                        </td>
                        <td className="border-b border-hairline py-1.5">
                          <AppointmentStatus status={v.status} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          {/* LỊCH SỬ KHÁM CŨ TỪ NOTION (05/10/2026) — chỉ đọc; khách không có
              lịch sử Notion thì khối tự ẩn. */}
          <LichSuNotion key={selected.clinic_patient_id} clinicPatientId={selected.clinic_patient_id} />

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
                onClick={() =>
                  selected.visits[0] ? moLuot(selected.visits[0]) : setOpenAppt(selected.appt)
                }
                className="inline-flex min-h-10 w-full items-center justify-center gap-2 rounded-control border border-brand-600 bg-white px-4 py-2 text-sm font-semibold text-brand-700 transition hover:bg-brand-50 sm:w-auto"
              >
                <FileText size={16} /> Mở phiếu khám
              </button>
              <div className="mt-2">
                <LichSuKham
                  clinicPatientId={selected.clinic_patient_id}
                  onChonLuot={(l) => {
                    const v = selected.visits.find((x) => x.visit_id === l.visit_id);
                    if (!v) return false;
                    moLuot(v);
                    return true;
                  }}
                />
              </div>
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
              {selected.visits.map((v) => (
                <li key={v.id}>
                  <button
                    type="button"
                    disabled={!enablePopup}
                    onClick={() => moLuot(v)}
                    className="block w-full rounded-control border border-line px-3 py-2 text-left text-xs hover:bg-surface-muted disabled:cursor-default disabled:hover:bg-transparent"
                  >
                  <span className="flex items-center justify-between gap-2">
                    <span className="font-medium text-ink">
                      {chuNhanLuot(v.nhan_luot)}
                    </span>
                    <AppointmentStatus status={v.status} />
                  </span>
                  <span className="mt-1 block text-ink-muted">
                    {fmtDateTimeOrDate(v.slot_start)}
                    {v.service_name ? ` · ${v.service_name}` : ""}
                  </span>
                  </button>
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

  if (openV5?.visit_id && selected) {
    return (
      <>
        <p className="mb-2 text-xs text-ink-muted">Kéo thanh phân cách để đổi độ rộng hai vùng làm việc.</p>
        <SplitPane
          className="md:h-[78vh]"
          initialLeftPct={42}
          left={directory}
          right={
            <section
              aria-label="Hồ sơ khám lượt"
              className="min-w-0 space-y-3 overflow-y-auto rounded-card border border-line bg-surface p-3 md:h-full"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm font-semibold text-ink">
                  Hồ sơ khám · {fmtDateTimeOrDate(openV5.slot_start)}
                  {openV5.service_name ? ` · ${openV5.service_name}` : ""} — chỉ xem
                </p>
                <button
                  type="button"
                  onClick={() => setOpenV5(null)}
                  className="rounded-control border border-line px-3 py-1.5 text-xs font-medium text-ink-soft hover:bg-surface-sunken"
                >
                  Đóng
                </button>
              </div>
              <PhieuKhamLuot
                key={openV5.visit_id}
                visitId={openV5.visit_id}
                clinicPatientId={selected.clinic_patient_id}
                choGhi={false}
                xemLai
                datChiDinh={async () => ({ ok: false, loi: "Chỉ xem." })}
                onDaDat={() => undefined}
              />
            </section>
          }
        />
      </>
    );
  }

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

  // CHƯA CHỌN AI ⇒ MỘT BẢNG RỘNG, cùng dáng với "Danh sách khách hàng" của
  // CSKH: tra cứu là đọc NHIỀU người một lúc, mà ba vùng hẹp thì mỗi lúc chỉ
  // đọc được một. Bấm một dòng mới mở ba vùng như cũ.
  if (!selected) {
    return (
      <section
        aria-label="Danh sách bệnh nhân"
        className="min-w-0 overflow-hidden rounded-card border border-line bg-surface shadow-card"
      >
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-4 py-3">
          <div>
            <p className="flex items-center gap-2 text-sm font-semibold text-ink">
              <UsersRound size={16} className="text-brand-600" /> Danh sách bệnh nhân
            </p>
            <p className="mt-0.5 text-xs text-ink-muted">
              <span className="tabular-nums">{phanTrang.soKhop}</span> hồ sơ · bấm một dòng để xem chi tiết
              {dangTai ? <span className="ml-2 text-ink-faint">Đang tải…</span> : null}
            </p>
          </div>
          <label className="relative w-full md:w-auto md:min-w-60 md:max-w-80 md:flex-1">
            <Search
              size={16}
              aria-hidden="true"
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-faint"
            />
            <input
              value={term}
              onChange={(event) => setTerm(event.target.value)}
              placeholder="Tìm tên, mã BN hoặc SĐT"
              aria-label="Tìm tên, mã BN hoặc SĐT"
              className="h-10 w-full rounded-control border border-line bg-white pl-9 pr-3 text-sm text-ink outline-none transition focus:border-brand-600 focus:ring-2 focus:ring-brand-600/15"
            />
          </label>
        </div>
        <div className="flex flex-wrap gap-1.5 border-b border-line px-4 py-2">
          {filters.map((item) => (
            <button
              key={item.key}
              type="button"
              onClick={() => doiLoc(item.key)}
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
          <span className="ml-auto">{nutChieuXep}</span>
        </div>
        {/* Từ 768px là bảng 6 cột (cuộn ngang nếu hẹp quá); dưới đó mỗi dòng
            xếp dọc nên KHÔNG đặt bề rộng tối thiểu — 375px không cuộn ngang. */}
        <div
          className={`overflow-x-auto transition-opacity ${dangTai ? "opacity-60" : ""}`}
          aria-busy={dangTai}
        >
          <div className="md:min-w-180">
            <div className="hidden gap-2 border-b border-hairline bg-surface-muted px-4 py-2 text-label font-semibold uppercase tracking-wide text-ink-muted md:grid md:grid-cols-[1.5fr_1fr_0.8fr_0.5fr_0.8fr_1fr]">
              <span>Khách hàng</span>
              <span>Số điện thoại</span>
              <span>Mới / cũ</span>
              <span>Số lượt</span>
              <span>Lần gần nhất</span>
              <span>Bác sĩ gần nhất</span>
            </div>
            {rows.length === 0 ? (
              <p className="px-4 py-12 text-center text-sm text-ink-muted">
                Không tìm thấy bệnh nhân phù hợp.
              </p>
            ) : (
              <div className="divide-y divide-hairline">
                {rows.map((row) => (
                  <button
                    key={row.clinic_patient_id}
                    type="button"
                    onClick={() => chonKhach(row.clinic_patient_id)}
                    className="flex w-full flex-col gap-2 px-4 py-3 text-left transition-colors hover:bg-surface-sunken md:grid md:items-center md:gap-2 md:grid-cols-[1.5fr_1fr_0.8fr_0.5fr_0.8fr_1fr]"
                  >
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-bold text-ink">
                        {row.full_name}
                      </span>
                      <span className="mt-0.5 block truncate font-mono text-xs text-ink-muted">
                        {row.patient_code}
                      </span>
                      <KenhDoiHuy k={row.hoso} gon />
                    </span>
                    <span className="truncate text-xs text-ink-soft">
                      {row.phone_primary ?? "—"}
                    </span>
                    <span>
                      <PatientKind value={row.phan_loai} />
                    </span>
                    <span className="text-xs tabular-nums text-ink-soft">
                      {row.visit_count}
                    </span>
                    <span className="text-xs tabular-nums text-ink-soft">
                      {row.latest ? fmtDate(row.latest) : "—"}
                    </span>
                    <span className="truncate text-xs text-ink-soft">
                      {row.visits[0]?.doctor_name ?? "—"}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
        <div className="flex flex-col items-center gap-2 border-t border-line px-4 py-3 sm:flex-row sm:justify-between">
          <p className="text-xs tabular-nums text-ink-muted">{dongHienThi}</p>
          <ThanhSoTrang
            trang={phanTrang.trang}
            soTrang={phanTrang.soTrang}
            onChon={doiTrang}
            nhan="Chuyển trang danh sách bệnh nhân"
            dangTai={dangTai}
          />
        </div>
      </section>
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
