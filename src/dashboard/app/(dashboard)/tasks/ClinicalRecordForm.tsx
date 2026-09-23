"use client";

// Hồ sơ lâm sàng (TÓM TẮT KHÁM BỆNH) — panel bên phải board "Công việc của tôi".
//   I Hành chính ← patient · III/IV Tiền sử ← patient_medical_profile ·
//   V Thai ← pregnancy · VI Cận lâm sàng ← lab_result  (đều ĐỒNG BỘ, read-only).
//   Sinh hiệu, II Lý do, V bệnh sử/khám thai, VII Chuẩn đoán, VIII Lời dặn = BÁC SĨ
//   điền → LƯU NHÁP vào visit (IN_PROGRESS) + clinical_record qua /api/clinical-record.
// AN TOÀN: nếu visit đã FINALIZED → khóa (luật cấm sửa). KHÔNG tự chốt hồ sơ.

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { X, Plus, CalendarPlus } from "lucide-react";
import { fmtDate, fmtDateTimeOrDate } from "../../../lib/datetime";
import { toHref } from "../../../lib/url";
import { INPUT, LABEL } from "../form-ui";
import PatientAdminEditor from "../PatientAdminEditor";
import HoSoHoanTatPanel from "./HoSoHoanTatPanel";
import SonoBiometry from "./SonoBiometry";
import TheoDoiThuThuat from "./TheoDoiThuThuat";
import ServiceFormEngine from "./ServiceFormEngine";
import { baoBenhAnDaLuu } from "../../../lib/su-kien-benh-an";
import TepCuaLuotKham from "./TepCuaLuotKham";
import { resolveServiceCode } from "../../../lib/form-schemas";
import {
  docNhap,
  donNhapCu,
  ghiNhap,
  khoaNhap,
  moTaLuc,
  xoaNhap,
} from "../../../lib/luu-nhap";
import { clinicalSyncDecision } from "../../../lib/clinical-sync";
import {
  clinicalCompletionGate,
  type ClinicalCompletionGate,
  type ClinicalCompletionMode,
} from "../../../lib/clinical-completion";
import { SU_KIEN_BANG } from "../../../lib/nhip-lam-moi";
import type { DoctorApptRow } from "./DoctorApptRow";

interface Profile {
  blood_type: string | null;
  allergies: string[] | null;
  chronic_diseases: string[] | null;
  current_medications: string[] | null;
  surgical_history: string[] | null;
  family_history: unknown;
  notes: string | null;
}
interface Pregnancy {
  edd_date: string | null;
  gestational_age_at_registration: number | null;
  is_high_risk: boolean | null;
  high_risk_reason: string | null;
  outcome?: string | null;
}
interface Lab {
  test_name: string;
  result_value: string | null;
  result_numeric: number | null;
  result_unit: string | null;
  flag: string | null;
  external_ref: string | null;
}
interface HistoryItem {
  visit_id: string;
  created_at: string;
  status: string;
  service: string | null;
  doctor: string | null;
  chief_complaint: string;
  assessment: string;
}
interface ApiRx {
  id: string;
  drug_catalog_id: string | null;
  drug_name_raw: string | null;
  quantity: string | null;
  dosage_instructions: string | null;
  caution: string | null;
}
interface Data {
  revision: number;
  prescription_draft: { items: RxRow[]; recorded_by: string } | null;
  profile: Profile | null;
  pregnancy: Pregnancy | null;
  labs: Lab[];
  history: HistoryItem[];
  prescriptions: ApiRx[];
  visit: { visit_id: string; status: string } | null;
  draft: {
    chief_complaint: string;
    subjective: unknown;
    objective: unknown;
    assessment: unknown;
    plan: unknown;
  };
}

const EMPTY = {
  ly_do: "", benh_su: "", chan_doan: "", loi_dan: "",
  mach: "", nhiet_do: "", huyet_ap: "", nhip_tho: "", spo2: "",
  can_nang: "", chieu_cao: "", bmi: "", muc_do_dau: "",
  tuoi_thai: "", du_kien_sinh: "", chieu_cao_tc: "", nhip_tim_thai: "",
};
type Fields = typeof EMPTY;

// Sinh hiệu bắt buộc — luật PM (CONTEXT v1.0), sửa 15/09/2026 thay D26 ("3
// trường cho MỌI khách"): 100% đo huyết áp; khách ĐANG CÓ THAI đo thêm cân nặng
// + chiều cao. Luật thật nằm ở API (clinical_record_service.sinh_hieu_tu_ho_so);
// đây chỉ đánh dấu * và nhắc sớm, câu API trả về vẫn hiện nếu lệch.
const VITALS_BAT_BUOC: ReadonlySet<keyof Fields> = new Set(["huyet_ap"]);
const VITALS_BAT_BUOC_CO_THAI: ReadonlySet<keyof Fields> = new Set([
  "huyet_ap",
  "can_nang",
  "chieu_cao",
]);
function vitalsBatBuoc(preg: Pregnancy | null | undefined): ReadonlySet<keyof Fields> {
  return preg && (preg.outcome ?? "ONGOING") === "ONGOING"
    ? VITALS_BAT_BUOC_CO_THAI
    : VITALS_BAT_BUOC;
}

// Tiền sử (III/IV) — bác sĩ sửa, lưu patient_medical_profile.
const EMPTY_PM = {
  allergies: "", blood_type: "", chronic: "", surgical: "",
  medications: "", family: "", notes: "",
};
type PmFields = typeof EMPTY_PM;

// Đơn thuốc (mục IX) — mỗi dòng 1 thuốc. Bác sĩ chọn từ danh mục drug_catalog
// hoặc nhập tay tự do nếu chưa có trong danh mục.
interface RxRow {
  id?: string;
  drug_catalog_id: string | null;
  drug_name: string;
  quantity: string;
  dosage: string;
  caution: string;
}
const EMPTY_RX: RxRow = {
  drug_catalog_id: null,
  drug_name: "",
  quantity: "",
  dosage: "",
  caution: "",
};

// Bốn khối bác sĩ GÕ TAY — đúng và chỉ đúng những thứ mất đi khi trang tải lại.
// Hồ sơ tải từ máy chủ về không nằm ở đây: nó lấy lại được, và để nó trên đĩa
// máy trạm là mở rộng chỗ dữ liệu bệnh nhân nằm mà không mua được gì.
interface GoDo {
  f: Fields;
  pm: PmFields;
  tk: TkFields;
  rx: RxRow[];
}

// Danh mục dùng chung cho picker (đọc runtime từ /api/catalog — KHÔNG hardcode).
interface DrugOpt {
  id: string;
  name_base: string;
  name_raw: string;
  variant: string | null;
  needs_review: boolean;
}

// Mục X — Theo dõi & Tái khám (theo biểu mẫu giấy: "Ngày tái khám + XN cần kiểm
// tra lại"). Lưu vào soap_plan.tai_kham — HỢP ĐỒNG với màn CSKH nhắc tái khám:
//   tai_kham: { ngay: "YYYY-MM-DD", xn: ["HM",…], ghi_chu?: "…" }
// BS không nhập gì → KHÔNG ghi khóa tai_kham (giữ soap_plan sạch).
const TAIKHAM_XN: [code: string, label: string][] = [
  ["HM", "Hormone"],
  ["SH", "Sinh hóa"],
  ["SA", "Siêu âm"],
  ["DXA", "Đo loãng xương"],
  ["PS", "Pap smear"],
];
const EMPTY_TK = { ngay: "", xn: [] as string[], ghi_chu: "" };
type TkFields = typeof EMPTY_TK;
const BLOOD_TYPES = ["", "A", "B", "AB", "O", "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"];

// Gom mọi mục I→X + Sinh hiệu + Phiếu chuyên khoa thành 4 TAB theo luồng khám
// (giảm cuộn). Chỉ render tab đang chọn; state ở global useState nên không mất gì.
const TABS = [
  "Hành chính & Tiền sử", // I Hành chính · III Dị ứng · IV Tiền sử
  "Khám", // Sinh hiệu · II Lý do · V Bệnh sử/khám thai · (Siêu âm)
  "Cận lâm sàng & Chuyên khoa", // VI CLS · Phiếu chuyên khoa
  "Chẩn đoán & Xử trí", // VII Chẩn đoán · VIII Lời dặn · IX Đơn thuốc · X Tái khám
];
// Tokens thanh tab đồng bộ ClinicAI — khớp ServiceFormEngine.
const TAB =
  "shrink-0 whitespace-nowrap rounded-lg px-3 py-1.5 text-sm transition-colors";
const TAB_ON = " bg-brand-100 font-semibold text-brand-800";
const TAB_OFF = " text-ink-soft hover:bg-surface-sunken";
const splitComma = (s: string): string[] =>
  s.split(",").map((x) => x.trim()).filter(Boolean);

const objOf = (x: unknown): Record<string, unknown> =>
  x && typeof x === "object" ? (x as Record<string, unknown>) : {};
const str = (x: unknown): string => (x == null ? "" : String(x));
const arr = (x: string[] | null | undefined) => (x && x.length ? x.join(", ") : "");
const famText = (x: unknown) => (!x ? "" : typeof x === "string" ? x : JSON.stringify(x));

// Tên xét nghiệm nguồn đôi khi kèm link Notion dài "(https://…)" → cắt bỏ cho gọn
// (feedback C6 — link tràn cột, hiển thị lỗi).
const cleanTestName = (s: string): string => {
  const out = (s ?? "").replace(/\s*\(https?:\/\/[^)]*\)?/gi, "").trim();
  return out || (s ?? "");
};

// Huyết áp dạng "tâm thu/tâm trương" (vd 120/80). null = hợp lệ; chuỗi = cảnh báo.
function bloodPressureWarn(v: string): string | null {
  const m = /^\s*(\d{2,3})\s*\/\s*(\d{2,3})\s*$/.exec(v);
  if (!m) return "Định dạng: tâm thu/tâm trương, vd 120/80";
  const s = Number(m[1]);
  const d = Number(m[2]);
  if (s < 60 || s > 260 || d < 30 || d > 160 || d >= s)
    return "Huyết áp bất thường (tâm thu 60–260 > tâm trương 30–160)";
  return null;
}

