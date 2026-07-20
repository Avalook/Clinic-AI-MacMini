"use client";

// Hồ sơ lâm sàng (TÓM TẮT KHÁM BỆNH) — panel bên phải board "Công việc của tôi".
//   I Hành chính ← patient · III/IV Tiền sử ← patient_medical_profile ·
//   V Thai ← pregnancy · VI Cận lâm sàng ← lab_result  (đều ĐỒNG BỘ, read-only).
//   Sinh hiệu, II Lý do, V bệnh sử/khám thai, VII Chuẩn đoán, VIII Lời dặn = BÁC SĨ
//   điền → LƯU NHÁP vào visit (IN_PROGRESS) + clinical_record qua /api/clinical-record.
// AN TOÀN: nếu visit đã FINALIZED → khóa (luật cấm sửa). KHÔNG tự chốt hồ sơ.

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { X, Plus, CalendarPlus } from "lucide-react";
import { fmtDate, fmtDateTimeOrDate } from "../../../lib/datetime";
import { toHref } from "../../../lib/url";
import { INPUT, LABEL } from "../form-ui";
import PatientAdminEditor from "../PatientAdminEditor";
import SonoBiometry from "./SonoBiometry";
import ServiceFormEngine from "./ServiceFormEngine";
import { resolveServiceCode } from "../../../lib/form-schemas";
import type { DoctorApptRow } from "./DoctorWorkBoard";

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
  drug_name_raw: string | null;
  quantity: string | null;
  dosage_instructions: string | null;
  caution: string | null;
}
interface Data {
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
  can_nang: "", chieu_cao: "", bmi: "",
  tuoi_thai: "", du_kien_sinh: "", chieu_cao_tc: "", nhip_tim_thai: "",
};
type Fields = typeof EMPTY;

// D26 — Sinh hiệu BẮT BUỘC: CHỈ 3 trường (Huyết áp / Cân nặng / Chiều cao).
// Mọi vital khác (mạch, nhiệt độ, nhịp thở, SpO2, BMI) là tuỳ chọn.
const REQUIRED_VITALS: ReadonlySet<keyof Fields> = new Set([
  "huyet_ap",
  "can_nang",
  "chieu_cao",
]);

// Tiền sử (III/IV) — bác sĩ sửa, lưu patient_medical_profile.
const EMPTY_PM = {
  allergies: "", blood_type: "", chronic: "", surgical: "",
  medications: "", family: "", notes: "",
};
type PmFields = typeof EMPTY_PM;

// Đơn thuốc (mục IX) — mỗi dòng 1 thuốc. Tên gợi ý từ drug_catalog (mig 051)
// qua <datalist>, vẫn cho gõ tự do (giữ name_raw verbatim khi BS tự nhập).
interface RxRow {
  drug_name: string;
  quantity: string;
  dosage: string;
  caution: string;
}
const EMPTY_RX: RxRow = { drug_name: "", quantity: "", dosage: "", caution: "" };

// Danh mục dùng chung cho picker (đọc runtime từ /api/catalog — KHÔNG hardcode).
interface DrugOpt { name_raw: string; variant: string | null; needs_review: boolean }
interface ClsOpt { service_code: string; name: string; category: string | null }

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
// Tokens thanh tab (đồng bộ theme hồng — khớp ServiceFormEngine).
const TAB =
  "shrink-0 whitespace-nowrap rounded-lg px-3 py-1.5 text-sm transition-colors";
const TAB_ON = " bg-[#fce7f3] font-semibold text-[#9d2463]";
const TAB_OFF = " text-[#52525b] hover:bg-[#f4f4f5]";
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
      <dt className="w-24 shrink-0 text-[#888888]">{label}</dt>
      <dd className="min-w-0 break-words font-medium text-[#171717]">{value || "—"}</dd>
    </div>
  );
}

function Section({ no, title, synced, editorLabel = "bác sĩ điền", children }: {
  no: string; title: string; synced?: boolean; editorLabel?: string; children: React.ReactNode;
}) {
  return (
    <section className="border-t border-[#f4f4f5] pt-3">
      <h4 className="mb-2 flex flex-wrap items-center gap-2 text-sm font-semibold text-[#171717]">
        <span>{no && <span className="text-[#ec4899]">{no}.</span>} {title}</span>
        <span className={
          "rounded px-1.5 py-0.5 text-[10px] font-medium " +
          (synced ? "bg-[#dcfce7] text-[#15803d]" : "bg-[#fef9c3] text-[#a16207]")
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
  onClose,
  vitalsOnly = false,
  fill = false,
  readOnly = false,
  canEditAdmin = false,
  showSono = false,
  showRebook = false,
  onRebook,
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
}) {
  const router = useRouter();
  const p = appt.patient;
  // Engine form chuyên khoa (pilot Phụ khoa): suy service_code từ tên dịch vụ.
  // Không khớp config nào → null → engine tự ẩn.
  const serviceCode = resolveServiceCode(appt.service?.name);
  const [data, setData] = useState<Data | null>(null);
  const [loading, setLoading] = useState(true);
  const [f, setF] = useState<Fields>(EMPTY);
  const [pm, setPm] = useState<PmFields>(EMPTY_PM);
  const [tk, setTk] = useState<TkFields>(EMPTY_TK);
  const [rx, setRx] = useState<RxRow[]>([]);
  // Danh mục picker dùng chung (thuốc + CLS) — đọc 1 lần từ /api/catalog.
  const [drugOpts, setDrugOpts] = useState<DrugOpt[]>([]);
  const [clsOpts, setClsOpts] = useState<ClsOpt[]>([]);
  const [labOrder, setLabOrder] = useState("");
  const [labBusy, setLabBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  // D26 — đã bấm Lưu sinh hiệu mà thiếu trường bắt buộc → bật viền đỏ inline.
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
    setPageIdx(idx);
  };
  // Hằng số ổn định theo từng lần mount (appt cố định vì board truyền key).
  const apptSlotStart = appt.slot_start;
  const apptServiceName = appt.service?.name ?? null;

  useEffect(() => {
    if (!p?.clinic_patient_id) return;
    let on = true;
    // Trang 0 = lượt đang mở (nạp theo appointmentId, đồng thời dựng `pages`).
    // Trang >0 = lượt cũ (nạp theo visitId đã biết trong `pages`).
    const isCurrent = pageIdx === 0;
    const pastVisitId = isCurrent ? null : (pagesRef.current[pageIdx]?.visitId ?? null);
    const qs = isCurrent
      ? `patientId=${p.clinic_patient_id}&appointmentId=${appt.id}`
      : `patientId=${p.clinic_patient_id}&visitId=${pastVisitId}`;
    fetch(`/api/clinical-record?${qs}`)
      .then((r) => r.json())
      .then((d: Data) => {
        if (!on) return;
        setData(d);
        setF(readDraft(d.draft));
        setTk(readTaiKham(d.draft));
        const pr = d.profile;
        setPm(
          pr
            ? {
                allergies: arr(pr.allergies),
                blood_type: pr.blood_type ?? "",
                chronic: arr(pr.chronic_diseases),
                surgical: arr(pr.surgical_history),
                medications: arr(pr.current_medications),
                family: famText(pr.family_history),
                notes: pr.notes ?? "",
              }
            : EMPTY_PM,
        );
        setRx(
          (d.prescriptions ?? []).map((p) => ({
            drug_name: p.drug_name_raw ?? "",
            quantity: p.quantity ?? "",
            dosage: p.dosage_instructions ?? "",
            caution: p.caution ?? "",
          })),
        );
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
      .catch(() => on && setData(null))
      .finally(() => on && setLoading(false));
    return () => { on = false; };
  }, [p?.clinic_patient_id, appt.id, pageIdx, apptSlotStart, apptServiceName]);

  // Tải danh mục thuốc + CLS cho picker (dùng chung mọi loại form khám).
  useEffect(() => {
    let on = true;
    fetch("/api/catalog")
      .then((r) => (r.ok ? r.json() : { drugs: [], cls: [] }))
      .then((d: { drugs?: DrugOpt[]; cls?: ClsOpt[] }) => {
        if (!on) return;
        setDrugOpts(d.drugs ?? []);
        setClsOpts(d.cls ?? []);
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

  const locked = data?.visit?.status === "FINALIZED";

  // GATE LỄ TÂN: CHỈ ghi được (bác sĩ khám / điều dưỡng điền sinh hiệu) khi lễ tân
  // đã check-in (bệnh nhân đã đến). ÁP CHO CẢ luồng đón-khám (vitalsOnly) — quy
  // trình: LỄ TÂN check-in TRƯỚC → điều dưỡng MỚI điền sinh hiệu (đổi 2026-07-03,
  // trước đây gộp check-in + sinh hiệu làm một). COMPLETED vẫn cho xem/sửa nháp
  // khi visit chưa FINALIZED (điền lại để sửa nếu sai).
  const arrivalPending =
    appt.status !== "CHECKED_IN" && appt.status !== "COMPLETED";

  // Đủ điều kiện TỰ ĐỘNG "Khám xong": đang đã-đến + đã điền Chuẩn đoán + Lời dặn.
  const willComplete =
    !vitalsOnly &&
    appt.status === "CHECKED_IN" &&
    f.chan_doan.trim() !== "" &&
    f.loi_dan.trim() !== "";

  // Sinh hiệu (Sinh hiệu) gói riêng để dùng cho cả 2 luồng lưu.
  const vitalsPayload = () => ({
    mach: f.mach,
    nhiet_do: f.nhiet_do,
    huyet_ap: f.huyet_ap,
    nhip_tho: f.nhip_tho,
    spo2: f.spo2,
    can_nang: f.can_nang,
    chieu_cao: f.chieu_cao,
    bmi: f.bmi,
  });

  // Điều dưỡng (đón-khám): ghi Sinh hiệu + (D25) "Lý do khám bệnh" mà BS đưa ra.
  // KHÔNG đụng mục khác. D26: 3 sinh hiệu BẮT BUỘC (Huyết áp/Cân nặng/Chiều cao).
  async function saveVitals() {
    if (arrivalPending) {
      setMsg("Chờ lễ tân check-in bệnh nhân (đã đến) trước khi điền sinh hiệu.");
      return;
    }
    const missingReq = [...REQUIRED_VITALS].filter((k) => f[k].trim() === "");
    if (missingReq.length) {
      setVitalsTried(true);
      setTab(1); // C — nhảy sang tab "Khám" (chứa Sinh hiệu) để thấy ô đỏ dù đang ở tab khác.
      setMsg("Bắt buộc nhập Huyết áp, Cân nặng, Chiều cao.");
      return;
    }
    setSaving(true);
    setMsg(null);
    const res = await fetch("/api/clinical-record", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        appointmentId: appt.id,
        clinicPatientId: p?.clinic_patient_id,
        vitalsOnly: true,
        chief_complaint: f.ly_do,
        objective: { vitals: vitalsPayload() },
      }),
    });
    setSaving(false);
    if (!res.ok) {
      setMsg((await res.json()).error ?? "Lỗi lưu sinh hiệu.");
      return;
    }
    setMsg("Đã lưu sinh hiệu.");
    router.refresh();
  }

  async function save() {
    if (readOnly) return; // Lễ tân chỉ-đọc: chặn ghi ngay tầng UI (server cũng chặn).
    if (viewingPast) return; // Đang xem lượt khám cũ qua pager: tuyệt đối không ghi.
    if (vitalsOnly) return saveVitals();
    // Chưa tải xong / tải LỖI (data=null) → KHÔNG lưu: form còn rỗng sẽ ghi đè
    // xoá đơn thuốc + tiền sử + chẩn đoán cũ của lượt khám (backend thay toàn bộ).
    if (loading || !data) {
      setMsg("Chưa tải xong hồ sơ — đợi/tải lại rồi lưu (tránh mất dữ liệu cũ).");
      return;
    }
    if (arrivalPending) {
      setMsg("Chờ lễ tân xác nhận bệnh nhân đã đến (check-in) trước khi khám.");
      return;
    }
    // C — Sinh hiệu BẮT BUỘC (D26) cũng áp cho luồng bác sĩ: thiếu → nhảy tab
    // "Khám" + bật viền đỏ (REQUIRED_VITALS ở tab khác nên không thì sẽ "im lặng").
    const missingReq = [...REQUIRED_VITALS].filter((k) => f[k].trim() === "");
    if (missingReq.length) {
      setVitalsTried(true);
      setTab(1);
      setMsg("Bắt buộc nhập Huyết áp, Cân nặng, Chiều cao.");
      return;
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
            chieu_cao: f.chieu_cao, bmi: f.bmi,
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
        prescriptions: rx,
      }),
    });
    if (!res.ok) {
      setSaving(false);
      setMsg((await res.json()).error ?? "Lỗi lưu hồ sơ.");
      return;
    }
    // Điền ĐỦ (Chuẩn đoán VII + Lời dặn VIII) + BN đã đến → TỰ ĐỘNG chuyển lịch
    // sang "Đã khám xong" (COMPLETED). Không đụng FINALIZE (khóa pháp lý riêng).
    if (willComplete) {
      const done = await fetch("/api/appointments", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: appt.id, action: "complete" }),
      });
      setSaving(false);
      setMsg(
        done.ok
          ? "Đã lưu hồ sơ & chuyển bệnh nhân sang Đã khám xong."
          : "Đã lưu hồ sơ. (Chưa tự chuyển Khám xong — hãy tải lại.)",
      );
    } else {
      setSaving(false);
      setMsg(
        "Đã lưu nháp. Điền đủ Chuẩn đoán + Lời dặn sẽ tự chuyển Đã khám xong.",
      );
    }
    router.refresh();
  }

  // Bác sĩ chỉ định 1 XN mới (PENDING) → ĐD nhập kết quả ở "Hàng đợi xét nghiệm".
  async function orderLab() {
    const name = labOrder.trim();
    if (!name) return;
    setLabBusy(true);
    const res = await fetch("/api/lab-result", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        clinicPatientId: p?.clinic_patient_id,
        appointmentId: appt.id,
        test_name: name,
      }),
    });
    setLabBusy(false);
    if (!res.ok) {
      setMsg((await res.json()).error ?? "Lỗi chỉ định XN.");
      return;
    }
    // Hiện ngay trong mục VI (đang chờ kết quả).
    setData((d) =>
      d
        ? {
            ...d,
            labs: [
              {
                test_name: name,
                result_value: null,
                result_numeric: null,
                result_unit: null,
                flag: null,
                external_ref: null,
              },
              ...d.labs,
            ],
          }
        : d,
    );
    setLabOrder("");
    setMsg("Đã chỉ định XN — điều dưỡng nhập kết quả ở Hàng đợi xét nghiệm.");
  }

  const preg = data?.pregnancy;
  const labs = data?.labs ?? [];
  // khoá khi: LỄ TÂN chỉ-đọc / hồ sơ đã chốt / đang lưu / (bác sĩ) BN chưa check-in
  // / đang tải prefill (chưa tải xong mà sửa+lưu sẽ ghi đè rỗng — xem guard save())
  // / đang XEM LƯỢT KHÁM CŨ qua pager (viewingPast — chỉ đọc, không ghi đè lượt cũ).
  const ro = readOnly || locked || saving || arrivalPending || loading || viewingPast;
  const vitalsRo = (readOnly && !vitalsOnly) || locked || saving || arrivalPending || loading || viewingPast;
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
        return [f.ly_do, f.benh_su, f.mach, f.nhiet_do, f.huyet_ap, f.nhip_tho, f.spo2, f.can_nang, f.chieu_cao, f.bmi, f.tuoi_thai, f.du_kien_sinh, f.chieu_cao_tc, f.nhip_tim_thai].some(ne);
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
        "flex flex-col rounded-xl border border-[#e4e4e7] bg-white shadow-[0_1px_3px_rgba(0,0,0,0.06)] " +
        (fill
          ? "max-h-[calc(100vh-2rem)] md:max-h-none md:h-full"
          : "max-h-[calc(100vh-2rem)]")
      }
    >
      {/* Danh mục dùng chung cho picker — options bơm runtime, KHÔNG hardcode
          vào schema tĩnh. Dùng cho mọi loại form khám (PK/SK/NT/NK/HMVS). */}
      <datalist id="drug-catalog-list">
        {drugOpts.map((d) => (
          <option key={d.name_raw} value={d.name_raw}>
            {d.needs_review ? "⚠ cần dược xác nhận" : d.variant ? `biến thể: ${d.variant}` : ""}
          </option>
        ))}
      </datalist>
      <datalist id="cls-catalog-list">
        {clsOpts.map((c) => (
          <option key={c.service_code} value={c.name}>
            {c.category ?? ""}
          </option>
        ))}
      </datalist>
      <div className="flex items-center justify-between border-b border-[#e4e4e7] px-4 py-3">
        <div className="min-w-0">
          <h3 className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm font-bold uppercase text-[#171717]">
            <span>Phiếu khám bệnh</span>
            {vitalsOnly && (
              <span className="rounded bg-[#fef9c3] px-1.5 py-0.5 text-[10px] font-medium normal-case text-[#a16207]">
                Chỉ ghi Sinh hiệu
              </span>
            )}
          </h3>
          <p className="text-xs text-[#888888]">
            {p?.full_name} · {p?.patient_code}
            {viewingPast
              ? `${pages[pageIdx]?.service ? ` · ${pages[pageIdx]?.service}` : ""} · ${fmtDateTimeOrDate(pages[pageIdx]?.date ?? appt.slot_start)}`
              : `${appt.service?.name ? ` · ${appt.service.name}` : ""} · ${fmtDateTimeOrDate(appt.slot_start)}`}
          </p>
        </div>
        <button onClick={onClose} aria-label="Đóng" className="shrink-0 rounded-md p-1 text-[#71717a] hover:bg-[#f4f4f5]">
          <X size={18} />
        </button>
      </div>

      {/* Banner cảnh báo = vùng TRÊN cố định (không cuộn cùng nội dung). */}
      {!viewingPast && ((readOnly && !vitalsOnly) || locked || (arrivalPending && !readOnly)) && (
        <div className="space-y-1.5 border-b border-[#e4e4e7] px-4 py-2">
          {readOnly && !vitalsOnly && (
            <p className="rounded-md bg-[#fce7f3] px-3 py-1.5 text-xs text-[#9d2463]">
              👁 Hồ sơ lâm sàng chỉ xem (Lễ tân/CSKH có thể sửa thông tin Hành chính ở tab tương ứng).
            </p>
          )}
          {locked && (
            <p className="rounded-md bg-[#fee2e2] px-3 py-1.5 text-xs text-[#dc2626]">
              🔒 Hồ sơ đã chốt (FINALIZED) — luật cấm sửa, chỉ xem.
            </p>
          )}
          {arrivalPending && !readOnly && (
            <p className="rounded-md bg-[#fef9c3] px-3 py-1.5 text-xs text-[#a16207]">
              🕓 Chờ lễ tân check-in (bệnh nhân đã đến) —{" "}
              {vitalsOnly ? "chưa điền được sinh hiệu." : "chưa khám được."}
            </p>
          )}
        </div>
      )}

      {/* Hàng 1: Khám mới / Khám cũ (chỉ hiển thị khi có >1 lượt khám) */}
      {pages.length > 1 && (
        <div className="flex shrink-0 items-center border-b border-[#e4e4e7] bg-[#fafafa] px-3 py-1.5 select-none">
          {/* Cụm nút chuyển đổi (đứng yên) */}
          <div className="flex shrink-0 items-center gap-1.5 pr-3 border-r border-[#e4e4e7]">
            <button
              type="button"
              onClick={() => {
                if (viewingPast) goPage(0);
              }}
              className={`rounded-lg px-3 py-1 text-xs font-semibold uppercase tracking-wider transition-all duration-150 ${
                !viewingPast
                  ? "bg-[#ec4899] text-white shadow-sm"
                  : "bg-white border border-[#e4e4e7] text-[#52525b] hover:bg-[#f4f4f5]"
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
                  ? "bg-[#ec4899] text-white shadow-sm"
                  : "bg-white border border-[#e4e4e7] text-[#52525b] hover:bg-[#f4f4f5]"
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
                        ? "bg-[#eff6ff] font-semibold text-[#1e40af] border-[#bfdbfe]"
                        : "bg-white border-[#e4e4e7] text-[#52525b] hover:bg-[#f4f4f5]"
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
        <div className="flex shrink-0 gap-1 overflow-x-auto border-b border-[#e4e4e7] px-3 py-1.5">
          {TABS.map((t, i) => (
            <button
              key={t}
              type="button"
              onClick={() => setTab(i)}
              className={TAB + (i === tab ? TAB_ON : TAB_OFF)}
            >
              {t}
              {tabFilled(i) && <span className="ml-1 text-[#ec4899]">✓</span>}
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
          <details className="border-t border-[#f4f4f5] pt-3" open>
            <summary className="cursor-pointer text-sm font-semibold text-[#171717]">
              Lịch sử khám trước ({data!.history.length})
            </summary>
            <ul className="mt-2 space-y-2">
              {data!.history.map((h) => (
                <li
                  key={h.visit_id}
                  className="rounded-lg border border-[#e4e4e7] bg-[#fafafa] p-2.5 text-sm"
                >
                  <div className="flex flex-wrap items-center justify-between gap-1">
                    <span className="font-medium text-[#171717]">
                      {fmtDate(h.created_at)}
                    </span>
                    <span className="text-xs text-[#888888]">
                      {[h.service, h.doctor].filter(Boolean).join(" · ") || "—"}
                    </span>
                  </div>
                  {h.chief_complaint && (
                    <p className="mt-1 line-clamp-3 text-[#52525b]">
                      <span className="text-[#888888]">Lý do: </span>
                      {h.chief_complaint}
                    </p>
                  )}
                  {h.assessment && (
                    <p className="mt-0.5 line-clamp-2 text-[#52525b]">
                      <span className="text-[#888888]">Chuẩn đoán: </span>
                      {h.assessment}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          </details>
        )}

        {(tab === 1 || showAll) && (
        <Section no="" title="Sinh hiệu" editorLabel="lễ tân/điều dưỡng điền">
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
              ["bmi", "BMI", "number", "0.1", 5, 80],
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
                // D26: 3 trường bắt buộc → đánh dấu * + báo "Bắt buộc" khi đã bấm Lưu.
                const required = REQUIRED_VITALS.has(k);
                const missing = required && v === "" && vitalsTried;
                return (
                  <div key={k}>
                    <label className={LABEL}>
                      {lbl}
                      {required && <span className="text-[#ec4899]"> *</span>}
                    </label>
                    <input
                      type={ty}
                      step={ty === "number" ? st : undefined}
                      inputMode={ty === "number" ? "decimal" : undefined}
                      min={ty === "number" ? lo : undefined}
                      max={ty === "number" ? hi : undefined}
                      placeholder={k === "huyet_ap" ? "vd 120/80" : undefined}
                      className={INPUT + (warn || missing ? " border-[#dc2626]" : "")}
                      value={f[k]}
                      disabled={vitalsRo}
                      onChange={(e) => set(k, e.target.value)}
                    />
                    {(missing || warn) && (
                      <p className="mt-0.5 text-[11px] text-[#dc2626]">
                        {missing ? "Bắt buộc" : warn}
                      </p>
                    )}
                  </div>
                );
              },
            )}
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
                    className={INPUT + (oor ? " border-[#dc2626]" : "")}
                    value={f[k]}
                    disabled={roRest}
                    onChange={(e) => set(k, e.target.value)}
                  />
                  {oor && (
                    <p className="mt-0.5 text-[11px] text-[#dc2626]">
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
          <div className="border-t border-[#f4f4f5] pt-3">
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
            <p className="text-sm text-[#a1a1aa]">— chưa chỉ định / chưa có kết quả —</p>
          ) : (
            <ul className="divide-y divide-[#f4f4f5] rounded-lg border border-[#e4e4e7]">
              {labs.map((l, i) => (
                <li key={i} className="flex items-center justify-between gap-2 px-3 py-1.5 text-sm">
                  <span className="min-w-0 truncate text-[#171717]">{cleanTestName(l.test_name)}</span>
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
                        className="text-xs font-medium text-[#2563eb] hover:underline"
                      >
                        Phiếu
                      </a>
                    )}
                    {l.flag && l.flag !== "NORMAL" && (
                      <span className="rounded bg-[#fee2e2] px-1.5 py-0.5 text-[10px] font-medium text-[#dc2626]">{l.flag}</span>
                    )}
                  </span>
                </li>
              ))}
            </ul>
          )}
          {!vitalsOnly && !readOnly && (
            <div className="mt-2 flex items-center gap-2">
              <input
                className={INPUT}
                value={labOrder}
                list="cls-catalog-list"
                disabled={roRest}
                onChange={(e) => setLabOrder(e.target.value)}
                placeholder="Chỉ định CLS (chọn từ danh mục hoặc gõ tự do)…"
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    orderLab();
                  }
                }}
              />
              <button
                onClick={orderLab}
                disabled={roRest || labBusy || !labOrder.trim()}
                className="shrink-0 rounded-lg border border-[#f3cfe0] px-3 py-2 text-sm font-medium text-[#9d2463] hover:bg-[#fdf2f8] disabled:opacity-50"
              >
                {labBusy ? "..." : "Chỉ định"}
              </button>
            </div>
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
            <div className="space-y-2">
              {rx.length === 0 && (
                <p className="text-sm text-[#a1a1aa]">— chưa kê thuốc —</p>
              )}
              {rx.map((row, i) => (
                <div key={i} className="rounded-lg border border-[#e4e4e7] p-2">
                  <div className="flex items-center gap-2">
                    <input
                      className={INPUT}
                      placeholder="Tên thuốc"
                      list="drug-catalog-list"
                      value={row.drug_name}
                      disabled={roRest}
                      onChange={(e) => setRxAt(i, "drug_name", e.target.value)}
                    />
                    {!roRest && (
                      <button
                        onClick={() => removeRx(i)}
                        aria-label="Xoá thuốc"
                        className="shrink-0 rounded-md p-1.5 text-[#dc2626] hover:bg-[#fef2f2]"
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
                      disabled={roRest}
                      onChange={(e) => setRxAt(i, "quantity", e.target.value)}
                    />
                    <input
                      className={INPUT}
                      placeholder="Cách dùng (vd: 2v/ngày sau ăn)"
                      value={row.dosage}
                      disabled={roRest}
                      onChange={(e) => setRxAt(i, "dosage", e.target.value)}
                    />
                    <input
                      className={INPUT}
                      placeholder="Lưu ý"
                      value={row.caution}
                      disabled={roRest}
                      onChange={(e) => setRxAt(i, "caution", e.target.value)}
                    />
                  </div>
                </div>
              ))}
              {!roRest && (
                <button
                  onClick={addRx}
                  className="inline-flex items-center gap-1 rounded-lg border border-dashed border-[#f3cfe0] px-3 py-1.5 text-sm font-medium text-[#9d2463] hover:bg-[#fdf2f8]"
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
                    className="inline-flex items-center gap-1.5 text-sm text-[#3f3f46]"
                  >
                    <input
                      type="checkbox"
                      className="h-4 w-4 accent-[#ec4899]"
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
          </div>
        </Section>
        )}

        {/* Phiếu khám CHUYÊN KHOA (engine config-driven) — pilot Phụ khoa. Chỉ hiện
            cho bác sĩ (KHÔNG ở luồng đón-khám vitalsOnly) khi dịch vụ có config +
            đã có visit. FINALIZED / lễ tân chỉ-đọc → read-only (route cũng chặn ghi). */}
        {tab === 2 && !vitalsOnly && !showAll && serviceCode && data?.visit?.visit_id && (
          <div className="border-t border-[#f4f4f5] pt-3">
            <ServiceFormEngine
              visitId={data.visit.visit_id}
              serviceCode={serviceCode}
              readOnly={readOnly || locked}
            />
          </div>
        )}
      </div>

      <div className="flex items-center justify-between gap-2 border-t border-[#e4e4e7] px-4 py-3">
        <span
          className={
            "text-xs " +
            (viewingPast
              ? "text-[#1e40af]"
              : readOnly && !vitalsOnly
                ? "text-[#9d2463]"
                : msg?.startsWith("Đã lưu")
                  ? "text-[#15803d]"
                  : "text-[#dc2626]")
          }
        >
          {viewingPast ? "" : readOnly && !vitalsOnly ? "👁 Hồ sơ lâm sàng chỉ xem." : (msg ?? "")}
        </span>
        <div className="flex gap-2">
          {/* Lễ tân chỉ-đọc / đang xem lượt cũ: ẨN nút Lưu hoàn toàn (không chỉ disable). */}
          {((!readOnly || vitalsOnly) && !viewingPast) && (
            <button
              onClick={save}
              disabled={vitalsOnly ? vitalsRo : ro}
              className="min-h-10 rounded-lg bg-[#ec4899] px-4 text-sm font-semibold text-white hover:bg-[#db2777] disabled:opacity-50"
            >
              {saving
                ? "Đang lưu…"
                : vitalsOnly
                  ? "Lưu sinh hiệu"
                  : willComplete
                    ? "Lưu & Khám xong"
                    : "Lưu hồ sơ"}
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
              className="inline-flex min-h-10 items-center gap-1 rounded-lg border border-[#f3cfe0] bg-white px-4 text-sm font-semibold text-[#9d2463] hover:bg-[#fdf2f8]"
            >
              <CalendarPlus size={15} /> Tái khám
            </button>
          )}
          <button onClick={onClose} className="min-h-10 rounded-lg border border-[#e4e4e7] bg-white px-4 text-sm text-[#52525b] hover:bg-[#f4f4f5]">
            Đóng
          </button>
        </div>
      </div>
    </div>
  );
}

function Loading() {
  return <p className="text-sm text-[#a1a1aa]">Đang tải…</p>;
}