function readDraft(d: Data["draft"]): Fields {
  const o = objOf(d.objective);
  const v = objOf(o.vitals);
  const k = objOf(o.kham_thai);
  const s = objOf(d.subjective);
  const a = objOf(d.assessment);
  const p = objOf(d.plan);
  return {
    ly_do: str(d.chief_complaint),
    benh_su: str(s.benh_su),
    chan_doan: str(a.chan_doan),
    loi_dan: str(p.loi_dan),
    mach: str(v.mach), nhiet_do: str(v.nhiet_do), huyet_ap: str(v.huyet_ap),
    nhip_tho: str(v.nhip_tho), spo2: str(v.spo2), can_nang: str(v.can_nang),
    chieu_cao: str(v.chieu_cao), bmi: str(v.bmi),
    muc_do_dau: str(v.muc_do_dau),
    tuoi_thai: str(k.tuoi_thai), du_kien_sinh: str(k.du_kien_sinh),
    chieu_cao_tc: str(k.chieu_cao_tc), nhip_tim_thai: str(k.nhip_tim_thai),
  };
}

// Prefill mục X từ plan.tai_kham (nếu hồ sơ nháp đã có); lọc mã XN ngoài danh mục.
function readTaiKham(d: Data["draft"]): TkFields {
  const t = objOf(objOf(d.plan).tai_kham);
  const codes = TAIKHAM_XN.map(([c]) => c);
  const xn = Array.isArray(t.xn)
    ? t.xn.map(String).filter((c) => codes.includes(c))
    : [];
  return { ngay: str(t.ngay), xn, ghi_chu: str(t.ghi_chu) };
}

function AdminRow({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="flex gap-2 text-sm">
      <dt className="w-24 shrink-0 text-ink-muted">{label}</dt>
      <dd className="min-w-0 break-words font-medium text-ink">{value || "—"}</dd>
    </div>
  );
}

function Section({ no, title, synced, editorLabel = "bác sĩ điền", children }: {
  no: string; title: string; synced?: boolean; editorLabel?: string; children: React.ReactNode;
}) {
  return (
    <section className="border-t border-surface-sunken pt-3">
      <h4 className="mb-2 flex flex-wrap items-center gap-2 text-sm font-semibold text-ink">
        <span>{no && <span className="text-brand-600">{no}.</span>} {title}</span>
        <span className={
          "rounded px-1.5 py-0.5 text-label font-medium " +
          (synced ? "bg-success-bg text-success" : "bg-warning-bg text-warning")
        }>
          {synced ? "đồng bộ" : editorLabel}
        </span>
      </h4>
      {children}
    </section>
  );
}

export default function ClinicalRecordForm({
  appt,
  staffId,
  onClose,
  canSign = false,
  vitalsOnly = false,
  fill = false,
  readOnly = false,
  canEditAdmin = false,
  showSono = false,
  showRebook = false,
  onRebook,
  completionMode = "TERMINAL",
  onCompletionGateChange,
}: {
  appt: DoctorApptRow;
  staffId: string | null;
  onClose: () => void;
  /** vitalsOnly = đón-khám (ĐD/Lễ tân/QL): CHỈ sửa Sinh hiệu, mọi mục khác xem. */
  vitalsOnly?: boolean;
  /** Lấp đầy CHIỀU CAO của khung cha (md+) — dùng khi đặt trong SplitPane. */
  fill?: boolean;
  /** readOnly = LỄ TÂN xem hồ sơ trong "Công việc của tôi": khóa MỌI ô +
   *  ẩn nút Lưu / Chỉ định XN / Thêm thuốc. Chỉ xem, không ghi. */
  readOnly?: boolean;
  /** canEditAdmin = cho SỬA mục I Hành chính (PATCH /api/patients) — độc lập với
   *  readOnly (Lễ tân chỉ-đọc lâm sàng nhưng vẫn sửa được hành chính). */
  canEditAdmin?: boolean;
  /** showPreVisitBrief = hiện nút "Xem tóm tắt trước khám" (gọi-và-hiện, read-only).
   *  Chỉ BÁC SĨ (isDoctorRole) bật từ server. ĐỘC LẬP với readOnly — nút chỉ đọc
   *  nên vẫn hiện khi form khóa ghi. */
  showPreVisitBrief?: boolean;
  /** canSign = BÁC SĨ (DOCTOR / ULTRASOUND_DOCTOR): hiện nút cho phép gửi / đính chính, cho
   *  phép gửi và đính chính. Backend cũng chặn theo vai — cờ này chỉ để không
   *  bày ra một cái nút mà người bấm chắc chắn nhận 403. Quản lý và TKYK KHÔNG
   *  có: ký là trách nhiệm chuyên môn, không phải quyền hành chính. */
  canSign?: boolean;
  /** showSono = BÁC SĨ SIÊU ÂM (ULTRASOUND_DOCTOR): hiện form số đo siêu âm thai
   *  (CRL/NT/BPD/HC/AC/FL/EFW) → /api/ultrasound. Server bật theo vai. */
  showSono?: boolean;
  /** enableVisitPager = BÁC SĨ / TKYK: hiện nút ◀ ▶ + "trang i/n" ở tiêu đề phiếu
   *  để xem các lượt khám TRƯỚC/SAU của BN (CHỈ ĐỌC). Lượt cũ luôn khóa ghi. */
  enableVisitPager?: boolean;
  /** showRebook = CSKH / Lễ tân: hiện nút "Tái khám" cạnh "Đóng" → mở trang đặt
   *  lịch của BN (/patients/[id]: hành chính giữ nguyên + form đặt lịch bên dưới). */
  showRebook?: boolean;
  /** onRebook = nếu truyền, nút "Tái khám" gọi callback (mở MODAL đặt lịch nhanh) thay vì
   *  điều hướng sang /patients/[id]. Không truyền → giữ hành vi push cũ (vd trang khác). */
  onRebook?: (clinicPatientId: string) => void;
  /** Bàn giao khách sang phòng dịch vụ ("HANDOFF") hay kết thúc lâm sàng ("TERMINAL"). */
  completionMode?: ClinicalCompletionMode;
  /** Báo trạng thái an toàn của form bệnh án lên khung cha (BanKham). */
  onCompletionGateChange?: (gate: ClinicalCompletionGate) => void;
}) {
  const router = useRouter();
  const p = appt.patient;
  // PHIẾU KHÁM LẤY TỪ CẤU HÌNH, không đoán từ tên dịch vụ nữa.
  //
  // `service.form_code` do backend chọn sẵn theo giới bệnh nhân
  // (service_type.form_code / form_code_nam — xem 20260805000004). Trước đây
  // chỗ này dò từ khoá trong TÊN dịch vụ, và 6/14 dịch vụ của Dr4Women không
  // dò ra: bác sĩ mở lượt khám thì phần phiếu ẩn hẳn, không một lời nào.
  //
  // `resolveServiceCode` giữ làm lưới đỡ cho dịch vụ chưa kịp khai — nhưng nó
  // là đường phụ, không phải đường chính.
  const serviceCode =
    appt.service?.form_code ?? resolveServiceCode(appt.service?.name);
  // Phân biệt "dịch vụ này vốn không có phiếu" với "chưa ai khai" — hai câu
  // khác nhau, và bác sĩ cần biết mình đang gặp câu nào.
  const khongCoPhieu = !serviceCode && !!appt.service?.name;
  const [data, setData] = useState<Data | null>(null);
  const [loading, setLoading] = useState(true);
  const [f, setF] = useState<Fields>(EMPTY);
  const requiredVitals = vitalsBatBuoc(data?.pregnancy);
  const requiredVitalsMsg =
    requiredVitals.size > 1
      ? "Khách đang có thai — bắt buộc nhập Huyết áp, Cân nặng, Chiều cao."
      : "Bắt buộc nhập Huyết áp.";
  const [pm, setPm] = useState<PmFields>(EMPTY_PM);
  const [tk, setTk] = useState<TkFields>(EMPTY_TK);
  const [rx, setRx] = useState<RxRow[]>([]);
  // Danh mục thuốc cho picker — đọc 1 lần từ /api/catalog.
  const [drugOpts, setDrugOpts] = useState<DrugOpt[]>([]);
  const [saving, setSaving] = useState(false);
  const [closing, setClosing] = useState(false);
  const [completedExplicit, setCompletedExplicit] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  // D26 — đã bấm lưu mà thiếu trường sinh hiệu bắt buộc → bật viền đỏ inline.
  const [vitalsTried, setVitalsTried] = useState(false);
  // Tab đang chọn (gom 4 mục). Đón-khám (vitalsOnly) mặc định mở tab "Khám" (1)
  // để điều dưỡng thấy Sinh hiệu ngay; còn lại mặc định tab "Hành chính" (0).
  const [tab, setTab] = useState(vitalsOnly ? 1 : 0);
  // Pager lượt khám (◀ ▶): trang 0 = LƯỢT NÀY (lịch đang mở, ghi được); trang >0 =
  // lượt khám CŨ (chỉ đọc). `pages` dựng 1 lần ở lần nạp trang 0 (ref để đọc trong
  // effect mà không phải thêm vào deps). Lượt cũ nạp bằng visitId.
  interface PageRef { visitId: string | null; date: string; service: string | null }
  const [pages, setPages] = useState<PageRef[]>([]);
  const [pageIdx, setPageIdx] = useState(0);
  const pagesRef = useRef<PageRef[]>([]);
  const viewingPast = pageIdx > 0;
  const showAll = viewingPast;
  // Đổi BN / lịch → component REMOUNT (cả 2 board truyền key={appt.id}) nên
  // pages/pageIdx tự reset, KHÔNG cần effect reset thủ công.
  // Đổi trang qua pager: bật loading NGAY trong handler (không setState trong
  // effect) rồi đổi pageIdx → effect dưới nạp lượt khám tương ứng.
  const goPage = (idx: number) => {
    setLoading(true);
    if (idx !== pageIdx) {
      // Viewing another visit replaces fields. Never mistake them for the
      // current chart when the doctor returns from historical records.
      setForceApply(true);
      setRemoteChanged(false);
    }
    setPageIdx(idx);
  };
  // Hằng số ổn định theo từng lần mount (appt cố định vì board truyền key).
  const apptSlotStart = appt.slot_start;
  const apptServiceName = appt.service?.name ?? null;

  const [coGoDoChuaLuu, setCoGoDoChuaLuu] = useState(false);
  const mocDaLuuRef = useRef<string>("");
  const latestLocal = useRef({ snapshot: "", saving: false });
  const [forceApply, setForceApply] = useState(false);
  const [reloadEpoch, setReloadEpoch] = useState(0);
  const [remoteChanged, setRemoteChanged] = useState(false);
  useEffect(() => {
    latestLocal.current = { snapshot: JSON.stringify({ f, pm, tk, rx }), saving };
  }, [f, pm, tk, rx, saving]);

  useEffect(() => {
    if (!p?.clinic_patient_id || saving) return;
    let on = true;
    // Trang 0 = lượt đang mở (nạp theo appointmentId, đồng thời dựng `pages`).
    // Trang >0 = lượt cũ (nạp theo visitId đã biết trong `pages`).
    const isCurrent = pageIdx === 0;
    const pastVisitId = isCurrent ? null : (pagesRef.current[pageIdx]?.visitId ?? null);
    const qs = isCurrent
      ? `patientId=${p.clinic_patient_id}&appointmentId=${appt.id}`
      : `patientId=${p.clinic_patient_id}&visitId=${pastVisitId}`;
    fetch(`/api/clinical-record?${qs}`)
      .then((r) => {
        if (!r.ok) throw new Error("Không tải được hồ sơ.");
        return r.json();
      })
      .then((d: Data) => {
        if (!on) return;
        const nextF = readDraft(d.draft);
        const nextTk = readTaiKham(d.draft);
        const pr = d.profile;
        const nextPm = pr
            ? {
                allergies: arr(pr.allergies),
                blood_type: pr.blood_type ?? "",
                chronic: arr(pr.chronic_diseases),
                surgical: arr(pr.surgical_history),
                medications: arr(pr.current_medications),
                family: famText(pr.family_history),
                notes: pr.notes ?? "",
              }
            : EMPTY_PM;
        const nextRx = d.prescription_draft
          ? d.prescription_draft.items.map((r) => ({
              ...r,
              id: r.id ?? undefined,
              drug_catalog_id: r.drug_catalog_id ?? null,
            }))
          : (d.prescriptions ?? []).map((p) => ({
              id: p.id,
              drug_catalog_id: p.drug_catalog_id ?? null,
              drug_name: p.drug_name_raw ?? "",
              quantity: p.quantity ?? "",
              dosage: p.dosage_instructions ?? "",
              caution: p.caution ?? "",
            }));
        const nextSnapshot = JSON.stringify({ f: nextF, pm: nextPm, tk: nextTk, rx: nextRx });
        if (isCurrent && mocDaLuuRef.current && !forceApply) {
          const choice = clinicalSyncDecision(latestLocal.current.snapshot,
            mocDaLuuRef.current, nextSnapshot, latestLocal.current.saving);
          if (choice === "conflict") { setRemoteChanged(true); return; }
          if (choice === "unchanged") { setData(d); return; }
        }
        if (isCurrent && forceApply) setForceApply(false);
        if (isCurrent) {
          mocDaLuuRef.current = nextSnapshot;
          latestLocal.current.snapshot = nextSnapshot;
        }
        setRemoteChanged(false);
        setCoGoDoChuaLuu(false);
        setData(d);
        setF(nextF);
        setTk(nextTk);
        setPm(nextPm);
        // Giữ dòng thuốc MỚI chưa lên máy chủ (chưa có id, chưa trùng tên dòng nào
        // vừa nạp) — không thì bản nạp lại xoá dòng người dùng đang gõ dở.
        setRx((cur) => [
          ...nextRx,
          ...(isCurrent
            ? cur.filter(
                (r) =>
                  !r.id &&
                  !nextRx.some(
                    (n) => n.drug_name.trim() !== "" && n.drug_name.trim() === r.drug_name.trim(),
                  ),
              )
            : []),
        ]);
        // Dựng danh sách lượt khám 1 lần: [lượt này] + lịch sử (mới → cũ).
        if (isCurrent && pagesRef.current.length === 0) {
          const built: PageRef[] = [
            { visitId: d.visit?.visit_id ?? null, date: apptSlotStart, service: apptServiceName },
            ...(d.history ?? []).map((h) => ({
              visitId: h.visit_id,
              date: h.created_at,
              service: h.service,
            })),
          ];
          pagesRef.current = built;
          setPages(built);
        }
      })
      .catch(() => {
        if (on) {
          if (reloadEpoch === 0) setData(null);
          setMsg("Không tải được bản cập nhật; nội dung đang nhập được giữ nguyên.");
        }
      })
      .finally(() => on && setLoading(false));
    return () => { on = false; };
  }, [p?.clinic_patient_id, appt.id, pageIdx, apptSlotStart, apptServiceName, reloadEpoch, saving, forceApply]);

  // Reuse the one clinic-scoped SSE connection; no EventSource per form.
  useEffect(() => {
    if (pageIdx !== 0) return;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const reload = () => {
      if (document.visibilityState === "hidden") return;
      clearTimeout(timer);
      timer = setTimeout(() => setReloadEpoch((n) => n + 1), 250);
    };
    const changed = (ev: Event) => {
      const table = (ev as CustomEvent<string>).detail;
      if (["clinical_record", "patient_medical_profile", "prescription", "lab_result", "visit", "vital_measurement"].includes(table)) reload();
    };
    window.addEventListener(SU_KIEN_BANG, changed);
    window.addEventListener("focus", reload);
    document.addEventListener("visibilitychange", reload);
    const safety = setInterval(reload, 60_000);
    return () => {
      clearTimeout(timer); clearInterval(safety);
      window.removeEventListener(SU_KIEN_BANG, changed);
      window.removeEventListener("focus", reload);
      document.removeEventListener("visibilitychange", reload);
    };
  }, [pageIdx]);

  // Tải danh mục thuốc cho picker (dùng chung mọi loại form khám).
  useEffect(() => {
    let on = true;
    fetch("/api/catalog")
      .then((r) => (r.ok ? r.json() : { drugs: [] }))
      .then((d: { drugs?: DrugOpt[] }) => {
        if (!on) return;
        setDrugOpts(d.drugs ?? []);
      })
      .catch(() => {});
    return () => { on = false; };
  }, []);

  const set = (k: keyof Fields, v: string) => setF((s) => ({ ...s, [k]: v }));
  const setP = (k: keyof PmFields, v: string) => setPm((s) => ({ ...s, [k]: v }));
  const toggleTkXn = (code: string) =>
    setTk((s) => ({
      ...s,
      xn: s.xn.includes(code) ? s.xn.filter((c) => c !== code) : [...s.xn, code],
    }));
  const setRxAt = (i: number, k: keyof RxRow, v: string) =>
    setRx((s) => s.map((r, j) => (j === i ? { ...r, [k]: v } : r)));
  const addRx = () => setRx((s) => [...s, { ...EMPTY_RX }]);
  const removeRx = (i: number) => setRx((s) => s.filter((_, j) => j !== i));

  // Hồ sơ có KHOÁ BÚT hay không — danh sách TRẮNG, khớp
  // `WRITABLE_VISIT_STATUSES` ở clinical_record_service.
  //
  // Trước đây là `=== "FINALIZED"`, một danh sách đen. Với INCOMPLETE nó tình
  // cờ đúng (khám dở vẫn ghi được), nhưng trạng thái CUỐI tiếp theo mà ai đó
  // thêm vào sẽ lọt qua và mở form cho một hồ sơ đã khoá — backend từ chối,
  // còn bác sĩ thì gõ xong mới biết.
  const GHI_DUOC = ["OPEN", "IN_PROGRESS", "INCOMPLETE"];
  const visitStatus = data?.visit?.status;
  const locked = visitStatus != null && !GHI_DUOC.includes(visitStatus);

  // GATE LỄ TÂN: CHỈ ghi được (bác sĩ khám / điều dưỡng điền sinh hiệu) khi lễ tân
  // đã check-in (bệnh nhân đã đến). ÁP CHO CẢ luồng đón-khám (vitalsOnly) — quy
  // trình: LỄ TÂN check-in TRƯỚC → điều dưỡng MỚI điền sinh hiệu (đổi 2026-07-03,
  // trước đây gộp check-in + sinh hiệu làm một). COMPLETED vẫn cho xem/sửa nháp
  // khi visit chưa FINALIZED (điền lại để sửa nếu sai).
  const arrivalPending =
    appt.status !== "CHECKED_IN" && appt.status !== "COMPLETED";

  // Saving a chart never finishes the visit. The physician may still order
  // services and return to read results; completion is a separate command.



  // ---- Giữ lại thứ đang gõ dở khi trang bị tải lại / máy mất điện -----------
  //
  // ĐỪNG LẪN VỚI CHỮ "LƯU NHÁP" Ở CUỐI HÀM `save()`. Câu đó nói về hồ sơ ĐÃ ghi
  // lên máy chủ nhưng chưa đủ trường để tự chuyển "Đã khám xong". Thứ ở đây thì
  // CHƯA RỜI KHỎI MÁY TRẠM — nên mọi chữ hiện cho người dùng đều phải nói "chưa
  // được lưu", không được nói "nháp", kẻo bác sĩ tưởng đã xong việc.
  //
  // Chỉ giữ khi ĐANG GHI ĐƯỢC: xem lượt khám cũ hay lễ tân mở chỉ-đọc thì không
  // có gì để mất, mà lưu lại chỉ tổ để dữ liệu bệnh nhân nằm trên máy vô ích.
  const khoaGoDo = khoaNhap(staffId, "phieu-kham", appt.id);
  // Effect tự lưu gọi bản `save` MỚI NHẤT (state mới nhất), không bắt bản cũ.
  const saveRef = useRef<((a?: boolean, b?: boolean) => Promise<void>) | null>(null);
  const ghiDuoc = !readOnly && !viewingPast && !vitalsOnly && !loading && !!data;

  // Bản gõ dở đọc NGAY lúc dựng component, không qua effect: đọc kho của trình
  // duyệt là việc đồng bộ, và làm nó trong effect thì màn hình chớp một nhịp
  // không có dải nhắc.
  const [goDoCu, setGoDoCu] = useState<{ moTa: string; giaTri: GoDo } | null>(() => {
    if (typeof window === "undefined" || !khoaGoDo) return null;
    donNhapCu(window.localStorage, Date.now());
    const b = docNhap<GoDo>(window.localStorage, khoaGoDo, Date.now());
    // `moTa` tính sẵn ở đây: gọi đồng hồ trong lúc vẽ thì mỗi lần vẽ ra một số khác.
    return b ? { moTa: moTaLuc(b.luc, Date.now()), giaTri: b.giaTri } : null;
  });


  // Ghi sau mỗi nhịp gõ ngừng 1 giây. Ghi mỗi phím là ép đĩa vô ích; chờ lâu hơn
  // thì đúng lúc mất điện lại chưa kịp ghi.
  useEffect(() => {
    if (!ghiDuoc || !khoaGoDo || typeof window === "undefined") return;
    const hienTai = JSON.stringify({ f, pm, tk, rx });
    // Lần chạy đầu sau khi nạp xong hồ sơ CHỈ đặt mốc: lúc này form vừa được
    // điền từ máy chủ, chưa ai gõ gì. Ghi ở đây là để lại một bản y hệt bản
    // chính, rồi lần mở sau hỏi "khôi phục?" cho một thứ không có gì để khôi phục.
    if (mocDaLuuRef.current === "") {
      mocDaLuuRef.current = hienTai;
      return;
    }
    if (hienTai === mocDaLuuRef.current) return;
    const t = setTimeout(() => {
      ghiNhap(window.localStorage, khoaGoDo, { f, pm, tk, rx }, Date.now());
      setCoGoDoChuaLuu(true);
      // TỰ LƯU LÊN MÁY CHỦ (Tuyền 17/09/2026): gõ xong ~1 giây là ghi thật, để màn
      // bác sĩ / thư ký bên kia thấy ngay và chuyển màn không mất gì. Bản trên máy
      // trạm vẫn giữ làm lưới hứng khi mất mạng.
      void saveRef.current?.(false, true);
    }, 1000);
    return () => clearTimeout(t);
  }, [ghiDuoc, khoaGoDo, f, pm, tk, rx]);

  // Đóng tab / tải lại khi còn thứ chưa lưu → trình duyệt hỏi lại. Đây là lớp
  // chặn TRƯỚC; bản gõ dở ở trên là lưới hứng khi lớp này không kịp (mất điện).
  useEffect(() => {
    if (!coGoDoChuaLuu) return;
    const canhBao = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", canhBao);
    return () => window.removeEventListener("beforeunload", canhBao);
  }, [coGoDoChuaLuu]);

  function khoiPhucGoDo() {
    if (!goDoCu) return;
    if (canSign && data?.prescription_draft) {
      setMsg("Có đơn thuốc thư ký đang chờ duyệt. Không thể khôi phục đơn thuốc cũ đè lên bản đang xem.");
      return;
    }
    setF(goDoCu.giaTri.f);
    setPm(goDoCu.giaTri.pm);
    setTk(goDoCu.giaTri.tk);
    setRx(goDoCu.giaTri.rx);
    setGoDoCu(null);
  }

  function boGoDo() {
    if (khoaGoDo && typeof window !== "undefined") xoaNhap(window.localStorage, khoaGoDo);
    setGoDoCu(null);
  }

  async function save(approvePrescriptionDraft = false, tuDong = false) {
    if (readOnly) return; // Lễ tân chỉ-đọc: chặn ghi ngay tầng UI (server cũng chặn).
    if (viewingPast) return; // Đang xem lượt khám cũ qua pager: tuyệt đối không ghi.
    if (vitalsOnly) return; // Sinh hiệu chỉ đo ở màn Đo sinh hiệu (17/09/2026).
    // Chưa tải xong / tải LỖI (data=null) → KHÔNG lưu: form còn rỗng sẽ ghi đè
    // xoá đơn thuốc + tiền sử + chẩn đoán cũ của lượt khám (backend thay toàn bộ).
    if (approvePrescriptionDraft && data?.prescription_draft) {
      if (JSON.stringify({ f, pm, tk, rx }) !== mocDaLuuRef.current) {
        setMsg("Bạn đang sửa bệnh án. Hãy lưu phần đang sửa trước rồi mới duyệt đơn thuốc thư ký nhập.");
        return;
      }
      const shown = JSON.stringify(rx.map(({ id, drug_catalog_id, drug_name, quantity, dosage, caution }) =>
        ({ id: id ?? null, drug_catalog_id: drug_catalog_id ?? null, drug_name, quantity, dosage, caution })));
      const pending = JSON.stringify(data.prescription_draft.items.map(({ id, drug_catalog_id, drug_name, quantity, dosage, caution }) =>
        ({ id: id ?? null, drug_catalog_id: drug_catalog_id ?? null, drug_name, quantity, dosage, caution })));
      if (shown !== pending) {
        setMsg("Đơn thuốc trên màn hình không khớp bản thư ký đã lưu. Tải lại trước khi duyệt.");
        return;
      }
    }
    // Tự lưu: im lặng bỏ qua khi chưa lưu được (đang lưu, đang tải, có bản mới
    // từ bên kia) — lần gõ sau sẽ thử lại; không nhảy tab, không bật lỗi.
    if (tuDong && (saving || loading || !data || remoteChanged || arrivalPending)) return;
    // DÒNG THUỐC ĐANG GÕ DỞ (17/09/2026): bấm "Thêm thuốc" rồi gõ, bản tự lưu chạy
    // giữa chừng gửi một dòng thiếu tên/số lượng/cách dùng; máy chủ bỏ dòng ấy, lần
    // nạp lại xoá luôn dòng người dùng đang gõ. Chưa đủ ba ô thì chưa tự lưu.
    if (
      tuDong &&
      !(canSign && data?.prescription_draft) &&
      rx.some((r) => !r.drug_name.trim() || !r.quantity.trim() || !r.dosage.trim())
    ) {
      return;
    }
    if (remoteChanged) {
      setMsg("Hồ sơ đã có thay đổi. Tải và đối chiếu bản mới trước khi lưu.");
      return;
    }
    if (loading || !data) {
      setMsg("Chưa tải xong hồ sơ — đợi/tải lại rồi lưu (tránh mất dữ liệu cũ).");
      return;
    }
    if (arrivalPending) {
      setMsg("Chờ lễ tân xác nhận bệnh nhân đã đến (check-in) trước khi khám.");
      return;
    }
    // C — Sinh hiệu bắt buộc cũng áp cho luồng bác sĩ: thiếu → nhảy tab "Khám"
    // + bật viền đỏ (ô ở tab khác nên không thì sẽ "im lặng").
    // Sinh hiệu chỉ xem ở đây (đo ở màn Đo sinh hiệu) nên thiếu thì NHẮC, không
    // chặn lưu bệnh án — bác sĩ không có ô nào để tự bù.
    const missingReq = [...requiredVitals].filter((k) => f[k].trim() === "");
    if (missingReq.length && !tuDong) {
      setVitalsTried(true);
    }
    setSaving(true);
    setMsg(null);
    // Mục X: chỉ ghi khóa tai_kham khi có ngày HOẶC ≥1 nhóm XN (hợp đồng với màn
    // CSKH nhắc tái khám — không nhập gì thì giữ soap_plan sạch, không có khóa).
    const tkNgay = tk.ngay.trim();
    const tkXn = TAIKHAM_XN.map(([c]) => c).filter((c) => tk.xn.includes(c));
    const tkGhiChu = tk.ghi_chu.trim();
    const plan: Record<string, unknown> = { loi_dan: f.loi_dan };
    if (tkNgay || tkXn.length > 0) {
      plan.tai_kham = {
        ...(tkNgay ? { ngay: tkNgay } : {}),
        xn: tkXn,
        ...(tkGhiChu ? { ghi_chu: tkGhiChu } : {}),
      };
    }
    const res = await fetch("/api/clinical-record", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        appointmentId: appt.id,
        clinicPatientId: p?.clinic_patient_id,
        chief_complaint: f.ly_do,
        subjective: { benh_su: f.benh_su },
        objective: {
          vitals: {
            mach: f.mach, nhiet_do: f.nhiet_do, huyet_ap: f.huyet_ap,
            nhip_tho: f.nhip_tho, spo2: f.spo2, can_nang: f.can_nang,
            // Không gửi BMI: máy chủ tự tính từ cân nặng/chiều cao (S0-3).
            chieu_cao: f.chieu_cao, muc_do_dau: f.muc_do_dau,
          },
          kham_thai: {
            tuoi_thai: f.tuoi_thai, du_kien_sinh: f.du_kien_sinh,
            chieu_cao_tc: f.chieu_cao_tc, nhip_tim_thai: f.nhip_tim_thai,
          },
        },
        assessment: { chan_doan: f.chan_doan },
        plan,
        profile: {
          allergies: splitComma(pm.allergies),
          blood_type: pm.blood_type || null,
          chronic_diseases: splitComma(pm.chronic),
          surgical_history: splitComma(pm.surgical),
          current_medications: splitComma(pm.medications),
          family_history: pm.family || null,
          notes: pm.notes || null,
        },
        expectedRevision: data.revision,
        approvePrescriptionDraft,
        prescriptions: canSign && data.prescription_draft
          ? data.prescriptions.map((r) => ({
              id: r.id,
              drug_catalog_id: r.drug_catalog_id ?? null,
              drug_name: r.drug_name_raw ?? "",
              quantity: r.quantity ?? "",
              dosage: r.dosage_instructions ?? "",
              caution: r.caution ?? "",
            }))
          : rx.map((r) => ({
              ...r,
              drug_catalog_id: r.drug_catalog_id ?? null,
            })),
      }),
    });
    if (!res.ok) {
      setSaving(false);
      setMsg((await res.json()).error ?? "Lỗi lưu hồ sơ.");
      return; // GIỮ bản gõ dở: lưu hỏng đúng là lúc cần nó nhất.
    }
    // Đã nằm trên máy chủ → bản trên máy trạm hết việc. Xoá ngay, và dời mốc
    // "đã lưu" để cảnh báo đóng tab không còn kêu oan.
    if (khoaGoDo && typeof window !== "undefined") xoaNhap(window.localStorage, khoaGoDo);
    mocDaLuuRef.current = JSON.stringify({ f, pm, tk, rx });
    setCoGoDoChuaLuu(false);
    if (data?.visit?.visit_id) baoBenhAnDaLuu(data.visit.visit_id);
    if (tuDong) {
      // Không nạp lại cả form (người đang gõ tiếp sẽ mất chữ); chỉ nhận số phiên
      // bản mới để lần lưu sau không bị coi là ghi đè.
      const ra = (await res.json().catch(() => null)) as { revision?: number } | null;
      if (ra?.revision !== undefined) {
        setData((d) => (d ? { ...d, revision: ra.revision as number } : d));
      }
      setSaving(false);
      setMsg(
        `Đã tự lưu lúc ${new Date().toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit", second: "2-digit", timeZone: "Asia/Ho_Chi_Minh" })}.`,
      );
      return;
    }
    setLoading(true);
    setReloadEpoch((n) => n + 1);
    setSaving(false);
    setMsg(approvePrescriptionDraft
      ? "Đã duyệt đơn thuốc thư ký nhập; nhà thuốc có thể tiếp nhận."
      : canSign
        ? "Đã lưu nháp hồ sơ. Kết thúc lượt khám là thao tác riêng sau khi hoàn tất chỉ định."
        : "Đã lưu nháp. Đơn thuốc cần bác sĩ duyệt trước khi nhà thuốc tiếp nhận.");
    router.refresh();
  }

  useEffect(() => {
    saveRef.current = save;
  });

  /* eslint-disable react-hooks/refs */
  const currentSnapshot = JSON.stringify({ f, pm, tk, rx });
  const isDirty =
    mocDaLuuRef.current !== "" && currentSnapshot !== mocDaLuuRef.current;

  const completionGate = useMemo(
    () =>
      clinicalCompletionGate({
        mode: completionMode,
        hasData: Boolean(data),
        loading,
        saving,
        remoteChanged,
        dirty: isDirty,
        hasPrescriptionDraft: Boolean(data?.prescription_draft),
        diagnosis: f.chan_doan,
        advice: f.loi_dan,
      }),
    [
      completionMode,
      data,
      loading,
      saving,
      remoteChanged,
      isDirty,
      f.chan_doan,
      f.loi_dan,
    ],
  );
  /* eslint-enable react-hooks/refs */

  useEffect(() => {
    onCompletionGateChange?.(completionGate);
  }, [onCompletionGateChange, completionGate]);

  async function completeExam() {
    if (!canSign || readOnly || vitalsOnly || viewingPast || appt.status !== "CHECKED_IN") return;
    if (closing) return;
    const gate = clinicalCompletionGate({
      mode: "TERMINAL",
      hasData: Boolean(data),
      loading,
      saving,
      remoteChanged,
      dirty:
        mocDaLuuRef.current !== "" &&
        JSON.stringify({ f, pm, tk, rx }) !== mocDaLuuRef.current,
      hasPrescriptionDraft: Boolean(data?.prescription_draft),
      diagnosis: f.chan_doan,
      advice: f.loi_dan,
    });
    if (!gate.ok) {
      setMsg(gate.message ?? "Hồ sơ chưa sẵn sàng.");
      return;
    }
    if (!window.confirm("Bác sĩ xác nhận đã hoàn tất lần khám này và các chỉ định cần làm trong lượt. Kết quả gửi về sau vẫn được theo dõi riêng. Kết thúc khám?")) return;
    setClosing(true);
    try {
      const res = await fetch("/api/appointments", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: appt.id, action: "complete" }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        setMsg(body?.error ?? "Chưa thể kết thúc khám; hãy kiểm tra tình trạng lượt khám.");
        return;
      }
      setCompletedExplicit(true);
      setMsg("Đã kết thúc khám. Các kết quả về sau vẫn được theo dõi riêng.");
      router.refresh();
    } catch {
      setMsg("Không gửi được lệnh kết thúc khám. Hãy kiểm tra kết nối rồi thử lại.");
    } finally {
      setClosing(false);
    }
  }

  const preg = data?.pregnancy;
  const labs = data?.labs ?? [];
  // khoá khi: LỄ TÂN chỉ-đọc / hồ sơ đã chốt / đang lưu / (bác sĩ) BN chưa check-in
  // / đang tải prefill (chưa tải xong mà sửa+lưu sẽ ghi đè rỗng — xem guard save())
  // / đang XEM LƯỢT KHÁM CŨ qua pager (viewingPast — chỉ đọc, không ghi đè lượt cũ).
  const ro = readOnly || locked || saving || arrivalPending || loading || viewingPast;
  // SINH HIỆU CHỈ ĐO Ở MÀN "ĐO SINH HIỆU" (Tuyền chốt 17/09/2026: "cái nào cũ
  // thì bỏ"). Luồng đón-khám cũ (vitalsOnly) chỉ còn XEM số đã đo — lưu ở đây
  // không báo "đã đo" cho luồng khám, khách kẹt ngoài hàng chờ bác sĩ.
  //
  // Batch pilot 18/09: KHÔNG còn nhập trùng ở bệnh án, kể cả vai bác sĩ/thư ký
  // — ô sinh hiệu ở đây luôn chỉ xem số đo từ `vital_measurement`.
  const vitalsRo = true;
  const rxReadOnly = ro || vitalsOnly || (canSign && data?.prescription_draft != null);
  const roRest = ro || vitalsOnly; // đón-khám (vitalsOnly): mọi mục khác chỉ xem
  // "YYYY-MM-DD" theo giờ máy người dùng — min cho ô Ngày tái khám (mục X).
  const todayYmd = new Date().toLocaleDateString("en-CA");

  // Dấu ✓ trên tab nếu mục đó đã có field điền (gợi tiến độ; thuần đọc state).
  const ne = (s: string) => s.trim() !== "";
  const tabFilled = (t: number): boolean => {
    switch (t) {
      case 0:
        return [pm.allergies, pm.blood_type, pm.chronic, pm.surgical, pm.medications, pm.family, pm.notes].some(ne);
      case 1:
        return [f.ly_do, f.benh_su, f.mach, f.nhiet_do, f.huyet_ap, f.nhip_tho, f.spo2, f.can_nang, f.chieu_cao, f.bmi, f.muc_do_dau, f.tuoi_thai, f.du_kien_sinh, f.chieu_cao_tc, f.nhip_tim_thai].some(ne);
      case 2:
        return (data?.labs?.length ?? 0) > 0;
      case 3:
        return ne(f.chan_doan) || ne(f.loi_dan) || rx.length > 0 || ne(tk.ngay) || tk.xn.length > 0 || ne(tk.ghi_chu);
      default:
        return false;
    }
  };

  return (
    <div
      className={
        "flex flex-col rounded-card border border-line bg-surface shadow-card " +
        (fill
          ? "max-h-[calc(100vh-2rem)] md:max-h-none md:h-full"
          : "max-h-[calc(100vh-2rem)]")
      }
    >
      {/* Danh mục dùng chung cho picker đã nạp vào state drugOpts */}
      {remoteChanged && (
        <div role="status" className="border-b border-line bg-amber-50 px-4 py-3 text-sm text-amber-900">
          Hồ sơ có bản mới từ nhân viên khác. Nội dung bạn đang nhập được giữ nguyên.
          <button type="button" disabled={saving} className="ml-2 underline font-semibold"
            onClick={() => { setForceApply(true); setReloadEpoch((n) => n + 1); }}>
            Tải bản mới và bỏ nội dung chưa lưu
          </button>
        </div>
      )}
      {/* Có thứ gõ dở của chính người này, cho chính lịch hẹn này, chưa kịp lưu.
          Không tự điền đè: bác sĩ có thể đã chủ ý bỏ nó, và điền đè lên hồ sơ
          vừa tải về là cách âm thầm làm hỏng dữ liệu đúng. Hỏi, rồi mới làm. */}
      {ghiDuoc && goDoCu && (
        <div className="flex flex-wrap items-center gap-2 border-b border-line bg-amber-50 px-4 py-2 text-sm text-amber-900">
          <span className="flex-1">
            Có nội dung bạn gõ dở <b>{goDoCu.moTa}</b> mà <b>chưa được lưu</b>.
          </span>
          <button
            type="button"
            onClick={khoiPhucGoDo}
            className="rounded border border-amber-700 px-2 py-1 font-medium hover:bg-amber-100"
          >
            Khôi phục
          </button>
          <button
            type="button"
            onClick={boGoDo}
            className="rounded px-2 py-1 underline hover:bg-amber-100"
          >
            Bỏ
          </button>
        </div>
      )}
      <div className="flex items-center justify-between border-b border-line px-4 py-3">
        <div className="min-w-0">
          <h3 className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm font-bold uppercase text-ink">
            <span>Phiếu khám bệnh</span>
            {vitalsOnly && (
              <span className="rounded bg-warning-bg px-1.5 py-0.5 text-label font-medium normal-case text-warning">
                Chỉ xem — đo ở màn Đo sinh hiệu
              </span>
            )}
          </h3>
          <p className="text-xs text-ink-muted">
            {p?.full_name} · {p?.patient_code}
            {viewingPast
              ? `${pages[pageIdx]?.service ? ` · ${pages[pageIdx]?.service}` : ""} · ${fmtDateTimeOrDate(pages[pageIdx]?.date ?? appt.slot_start)}`
              : `${appt.service?.name ? ` · ${appt.service.name}` : ""} · ${fmtDateTimeOrDate(appt.slot_start)}`}
          </p>
        </div>
        <button onClick={onClose} aria-label="Đóng" className="shrink-0 rounded-md p-1 text-ink-muted hover:bg-surface-sunken">
          <X size={18} />
        </button>
      </div>

      {/* Banner cảnh báo = vùng TRÊN cố định (không cuộn cùng nội dung). */}
      {!viewingPast && (readOnly || locked || (arrivalPending && !readOnly)) && (
        <div className="space-y-1.5 border-b border-line px-4 py-2">
          {readOnly && !vitalsOnly && (
            <p className="rounded-md bg-brand-100 px-3 py-1.5 text-xs text-brand-800">
              👁 Hồ sơ lâm sàng chỉ xem (Lễ tân/CSKH có thể sửa thông tin Hành chính ở tab tương ứng).
            </p>
          )}
          {/* Bảng lịch ở Trang chủ mở phiếu CHỈ XEM (Tuyền chốt 18/09/2026).
              Nhãn "Chỉ xem — đo ở màn Đo sinh hiệu" chỉ nói về sinh hiệu, nên
              người mở tưởng phần còn lại gõ được. Nói thẳng chỗ sửa. */}
          {readOnly && vitalsOnly && (
            <p className="rounded-md bg-brand-100 px-3 py-1.5 text-xs text-brand-800">
              👁 Chỉ xem — sửa bệnh án ở Bàn khám, đo sinh hiệu ở màn Đo sinh hiệu.
            </p>
          )}
          {locked && (
            <p className="rounded-md bg-danger-bg px-3 py-1.5 text-xs text-danger">
              🔒 Hồ sơ đã chốt (FINALIZED) — luật cấm sửa, chỉ xem.
            </p>
          )}
          {arrivalPending && !readOnly && (
            <p className="rounded-md bg-warning-bg px-3 py-1.5 text-xs text-warning">
              🕓 Chờ lễ tân check-in (bệnh nhân đã đến) —{" "}
              {vitalsOnly ? "chưa điền được sinh hiệu." : "chưa khám được."}
            </p>
          )}
        </div>
      )}

      {/* Hàng 1: Khám mới / Khám cũ (chỉ hiển thị khi có >1 lượt khám) */}
      {pages.length > 1 && (
        <div className="flex shrink-0 items-center border-b border-line bg-surface-muted px-3 py-1.5 select-none">
          {/* Cụm nút chuyển đổi (đứng yên) */}
          <div className="flex shrink-0 items-center gap-1.5 pr-3 border-r border-line">
            <button
              type="button"
              onClick={() => {
                if (viewingPast) goPage(0);
              }}
              className={`rounded-lg px-3 py-1 text-xs font-semibold uppercase tracking-wider transition-all duration-150 ${
                !viewingPast
                  ? "bg-brand-600 text-white shadow-sm"
                  : "bg-surface border border-line text-ink-soft hover:bg-surface-sunken"
              }`}
            >
              Khám mới
            </button>
            <button
              type="button"
              onClick={() => {
                if (!viewingPast) {
                  goPage(1); // Mặc định chọn lượt cũ gần nhất
                }
              }}
              className={`rounded-lg px-3 py-1 text-xs font-semibold uppercase tracking-wider transition-all duration-150 ${
                viewingPast
                  ? "bg-brand-600 text-white shadow-sm"
                  : "bg-surface border border-line text-ink-soft hover:bg-surface-sunken"
              }`}
            >
              Khám cũ
            </button>
          </div>

          {/* Danh sách các lần khám cũ di chuyển (chỉ hiện khi viewingPast) */}
          {viewingPast && (
            <div
              className="flex-1 overflow-x-auto pl-3 flex items-center gap-1.5 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
              onWheel={(e) => {
                if (e.deltaY !== 0) {
                  e.currentTarget.scrollLeft += e.deltaY;
                }
              }}
            >
              {pages.slice(1).map((pg, i) => {
                const visitIdx = i + 1;
                const isSelected = pageIdx === visitIdx;
                const lanLabel = `Lần ${pages.length - visitIdx}`;
                return (
                  <button
                    key={pg.visitId ?? visitIdx}
                    type="button"
                    onClick={() => goPage(visitIdx)}
                    className={`shrink-0 rounded-lg px-2.5 py-1 text-xs font-medium border transition-colors duration-150 ${
                      isSelected
                        ? "bg-status-assigned-bg font-semibold text-status-assigned border-status-assigned"
                        : "bg-surface border-line text-ink-soft hover:bg-surface-sunken"
                    }`}
                  >
                    {lanLabel}: {fmtDate(pg.date)}
                  </button>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Thanh TAB (cố định) — chia 4 mục theo luồng khám; chỉ render tab đang chọn. */}
      {!viewingPast && (
        <div className="flex shrink-0 gap-1 overflow-x-auto border-b border-line px-3 py-1.5">
          {TABS.map((t, i) => (
            <button
              key={t}
              type="button"
              onClick={() => setTab(i)}
              className={TAB + (i === tab ? TAB_ON : TAB_OFF)}
            >
              {t}
              {tabFilled(i) && <span className="ml-1 text-brand-600">✓</span>}
            </button>
          ))}
        </div>
      )}

      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-3">
        {tab === 0 && !showAll && (
        <Section
          no="I"
          title="Hành chính"
          synced={!canEditAdmin}
          editorLabel="có thể sửa"
        >
          {canEditAdmin && p ? (
            <PatientAdminEditor
              patient={{
                clinic_patient_id: p.clinic_patient_id,
                full_name: p.full_name,
                date_of_birth: p.date_of_birth,
                phone_primary: p.phone_primary,
                phone_secondary: p.phone_secondary,
                gender: p.gender,
                ethnicity: p.ethnicity,
                nationality: p.nationality,
                occupation: p.occupation,
                patient_objection: p.patient_objection,
                address: p.address,
                guardian_name: p.guardian_name,
              }}
            />
          ) : (
            <dl className="grid gap-x-4 gap-y-1.5 sm:grid-cols-2">
              <AdminRow label="Họ tên" value={p?.full_name} />
              <AdminRow label="Ngày sinh" value={p?.date_of_birth ? fmtDate(p.date_of_birth) : null} />
              <AdminRow label="Giới tính" value={p?.gender} />
              <AdminRow label="Dân tộc" value={p?.ethnicity} />
              <AdminRow label="Quốc tịch" value={p?.nationality} />
              <AdminRow label="Nghề nghiệp" value={p?.occupation} />
              <AdminRow label="Đối tượng" value={p?.patient_objection} />
              <AdminRow label="SĐT" value={p?.phone_primary} />
              <AdminRow label="Địa chỉ" value={p?.address} />
            </dl>
          )}
        </Section>
        )}

        {tab === 0 && !showAll && (data?.history?.length ?? 0) > 0 && (
          <details className="border-t border-surface-sunken pt-3" open>
            <summary className="cursor-pointer text-sm font-semibold text-ink">
              Lịch sử khám trước ({data!.history.length})
            </summary>
            <ul className="mt-2 space-y-2">
              {data!.history.map((h) => (
                <li
                  key={h.visit_id}
                  className="rounded-lg border border-line bg-surface-muted p-2.5 text-sm"
                >
                  <div className="flex flex-wrap items-center justify-between gap-1">
                    <span className="font-medium text-ink">
                      {fmtDate(h.created_at)}
                    </span>
                    <span className="text-xs text-ink-muted">
                      {[h.service, h.doctor].filter(Boolean).join(" · ") || "—"}
                    </span>
                  </div>
                  {h.chief_complaint && (
                    <p className="mt-1 line-clamp-3 text-ink-soft">
                      <span className="text-ink-muted">Lý do: </span>
                      {h.chief_complaint}
                    </p>
                  )}
                  {h.assessment && (
                    <p className="mt-0.5 line-clamp-2 text-ink-soft">
                      <span className="text-ink-muted">Chuẩn đoán: </span>
                      {h.assessment}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          </details>
        )}

        {(tab === 1 || showAll) && (
        <Section no="" title="Sinh hiệu" editorLabel="đo ở màn Đo sinh hiệu — chỉ xem">
          <div className="grid grid-cols-2 gap-2">
            {/* Ô SỐ bắt buộc số + NGƯỠNG hợp lý (tránh gõ thừa số: 37→377). Huyết
                áp là CHỮ vì dạng "120/80". [key, nhãn, type, step, min, max] */}
            {([
              ["mach", "Mạch (l/p)", "number", "1", 20, 250],
              ["nhiet_do", "Nhiệt độ (°C)", "number", "0.1", 30, 45],
              ["huyet_ap", "Huyết áp", "text", undefined, 0, 0],
              ["nhip_tho", "Nhịp thở (l/p)", "number", "1", 5, 80],
              ["spo2", "SpO2 (%)", "number", "1", 50, 100],
              ["can_nang", "Cân nặng (kg)", "number", "0.1", 1, 300],
              ["chieu_cao", "Chiều cao (cm)", "number", "0.1", 20, 250],
              // Thang đau 0–10 — có trong phiếu giấy và trong bảng sinh hiệu
              // từ 16/09/2026, nhưng thiếu ô nhập thì cột ấy vĩnh viễn rỗng.
              ["muc_do_dau", "Mức độ đau (0–10)", "number", "1", 0, 10],
            ] as [keyof Fields, string, string, string | undefined, number, number][]).map(
              ([k, lbl, ty, st, lo, hi]) => {
                // Cảnh báo: ô số → ngoài ngưỡng; Huyết áp → sai định dạng/bất thường.
                let warn: string | null = null;
                const v = f[k].trim();
                if (v !== "") {
                  if (k === "huyet_ap") warn = bloodPressureWarn(v);
                  else if (ty === "number") {
                    const n = Number(v);
                    if (!Number.isFinite(n)) warn = "Phải là số";
                    else if (n < lo || n > hi) warn = `Nên trong ${lo}–${hi}`;
                  }
                }
                // Trường bắt buộc → đánh dấu * + báo "Bắt buộc" khi đã bấm Lưu.
                const required = requiredVitals.has(k);
                const missing = required && v === "" && vitalsTried;
                return (
                  <div key={k}>
                    <label className={LABEL}>
                      {lbl}
                      {required && <span className="text-brand-600"> *</span>}
                    </label>
                    <input
                      type={ty}
                      step={ty === "number" ? st : undefined}
                      inputMode={ty === "number" ? "decimal" : undefined}
                      min={ty === "number" ? lo : undefined}
                      max={ty === "number" ? hi : undefined}
                      placeholder={k === "huyet_ap" ? "vd 120/80" : undefined}
                      className={INPUT + (warn || missing ? " border-danger" : "")}
                      value={f[k]}
                      disabled={vitalsRo}
                      onChange={(e) => set(k, e.target.value)}
                    />
                    {(missing || warn) && (
                      <p className="mt-0.5 text-label text-danger">
                        {missing ? "Bắt buộc" : warn}
                      </p>
                    )}
                  </div>
                );
              },
            )}
            {vitalsTried &&
            [...requiredVitals].some((k) => f[k].trim() === "") ? (
              <p className="col-span-2 text-xs text-warning">
                {requiredVitalsMsg} — nhờ điều dưỡng đo ở màn Đo sinh hiệu.
              </p>
            ) : null}
            {/* BMI KHÔNG có ô nhập (S0-3, 18/09/2026 — thay chốt 15/09 "gợi ý,
                sửa được"): máy chủ tự tính từ cân nặng/chiều cao khi lưu. */}
            <div>
              <label className={LABEL} htmlFor="bmi-tu-tinh">BMI (tự tính khi lưu)</label>
              <input id="bmi-tu-tinh" className={INPUT} value={f.bmi || "—"} disabled readOnly />
            </div>
          </div>
        </Section>
        )}

        {/* D25 — "Lý do khám bệnh" do BÁC SĨ đưa ra, ĐIỀU DƯỠNG nhập hộ vào bệnh
            án → mở quyền sửa cho cả luồng đón-khám (dùng `ro` thay `roRest`).
            Tách bạch với "Vấn đề khiến BN đi khám" của CSKH (không có ở form này). */}
        {(tab === 1 || showAll) && (
        <Section no="II" title="Lý do khám bệnh" editorLabel="bác sĩ / điều dưỡng điền">
          <input className={INPUT} value={f.ly_do} disabled={ro} onChange={(e) => set("ly_do", e.target.value)} placeholder="VD: Khám thai" />
        </Section>
        )}

        {tab === 0 && !showAll && (
        <Section no="III" title="Tiền sử dị ứng">
          <input
            className={INPUT}
            value={pm.allergies}
            disabled={roRest}
            onChange={(e) => setP("allergies", e.target.value)}
            placeholder="Cách nhau dấu phẩy, vd: Penicillin, Hải sản"
          />
        </Section>
        )}

        {tab === 0 && !showAll && (
        <Section no="IV" title="Tiền sử (mạn tính / Phẫu thuật / thuốc / gia đình)">
          <div className="space-y-2">
            <div>
              <label className={LABEL}>Nhóm máu</label>
              <select className={INPUT} value={pm.blood_type} disabled={roRest} onChange={(e) => setP("blood_type", e.target.value)}>
                {BLOOD_TYPES.map((b) => (
                  <option key={b} value={b}>{b || "—"}</option>
                ))}
              </select>
            </div>
            <div>
              <label className={LABEL}>Bệnh mạn tính</label>
              <input className={INPUT} value={pm.chronic} disabled={roRest} onChange={(e) => setP("chronic", e.target.value)} placeholder="Cách nhau dấu phẩy" />
            </div>
            <div>
              <label className={LABEL}>Tiền sử phẫu thuật</label>
              <input className={INPUT} value={pm.surgical} disabled={roRest} onChange={(e) => setP("surgical", e.target.value)} placeholder="Cách nhau dấu phẩy" />
            </div>
            <div>
              <label className={LABEL}>Thuốc đang dùng</label>
              <input className={INPUT} value={pm.medications} disabled={roRest} onChange={(e) => setP("medications", e.target.value)} placeholder="Cách nhau dấu phẩy" />
            </div>
            <div>
              <label className={LABEL}>Tiền sử gia đình</label>
              <input className={INPUT} value={pm.family} disabled={roRest} onChange={(e) => setP("family", e.target.value)} />
            </div>
            <div>
              <label className={LABEL}>Ghi chú tiền sử</label>
              <textarea className={INPUT} rows={2} value={pm.notes} disabled={roRest} onChange={(e) => setP("notes", e.target.value)} />
            </div>
          </div>
        </Section>
        )}

        {(tab === 1 || showAll) && (
        <Section no="V" title="Bệnh sử & khám thai">
          <textarea className={INPUT} rows={2} value={f.benh_su} disabled={roRest} onChange={(e) => set("benh_su", e.target.value)} placeholder="Quá trình bệnh lý…" />
          {!loading && preg && (
            <dl className="mt-2 space-y-1.5">
              <AdminRow label="Dự kiến sinh (HS)" value={preg.edd_date ? fmtDate(preg.edd_date) : null} />
              <AdminRow label="Tuổi thai (ĐK)" value={preg.gestational_age_at_registration != null ? `${preg.gestational_age_at_registration} tuần` : null} />
              <AdminRow label="Nguy cơ cao" value={preg.is_high_risk ? `Có${preg.high_risk_reason ? " — " + preg.high_risk_reason : ""}` : "Không"} />
            </dl>
          )}
          <div className="mt-2 grid grid-cols-2 gap-2">
            {/* Dự kiến sinh = ngày; Tuổi thai/Cao TC/Tim thai = SỐ (bắt buộc số). */}
            {([
              ["tuoi_thai", "Tuổi thai (tuần)", 1, 45],
              ["du_kien_sinh", "Dự kiến sinh", 0, 0],
              ["chieu_cao_tc", "Cao TC/VB (cm)", 1, 60],
              ["nhip_tim_thai", "Tim thai (l/p)", 60, 220],
            ] as [keyof Fields, string, number, number][]).map(([k, lbl, lo, hi]) => {
              const ty = k === "du_kien_sinh" ? "date" : "number";
              const n = ty === "number" && f[k].trim() !== "" ? Number(f[k]) : null;
              const oor = n != null && Number.isFinite(n) && (n < lo || n > hi);
              return (
                <div key={k}>
                  <label className={LABEL}>{lbl}</label>
                  <input
                    type={ty}
                    step={ty === "number" ? (k === "chieu_cao_tc" ? "0.1" : "1") : undefined}
                    inputMode={ty === "number" ? "decimal" : undefined}
                    min={ty === "number" ? lo : undefined}
                    max={ty === "number" ? hi : undefined}
                    className={INPUT + (oor ? " border-danger" : "")}
                    value={f[k]}
                    disabled={roRest}
                    onChange={(e) => set(k, e.target.value)}
                  />
                  {oor && (
                    <p className="mt-0.5 text-label text-danger">
                      Nên trong {lo}–{hi}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        </Section>
        )}

        {/* Số đo siêu âm thai — CHỈ Bác sĩ Siêu âm (showSono). Lưu riêng qua
            /api/ultrasound (ultrasound_record), KHÔNG dính nút Lưu hồ sơ chính. */}
        {(tab === 1 || showAll) && showSono && !viewingPast && p?.clinic_patient_id && (
          <div className="border-t border-surface-sunken pt-3">
            <SonoBiometry
              appointmentId={appt.id}
              clinicPatientId={p.clinic_patient_id}
            />
          </div>
        )}

        {(tab === 2 || showAll) && (
        <Section no="VI" title="Kết quả cận lâm sàng" synced>
          {loading ? (
            <Loading />
          ) : labs.length === 0 ? (
            <p className="text-sm text-ink-faint">— chưa chỉ định / chưa có kết quả —</p>
          ) : (
            <ul className="divide-y divide-surface-sunken rounded-lg border border-line">
              {labs.map((l, i) => (
                <li key={i} className="flex items-center justify-between gap-2 px-3 py-1.5 text-sm">
                  <span className="min-w-0 truncate text-ink">{cleanTestName(l.test_name)}</span>
                  <span className="flex shrink-0 items-center gap-2">
                    <span className="font-medium">
                      {l.result_value ?? l.result_numeric ?? (l.external_ref ? "có phiếu" : "chờ KQ")}
                      {l.result_unit ? ` ${l.result_unit}` : ""}
                    </span>
                    {toHref(l.external_ref) && (
                      <a
                        href={toHref(l.external_ref)!}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs font-medium text-specialty-service hover:underline"
                      >
                        Phiếu
                      </a>
                    )}
                    {l.flag && l.flag !== "NORMAL" && (
                      <span className="rounded bg-danger-bg px-1.5 py-0.5 text-label font-medium text-danger">{l.flag}</span>
                    )}
                  </span>
                </li>
              ))}
            </ul>
          )}
          {!vitalsOnly && !readOnly && canSign && (
            // Slice 1 (18/09/2026): ô "Chỉ định CLS" gõ tự do ở đây từng ghi vào
            // `lab_result` — rail cũ, không vào hàng chờ phòng, không ai nhập
            // được kết quả. Chỉ định giờ chỉ đi một đường: khung Chỉ định của
            // Bàn khám (service_order), kết quả gắn vào đúng chỉ định.
            <p className="mt-2 text-sm text-ink-muted">
              Chỉ định cận lâm sàng ở khung “Chỉ định” của Bàn khám — kết quả sẽ gắn
              vào đúng chỉ định.
            </p>
          )}
        </Section>
        )}

        {(tab === 3 || showAll) && (
        <Section no="VII" title="Chuẩn đoán">
          <textarea className={INPUT} rows={2} value={f.chan_doan} disabled={roRest} onChange={(e) => set("chan_doan", e.target.value)} placeholder="VD: Z34 - Theo dõi thai…" />
        </Section>
        )}

        {(tab === 3 || showAll) && (
        <Section no="VIII" title="Hướng xử lý & lời dặn">
          <textarea className={INPUT} rows={3} value={f.loi_dan} disabled={roRest} onChange={(e) => set("loi_dan", e.target.value)} />
        </Section>
        )}

        {(tab === 3 || showAll) && !vitalsOnly && (
          <Section no="IX" title="Đơn thuốc">
            {data?.prescription_draft && (
              <div className="mb-3 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">
                Đơn thuốc nháp — chưa chuyển sang nhà thuốc.
                {canSign && !viewingPast && !readOnly && (
                  <button type="button" disabled={saving || loading || remoteChanged || locked}
                    onClick={() => void save(true)} className="ml-2 font-semibold underline">
                    Duyệt đơn thuốc đang xem
                  </button>
                )}
              </div>
            )}
            <div className="space-y-2">
              {rx.length === 0 && (
                <p className="text-sm text-ink-faint">— chưa kê thuốc —</p>
              )}
              {rx.map((row, i) => (
                <div key={i} className="rounded-lg border border-line p-2">
                  <div className="flex items-start gap-2">
                    <div className="flex-1 space-y-2">
                      <select
                        className={INPUT}
                        value={row.drug_catalog_id ?? ""}
                        disabled={rxReadOnly}
                        onChange={(e) => {
                          const id = e.target.value;
                          const opt = drugOpts.find((d) => d.id === id);

                          setRx((rows) =>
                            rows.map((r, j) =>
                              j !== i
                                ? r
                                : opt
                                  ? {
                                      ...r,
                                      drug_catalog_id: opt.id,
                                      drug_name: opt.name_raw,
                                    }
                                  : {
                                      ...r,
                                      drug_catalog_id: null,
                                      drug_name: "",
                                    },
                            ),
                          );
                        }}
                      >
                        <option value="">— Thuốc khác / chưa có trong danh mục —</option>

                        {drugOpts.map((d) => (
                          <option key={d.id} value={d.id}>
                            {d.name_raw}
                            {d.variant ? ` · ${d.variant}` : ""}
                          </option>
                        ))}
                      </select>

                      {row.drug_catalog_id === null && (
                        <input
                          className={INPUT}
                          placeholder="Tên thuốc chưa có trong danh mục"
                          value={row.drug_name}
                          disabled={rxReadOnly}
                          onChange={(e) => setRxAt(i, "drug_name", e.target.value)}
                        />
                      )}
                    </div>
                    {!rxReadOnly && (
                      <button
                        onClick={() => removeRx(i)}
                        aria-label="Xoá thuốc"
                        className="shrink-0 rounded-md p-1.5 text-danger hover:bg-danger-bg mt-1"
                      >
                        <X size={15} />
                      </button>
                    )}
                  </div>
                  <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-3">
                    <input
                      className={INPUT}
                      placeholder="Số lượng (vd: 30 viên)"
                      value={row.quantity}
                      disabled={rxReadOnly}
                      onChange={(e) => setRxAt(i, "quantity", e.target.value)}
                    />
                    <input
                      className={INPUT}
                      placeholder="Cách dùng (vd: 2v/ngày sau ăn)"
                      value={row.dosage}
                      disabled={rxReadOnly}
                      onChange={(e) => setRxAt(i, "dosage", e.target.value)}
                    />
                    <input
                      className={INPUT}
                      placeholder="Lưu ý"
                      value={row.caution}
                      disabled={rxReadOnly}
                      onChange={(e) => setRxAt(i, "caution", e.target.value)}
                    />
                  </div>
                </div>
              ))}
              {!rxReadOnly && (
                <button
                  onClick={addRx}
                  className="inline-flex items-center gap-1 rounded-lg border border-dashed border-brand-100 px-3 py-1.5 text-sm font-medium text-brand-800 hover:bg-brand-50"
                >
                  <Plus size={14} /> Thêm thuốc
                </button>
              )}
            </div>
          </Section>
        )}

        {/* X — Theo dõi & Tái khám: nguồn dữ liệu cho CSKH nhắc tái khám
            (soap_plan.tai_kham). KHÔNG bắt buộc — không ảnh hưởng "Khám xong". */}
        {(tab === 3 || showAll) && (
        <Section no="X" title="Theo dõi & Tái khám">
          <div className="space-y-2">
            <div>
              <label className={LABEL}>Ngày tái khám</label>
              <input
                type="date"
                min={todayYmd}
                className={INPUT}
                value={tk.ngay}
                disabled={roRest}
                onChange={(e) => setTk((s) => ({ ...s, ngay: e.target.value }))}
              />
            </div>
            <div>
              <label className={LABEL}>Xét nghiệm cần kiểm tra lại</label>
              <div className="flex flex-wrap gap-x-4 gap-y-1.5">
                {TAIKHAM_XN.map(([code, label]) => (
                  <label
                    key={code}
                    className="inline-flex items-center gap-1.5 text-sm text-ink-soft"
                  >
                    <input
                      type="checkbox"
                      className="h-4 w-4 accent-brand-600"
                      checked={tk.xn.includes(code)}
                      disabled={roRest}
                      onChange={() => toggleTkXn(code)}
                    />
                    {label} ({code})
                  </label>
                ))}
              </div>
            </div>
            <div>
              <label className={LABEL}>Ghi chú tái khám</label>
              <input
                className={INPUT}
                value={tk.ghi_chu}
                disabled={roRest}
                onChange={(e) => setTk((s) => ({ ...s, ghi_chu: e.target.value }))}
                placeholder="Tùy chọn, vd: nhịn ăn sáng trước khi xét nghiệm"
              />
            </div>
            {/* Bác sĩ quyết theo dõi sau thủ thuật — màn CSKH đọc (16/09/2026).
                Tự ẩn khi lượt không có chỉ định thủ thuật. */}
            {data?.visit?.visit_id && (
              <TheoDoiThuThuat visitId={data.visit.visit_id} readOnly={roRest} />
            )}
          </div>
        </Section>
        )}

        {/* Phiếu khám CHUYÊN KHOA (engine config-driven) — pilot Phụ khoa. Chỉ hiện
            cho bác sĩ (KHÔNG ở luồng đón-khám vitalsOnly) khi dịch vụ có config +
            đã có visit. FINALIZED / lễ tân chỉ-đọc → read-only (route cũng chặn ghi). */}
        {tab === 2 && !vitalsOnly && !showAll && serviceCode && data?.visit?.visit_id && (
          <div className="border-t border-surface-sunken pt-3">
            <ServiceFormEngine
              visitId={data.visit.visit_id}
              serviceCode={serviceCode}
              readOnly={readOnly || locked}
            />
          </div>
        )}

        {/* TỆP KẾT QUẢ — ngay trong hồ sơ, không phải một màn khác.
            
            Tuyền 16/09/2026: *"phải có chỗ up file cho bác sĩ, thư ký, điều
            dưỡng… cả CSKH cũng cần có file để xem và tải xuống"*. Kho tệp đã có
            từ 09/08 nhưng chỉ mở ở màn CSKH, nên người cầm kết quả trên tay
            phải nhờ người khác tải hộ.
            
            KHÔNG hiện ở chế độ chỉ-sinh-hiệu: điều dưỡng và lễ tân đo xong là
            xong, tệp kết quả thuộc về phần chuyên môn. */}
        {tab === 2 && !vitalsOnly && !showAll && p?.clinic_patient_id && (
          <div className="border-t border-surface-sunken pt-3">
            <TepCuaLuotKham
              clinicPatientId={p.clinic_patient_id}
              appointmentId={appt.id}
            />
          </div>
        )}

        {/* CHƯA CÓ LƯỢT KHÁM — và đây là lỗ hổng của chính khối bên dưới.
            Dòng "chưa gắn phiếu" ở dưới cũng đòi `visit_id`, nên khi lượt khám
            chưa mở thì KHÔNG có gì hiện ra cả: không phiếu, không lời giải
            thích. Đã gặp thật khi rà màn bác sĩ 06/08 — tab trống trơn, và
            người ngồi trước màn hình không có cách nào biết vì sao.

            `!loading` để không loé dòng này trong lúc đang đọc dữ liệu. */}
        {tab === 2 && !vitalsOnly && !showAll && !loading && !data?.visit?.visit_id && (
          <div className="border-t border-surface-sunken pt-3">
            <p className="rounded-card border border-line bg-brand-50/40 px-3 py-2.5 text-sm text-ink-muted">
              Chưa mở lượt khám nên chưa có chỗ ghi phiếu chuyên khoa.{" "}
              {readOnly || locked ? (
                <>Lượt khám mở khi lễ tân check-in bệnh nhân.</>
              ) : (
                <>
                  Bấm <span className="font-medium text-ink">Lưu hồ sơ</span> ở
                  dưới để mở lượt khám — phiếu sẽ hiện ra ngay sau đó.
                </>
              )}
            </p>
          </div>
        )}

        {/* NÓI RA thay vì ẩn. Một khoảng trống ở đúng chỗ lẽ ra có phiếu khám
            đọc thành "hệ thống hỏng", và bác sĩ sẽ đi hỏi kỹ thuật thay vì ghi
            tiếp vào bệnh án chung. */}
        {tab === 2 && !vitalsOnly && !showAll && khongCoPhieu && data?.visit?.visit_id && (
          <div className="border-t border-surface-sunken pt-3">
            <p className="rounded-card border border-line bg-brand-50/40 px-3 py-2.5 text-sm text-ink-muted">
              Dịch vụ <span className="font-medium text-ink">{appt.service?.name}</span>{" "}
              chưa gắn phiếu khám chuyên khoa — ghi vào bệnh án ở tab bên cạnh.
              Quản lý gắn phiếu cho dịch vụ này ở{" "}
              <span className="font-medium text-ink">Cài đặt → Cấu trúc phòng khám</span>.
            </p>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between gap-2 border-t border-line px-4 py-3">
        <span
          className={
            "text-xs " +
            (viewingPast
              ? "text-brand-800"
              : readOnly && !vitalsOnly
                ? "text-brand-800"
                : /^Đã (lưu|duyệt|kết thúc)/.test(msg ?? "")
                  ? "text-success"
                  : "text-danger")
          }
        >
          {viewingPast ? "" : readOnly && !vitalsOnly ? "👁 Hồ sơ lâm sàng chỉ xem." : (msg ?? "")}
        </span>
        <div className="flex gap-2">
          {/* Lễ tân chỉ-đọc / đang xem lượt cũ: ẨN nút Lưu hoàn toàn (không chỉ disable). */}
          {vitalsOnly && !viewingPast ? (
            <a
              href="/do-sinh-hieu"
              className="inline-flex min-h-10 items-center rounded-lg bg-brand-600 px-4 text-sm font-semibold text-white hover:bg-brand-700"
            >
              Đo sinh hiệu
            </a>
          ) : null}
          {!readOnly && !vitalsOnly && !viewingPast && (
            <button
              onClick={() => void save()}
              disabled={ro}
              className="min-h-10 rounded-lg bg-brand-600 px-4 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
            >
              {saving ? "Đang lưu…" : "Lưu hồ sơ"}
            </button>
          )}
          {canSign && !readOnly && !vitalsOnly && !viewingPast && appt.status === "CHECKED_IN" && (
            <button
              type="button"
              onClick={() => void completeExam()}
              disabled={saving || closing || loading || !data || remoteChanged || completedExplicit}
              className="min-h-10 rounded-control border border-brand-100 bg-surface px-4 text-sm font-semibold text-brand-800 hover:bg-brand-50 disabled:opacity-50"
              title="Chỉ kết thúc sau khi bác sĩ đã xử lý xong các chỉ định của lượt này"
            >
              {closing ? "Đang kết thúc…" : completedExplicit ? "Đã kết thúc khám" : "Kết thúc khám"}
            </button>
          )}
          {/* CSKH / Lễ tân: Tái khám. Có onRebook → mở MODAL đặt lịch nhanh (ở Danh sách
              BN); không có → push sang /patients/[id] như cũ. Đặt cạnh "Đóng". */}
          {showRebook && p?.clinic_patient_id && (
            <button
              onClick={() =>
                onRebook
                  ? onRebook(p.clinic_patient_id)
                  : router.push(`/patients/${p.clinic_patient_id}`)
              }
              className="inline-flex min-h-10 items-center gap-1 rounded-control border border-brand-100 bg-surface px-4 text-sm font-semibold text-brand-800 hover:bg-brand-50"
            >
              <CalendarPlus size={15} /> Tái khám
            </button>
          )}
          <button onClick={onClose} className="min-h-10 rounded-control border border-line bg-surface px-4 text-sm text-ink-soft hover:bg-surface-sunken">
            Đóng
          </button>
        </div>
      </div>

      {/* HỒ SƠ ĐÃ HOÀN TẤT — cho phép gửi + đính chính. Không còn nút ký:
          mốc khoá là Hoàn tất khám ở Bàn khám (23/09/2026). Không hiện khi đang
          xem lượt cũ hoặc chỉ nhập sinh hiệu. */}
      {!viewingPast && !vitalsOnly && (
        <HoSoHoanTatPanel
          visitId={data?.visit?.visit_id ?? null}
          revision={data?.revision ?? null}
          isDoctor={canSign}
          onChanged={() => router.refresh()}
        />
      )}
    </div>
  );
}

function Loading() {
  return <p className="text-sm text-ink-faint">Đang tải…</p>;
}
